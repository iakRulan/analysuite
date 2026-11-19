# analysette — 科研数据分析综合 Skill

一条管线覆盖数据分析赛道：清洗、统计、可视化、代码生成与执行、SQL 查询。

## 依赖
- Python 3.9+；pandas/numpy；matplotlib（可视化）；标准库 sqlite3。

## 用法
```bash
python3 scripts/analysuite.py --case /input/case.json --work /app/work
```

输入示例：
```json
{
  "case_id": "demo",
  "modes": ["stats", "visualize", "dbquery"],
  "inputs": ["data.csv"],
  "metrics": ["value", "score"],
  "group_by": "grp",
  "chart": {"kind": "bar", "x": "grp", "y": "value"},
  "query": "SELECT grp, AVG(value) AS mean_value FROM data GROUP BY grp"
}
```
> 示意示例，不是正式案例结果。

## 输出
| 文件 | 内容 |
|-|-|
| `stats.json` | 每列 n/mean/std/min/max/median/missing；分组均值 |
| `chart.json` + `chart.png` | 图表参数与渲染结果 |
| `query_result.json` | SQL 列名 + 行 + 预览（或错误） |
| `code_run.json` | 生成脚本、退出码、stdout/stderr |
| `quality_report.json` | 清洗证据（有 clean 时） |
| `result.json` | `case_id` / `status` / modes / counts |

## 关键设计
统计由输出表重算；图表与表列映射；代码真执行并留输出；SQL 错误如实上报；清洗证据保留。

## 局限
- 不做超出所算数字的统计推断；不做出版级美化。

## 版本
analysuite 1.0.0。
