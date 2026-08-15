# 项目总结

## 目标

做一个 Amazon + TikTok Shop 词库 Agent。用户输入产品关键词后，系统自动收集公开来源关键词，整理成可下载模板，用来支持 listing、选品判断、视频选题和后续内容生成。

## 已完成

- 建立了本地网页：`http://127.0.0.1:8066`
- 支持 Amazon / TikTok Shop 切换。
- 支持英文市场和西语市场选项。
- TikTok Shop 采集改成更稳定的公开搜索建议模式，避免慢网页搜索导致 0 结果。
- 增加 Bing public suggestions fallback，Google suggestions 被限制时也能采集。
- 去掉来源噪音词，例如 `bing public`、`public`、`slip` 单独词。
- 词库导出从复杂版收敛成简约版。
- 默认 XLSX 只保留 4 个 sheet：
  - `TK模板`
  - `汇总表`
  - `agent analysis`
  - `google trends`
- 主表精简为 7 列：
  - `高频词类型`
  - `特征词`
  - `Weight`
  - `出现次数`
  - `原始搜索词`
  - `地区/语种`
  - `结论`
- 没有真实趋势数据时，不再显示空的上升速度表格。
- Agent 结论改成简单可读的候选方向判断。

## 数据判断逻辑

当前公开采集只能说明：

- 哪些词被公开搜索建议反复提到。
- 哪些长尾词更适合作为候选方向。
- 哪些词适合进入 listing、标题、评论痛点或视频选题。

当前公开采集不能说明：

- 真实搜索量。
- 真实 TikTok 热度。
- 真实销量。
- 真实 GMV。
- 真实上升速度。

如果要判断趋势，需要上传真实报告，例如：

- TikTok Creative Center 周度数据。
- TikTok Seller Center 商品表现。
- TikTok Ads search term / creative report。
- Google Trends 周度 interest。
- Amazon Ads / SQP / ABA 导出。

## 对合作者的说明

可以这样解释：

> 现在这个版本先解决词库和候选方向。我们不会把公开搜索建议伪装成真实趋势。没有后台或趋势报告时，只给候选方向；上传真实周度数据后，Agent 才会判断哪个需求总量更大、哪个方向增长更快。

## 下一步建议

1. 接入或上传 TikTok Creative Center / Seller Center 周度数据。
2. 在 `agent analysis` 里增加真实趋势排序。
3. 对每个关键词输出内容方向：listing、短视频 hook、痛点、卖点、场景。
4. 后续再恢复视频生成流程，但词库和趋势判断要先稳定。
