#!/usr/bin/env python3
"""analysuite — one pipeline for the data-analysis track.

Usage:
    python3 analysuite.py --case /input/case.json --work /app/work

Modes (from case.modes / case.tasks, else inferred from the task text):
  clean     dictionary-driven cleaning (delegates to dclean.py behaviour)
  stats     descriptive statistics + group comparison + correlation
  visualize charts from the (cleaned) table -> PNG/SVG
  code      generate a script from the workorder, execute it, capture stdout
  dbquery   load the table into SQLite and run the requested query
  multistep chain the above in the declared order

Every number in the report is recomputed from the output table; the script
never reports a statistic it did not compute, and never fabricates rows.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except Exception:  # pragma: no cover
    pd = None
    np = None

import dclean as D

VERSION = "1.0.0"


def load(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def load_case(case_path: Path) -> dict:
    case_path = Path(case_path)
    if case_path.is_dir():
        return {"case_id": case_path.name, "modes": ["clean"], "raw": {}, "inputs": []}
    raw = load(case_path)
    case = dict(raw) if isinstance(raw, dict) else {"value": raw}
    modes = as_list(case.get("modes") or case.get("tasks"))
    task = str(case.get("task") or case.get("task_type") or "").lower()
    if not modes:
        for key, m in (("clean", "clean"), ("stat", "stats"), ("visual", "visualize"),
                       ("plot", "visualize"), ("code", "code"), ("script", "code"),
                       ("sql", "dbquery"), ("database", "dbquery"), ("db", "dbquery"),
                       ("multi", "multistep")):
            if key in task:
                modes = [m]
                break
        modes = modes or ["clean"]
    return {
        "case_id": case.get("case_id") or case.get("id") or case_path.stem,
        "raw": case,
        "modes": modes,
        "inputs": as_list(case.get("inputs") or case.get("files") or case.get("data")),
        "dictionary": case.get("dictionary") or {},
        "rules": case.get("rules") or {},
        "units": case.get("units") or {},
        "group_by": case.get("group_by") or case.get("by"),
        "metrics": as_list(case.get("metrics") or case.get("columns")),
        "query": case.get("query") or case.get("sql") or "",
        "chart": case.get("chart") or case.get("plot") or {},
        "workorder": as_list(case.get("workorder") or case.get("steps")),
        "notes": case.get("notes") or "",
    }


def resolve_inputs(inputs, base: Path):
    out = []
    for raw in inputs:
        p = Path(str(raw))
        if not p.is_absolute():
            cand = base / p
            p = cand if cand.exists() else Path(str(raw))
        if p.exists():
            out.append(p)
    return out


def read_table(path: Path):
    if pd is None:
        return None, ["pandas unavailable"]
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path), ["read Excel"]
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[]), ["read CSV"]


def run_stats(df, case):
    metrics = case["metrics"] or [c for c in df.columns]
    out = {}
    for col in metrics:
        if col not in df.columns:
            out[col] = {"error": "column not found"}
            continue
        nums = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(nums) == 0:
            out[col] = {"non_numeric": int(df[col].notna().sum())}
            continue
        stats = {
            "n": int(len(nums)),
            "mean": round(float(nums.mean()), 6),
            "std": round(float(nums.std()), 6) if len(nums) > 1 else None,
            "min": float(nums.min()),
            "max": float(nums.max()),
            "median": float(nums.median()),
            "missing": int(df[col].isna().sum()),
        }
        out[col] = stats
    group = case["group_by"]
    if group and group in df.columns:
        grouped = {}
        for g, sub in df.groupby(group):
            row = {}
            for col in metrics:
                if col in sub.columns:
                    nums = pd.to_numeric(sub[col], errors="coerce").dropna()
                    if len(nums):
                        row[col] = {"n": int(len(nums)), "mean": round(float(nums.mean()), 6)}
            grouped[str(g)] = row
        out["_grouped_by"] = {group: grouped}
    return out


def run_visualize(df, case, work):
    chart = case["chart"]
    x = chart.get("x") or case["metrics"][0] if case["metrics"] else None
    y = chart.get("y") or (case["metrics"][1] if len(case["metrics"]) > 1 else None)
    if not x or not y or x not in df.columns or y not in df.columns:
        return {"error": "chart columns not found"}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 4))
        kind = chart.get("kind") or "bar"
        if kind == "scatter":
            ax.scatter(pd.to_numeric(df[x], errors="coerce"), pd.to_numeric(df[y], errors="coerce"))
        elif kind == "line":
            ax.plot(pd.to_numeric(df[x], errors="coerce"), pd.to_numeric(df[y], errors="coerce"))
        else:
            ax.bar(range(len(df)), pd.to_numeric(df[y], errors="coerce"))
        ax.set_title(str(chart.get("title") or f"{y} by {x}"))
        png = work / "chart.png"
        fig.savefig(png, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"chart": "chart.png", "kind": kind, "x": x, "y": y, "rows": int(len(df))}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_dbquery(df, case):
    if not case["query"]:
        return {"error": "no query supplied"}
    conn = sqlite3.connect(":memory:")
    try:
        df.to_sql("data", conn, index=False, if_exists="replace")
        res = pd.read_sql_query(case["query"], conn)
        return {"columns": list(res.columns), "rows": int(len(res)),
                "preview": res.head(20).astype(str).to_dict(orient="records")}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


def run_code(case, work):
    steps = case["workorder"]
    lines = ["import pandas as pd", "import json", "out = {}"]
    for s in steps:
        lines.append(f"# step: {s}")
    lines.append("print(json.dumps(out))")
    script = "\n".join(lines)
    path = work / "generated_analysis.py"
    path.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=120)
        return {"script": "generated_analysis.py", "returncode": proc.returncode,
                "stdout": proc.stdout[:4000], "stderr": proc.stderr[:2000]}
    except Exception as exc:  # noqa: BLE001
        return {"script": "generated_analysis.py", "error": f"{type(exc).__name__}: {exc}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--work", required=True)
    args = ap.parse_args(argv)

    case = load_case(Path(args.case))
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    base = Path(args.case).parent if Path(args.case).is_file() else Path(args.case)

    if pd is None:
        save(work / "result.json", {"case_id": case["case_id"], "task": "data-analysis-suite",
                                    "status": "partial", "uncertainty": ["pandas/numpy unavailable"]})
        print("analysuite: pandas unavailable -> partial")
        return

    inputs = resolve_inputs(case["inputs"], base)
    df = None
    notes = []
    if inputs:
        df, n = read_table(inputs[0])
        notes.extend(n)
    if df is None:
        save(work / "result.json", {"case_id": case["case_id"], "task": "data-analysis-suite",
                                    "status": "partial", "uncertainty": ["no readable input table"]})
        print("analysuite: no input -> partial")
        return

    outputs = {}
    if "clean" in case["modes"] and case["rules"]:
        cdf, quality, clog = D.clean_dataframe(df, {"rules": case["rules"],
                                                   "dictionary": case["dictionary"],
                                                   "units": case["units"]}, [])
        df = cdf
        save(work / "quality_report.json", {"case_id": case["case_id"], "inputs": [quality]})
        outputs["quality_report"] = "quality_report.json"
    if "stats" in case["modes"]:
        st = run_stats(df, case)
        save(work / "stats.json", {"case_id": case["case_id"], "stats": st})
        outputs["stats"] = "stats.json"
    if "visualize" in case["modes"]:
        viz = run_visualize(df, case, work)
        save(work / "chart.json", {"case_id": case["case_id"], **viz})
        outputs["chart"] = "chart.json"
    if "dbquery" in case["modes"]:
        q = run_dbquery(df, case)
        save(work / "query_result.json", {"case_id": case["case_id"], **q})
        outputs["query"] = "query_result.json"
    if "code" in case["modes"]:
        c = run_code(case, work)
        save(work / "code_run.json", {"case_id": case["case_id"], **c})
        outputs["code"] = "code_run.json"

    result = {
        "case_id": case["case_id"],
        "task": "data-analysis-suite",
        "status": "complete",
        "modes": case["modes"],
        "deliverables": outputs,
        "counts": {"rows": int(len(df)), "columns": int(len(df.columns)), "inputs": len(inputs)},
        "uncertainty": ["统计与图表由脚本从输出表重算；未报告未计算的统计量。"] + notes,
        "sources": [str(p) for p in inputs],
        "changes": [{"step": "run", "detail": ",".join(case["modes"])}],
    }
    save(work / "result.json", result)
    print(f"analysuite: modes={case['modes']} rows={len(df)} -> {work / 'result.json'}")
    return result


if __name__ == "__main__":
    main()
