# 自测记录（示例，非平台正式案例）

- 输入：4 行构造 CSV，modes=stats/visualize/dbquery
- 结果：value 均值 16.0、score 均值 0.65；分组 A=11.0 / B=21.0；柱图 chart.png；SQL 返回 2 行（A=11.0, B=21.0）
- 验证：SQL 使用保留字 `group` 时如实上报 DatabaseError，不隐藏。

> 本文件为技能自测示例，不冒充平台正式案例结果。
