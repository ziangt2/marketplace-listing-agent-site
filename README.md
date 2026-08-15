# Marketplace Listing Agent

Amazon + TikTok Shop 关键词词库工具。输入一个产品关键词，例如 `yoga mat`，系统会采集公开搜索建议和可访问的公开来源，整理成可下载的 CSV / XLSX 词库。

当前版本主线是词库，不生成模拟销售、模拟搜索量、模拟趋势或假评论。

## 核心功能

- 支持 Amazon 和 TikTok Shop 两个平台。
- 支持 US、UK、CA、AU、DE，以及 Spanish Bundle / US Spanish / Spain / Mexico 等西语市场。
- 使用公开建议源和公开页面来源生成关键词池。
- 支持上传或粘贴真实报告：Google Trends、TikTok Seller Center、TikTok Ads、Amazon Ads、SQP 等。
- 没有真实趋势数据时，只输出候选方向，不填写上升速度。
- 导出简化 XLSX：
  - `TK模板`
  - `汇总表`
  - `agent analysis`
  - `google trends`

## 主表字段

`TK模板` 默认字段：

| 字段 | 说明 |
| --- | --- |
| 高频词类型 | 按规则归类，例如核心关键词、使用场景、规格参数、痛点评论词 |
| 特征词 | 从真实来源文本中抽取的关键词或短语 |
| Weight | 内部排序分，只用于优先级，不代表官方搜索量 |
| 出现次数 | 在采集文本或上传文本中观察到的次数 |
| 原始搜索词 | 触发该词的公开搜索 query |
| 地区/语种 | 来源市场和语言 |
| 结论 | 没有真实趋势数据时显示候选方向；有真实报告时可输出更强判断 |

## Agent Analysis

`agent analysis` 用来回答合作者关心的问题：

- 当前产品先做哪个关键词方向？
- 哪些词只是公开词频高？
- 是否有真实趋势数据支撑？
- 如果没有趋势数据，下一步需要补什么？

当前逻辑：

- 只有公开搜索建议时：输出候选方向，不写上升速度。
- 上传真实周度/月度趋势报告后：可以基于真实总量和增长字段做趋势判断。

## 数据原则

本工具不会编造：

- Amazon ABA 分数
- TikTok 官方热度
- Google Trends 热度
- 搜索量
- 销量
- GMV
- 评论数
- 上升速度

空白代表没有真实来源。需要这些指标时，请上传真实后台或趋势导出。

## 本地运行

```bash
cp .env.example .env.local
npm run dev
```

打开：

```text
http://127.0.0.1:8066
```

`.env.local` 可选：

```text
OPENAI_API_KEY=sk-your-openai-key-here
GOOGLE_API_KEY=AIza-your-google-gemini-key-here
```

当前词库功能不要求 API key。API key 主要留给后续图片/视频模型测试。

## Vercel 部署

把本目录作为 Vercel 项目根目录部署：

```bash
vercel --prod --yes
```

API 路由：

```text
/api/marketplace-collect
/api/parse-upload
/api/export-keyword-xlsx
```

## 当前边界

- TikTok Shop 公开网页经常限制自动访问，所以当前 TikTok Shop 默认优先使用公开搜索建议源，保证速度和稳定性。
- 真正的“需求上升速度”必须来自真实周度/月度数据，不能靠搜索建议推断。
- 如果要做生产级 TikTok Shop 商品/评论抓取，建议接入 Apify、Bright Data 或官方后台导出。
