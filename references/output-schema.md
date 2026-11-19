# 输出字段字典

## `stats.json`
`stats{column}: {n, mean, std, min, max, median, missing}`；分组时追加 `_grouped_by{by: {group: {col: {n, mean}}}}`

## `chart.json`
`{chart|error, kind, x, y, rows}`

## `query_result.json`
`{columns[], rows, preview[]{...}}` 或 `{error}`

## `code_run.json`
`{script, returncode, stdout, stderr}` 或 `{script, error}`

## `result.json`
`case_id` / `task` / `status` / `modes[]` / `deliverables{}` / `counts{rows, columns, inputs}` / `uncertainty` / `sources` / `changes`
