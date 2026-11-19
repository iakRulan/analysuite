---
name: analysuite
description: "One pipeline for the data-analysis track: dictionary-driven cleaning, descriptive statistics and group comparison, charts to PNG, generated-script execution with captured output, and SQL queries over the table via in-memory SQLite. Trigger on: '科研数据分析', '统计分析', '数据可视化', '科研代码生成与执行', '多步骤数据分析', '科研数据库查询', 'data analysis suite', 'stats and plots', 'run analysis code'. Not for: hypothesis testing claims beyond the computed numbers, or figure beautification."
---

# analysette / analysuite — Data-analysis Suite

Cover the whole analysis track with one pipeline where every reported number is recomputed from the output table. The failure mode this skill exists to prevent: statistics that don't match the data, charts with no mapping to the table, code that is written but never run, and SQL results quoted from memory.

**Method in one line:** read the table → clean (optional) → stats / chart / code / SQL per the declared modes → write each result with its input and command.

## When to use
- Input: case file (default `/input/case.json`) with `modes`/`tasks`, `inputs`, `metrics`, `group_by`, `chart`, `query`, `workorder`.
- Output: under `/app/output` — `quality_report.json`, `stats.json`, `chart.json` + `chart.png`, `code_run.json`, `query_result.json`, `result.json`.

## Modes
| mode | what it does |
|-|-|
| `clean` | dictionary-driven cleaning (missing/not-detected/zero, dedup by key, unit mapping, outlier policy) |
| `stats` | per-column n/mean/std/min/max/median/missing; group means when `group_by` is set |
| `visualize` | bar/line/scatter → `chart.png` with x/y from the case |
| `code` | generate a script from the workorder, run it, capture stdout/stderr/exit code |
| `dbquery` | load the table into in-memory SQLite and run `query`, returning columns + rows |
| `multistep` | run the declared modes in order |

## Rules that must hold
1. **Numbers are recomputed** from the output table — never quoted.
2. **Charts map to the table** (x/y columns from the case; row count recorded).
3. **Code is executed** and the exit code + output are captured.
4. **SQL errors are reported**, not hidden (e.g. reserved-word column names).
5. **Cleaning evidence** is preserved when `clean` runs (quality report).

## Exception handling
| Situation | Behaviour |
|-|-|
| pandas missing | `partial` result |
| No input table | `partial` |
| Column not found | per-column `error` entry |
| Chart columns missing | `chart.json` records the error |
| SQL syntax error | `query_result.json` records the DB error |
| Script timeout | recorded as error |

## Self-check
```bash
python3 -c "import json;s=json.load(open('/app/work/stats.json'))['stats'];print({k:v.get('mean') for k,v in s.items() if isinstance(v,dict) and 'mean' in v})"
python3 -c "import json;r=json.load(open('/app/work/result.json'));print(r['case_id'], r['status'], r['modes'], r['counts'])"
```
