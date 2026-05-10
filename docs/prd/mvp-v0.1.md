# Comment Manager v0.1 — MVP PRD

## Problem Statement

游戏社区运营者需要跨平台监控玩家反馈。当前反馈散落在 Steam 评论区、Steam 讨论区、Discord、QQ、小黑盒等多个平台，运营者无法高效收集、分析和响应。本工具解决"玩家说了什么，哪些是负面/BUG反馈，什么时候应该触发告警"的问题。

## Solution

Comment Manager 是一个游戏社区评论聚合分析平台。MVP 阶段聚焦 Steam 平台，爬取评论和讨论帖，通过 DeepSeek AI 自动分析情感/分类/摘要/去重，在 Dashboard 可视化展示趋势，关键词命中时通过钉钉推送告警。

## User Stories

1. 作为游戏运营者，我想要添加监控的游戏（通过 Steam App ID），以便指定监控范围
2. 作为游戏运营者，我想要手动触发 Steam 评论爬虫，以便立即获取最新评论
3. 作为游戏运营者，我想要系统定时自动爬取评论，以便持续监控无需手动操作
4. 作为游戏运营者，我想要在 Dashboard 看到评论总量、今日新增、BUG 数量、负面率，以便快速掌握舆情概况
5. 作为游戏运营者，我想要查看评论趋势图（按日），以便发现舆情波动的节点
6. 作为游戏运营者，我想要查看评论分类分布（BUG/建议/投诉/赞美/其他），以便识别反馈类型占比
7. 作为游戏运营者，我想要查看评论来源分布（Steam 商店 vs Steam 讨论区），以便了解各渠道活跃度
8. 作为游戏运营者，我想要查看词云（从评论内容中提取高频关键词），以便直观了解玩家在讨论什么
9. 作为游戏运营者，我想要用关键词搜索评论，以便找到特定话题的反馈
10. 作为游戏运营者，我想要按平台、情感、分类筛选评论，以便缩小关注范围
11. 作为游戏运营者，我想要设置关键词告警规则（如 "crash"、"闪退"），当新评论命中时通过钉钉推送通知
12. 作为游戏运营者，我想要告警有冷却时间（5分钟），以避免同一规则在短时间内刷屏
13. 作为游戏运营者，我想要生成评论报告（Excel/PDF），以便分享给团队或留档
14. 作为游戏运营者，我想要 AI 自动判断评论情感（正面/负面/中性），以便快速识别需要关注的反馈
15. 作为游戏运营者，我想要 AI 自动分类评论（BUG/建议/投诉/赞美/其他），以便按类别处理
16. 作为游戏运营者，我想要长评论自动生成摘要，以便无需逐条阅读即可了解要点
17. 作为游戏运营者，我想要语义相似的重复评论自动标记去重，以便不被刷屏干扰
18. 作为游戏运营者，我想要通过用户名密码登录，以便保护数据不被未授权访问
19. 作为游戏运营者，我的 Steam 商店评论和讨论区双路采集中有一条失败时，另一条仍能保证数据入库
20. 作为游戏运营者，我预留了 Discord/QQ/小黑盒的爬虫接口，以便后续扩展其他平台

## Implementation Decisions

### AI Provider 架构
- Chat 统一使用 DeepSeek `deepseek-v4-flash`，通过 OpenAI SDK 兼容接口调用
- Embedding 使用 Qwen `text-embedding-v3`，通过 DashScope 兼容接口调用
- 去除 primary/fallback 双层容错架构，改为直接路由：Chat → DeepSeekProvider，Embed → QwenProvider
- AI 调用异常时优雅降级：Chat 返回空字符串，Embedding 返回空列表，后续 pipeline 步骤有独立容错
- 向量维度从 1536（OpenAI text-embedding-3-small）迁移到 1024（Qwen text-embedding-v3）
- 语种检测使用 langdetect 库，独立于 AI pipeline
- AI 分析步骤失败时不阻塞后续步骤，每条评论独立容错

### 爬虫容错
- 规则优先降级：情感分析和分类在 AI 失败时有规则匹配回退（中英文关键词）
- Steam 商店评论和 Steam 讨论区双路独立采集
- 重复评论通过 pgvector 余弦相似度自动去重（阈值 0.85）
- 爬虫翻页有上限（评论 10 页、讨论 5 页），按时间倒序增量抓取

### 告警
- 关键词匹配检查在新评论入库时触发（非回溯）
- 同一规则的冷却时间为 5 分钟，通过 `last_triggered_at` 字段控制
- 钉钉推送使用 webhook markdown 格式

### 词云
- 改用 jieba 分词从评论内容提取关键词
- 内置中英文停用词过滤
- 过滤长度小于 2 的词
- 按词频降序取 top N

### 路由架构
- `/api/auth` — 登录认证
- `/api/games` — 游戏 CRUD
- `/api/comments` — 评论列表 + 筛选
- `/api/search` — 语义搜索（pgvector）或全文搜索
- `/api/dashboard` — 统计/趋势/分类/来源/词云
- `/api/alerts` — 告警规则 CRUD
- `/api/reports` — 报告任务 CRUD
- `/api/export` — 报告生成 + 下载
- `/api/crawlers` — 爬虫手动触发
- `/api/settings` — 系统设置（暂为占位）

### Schema
- Game: id, name, steam_app_id, icon_url, created_at
- Comment: id, game_id, platform, source_type, source_url, author_name, content, content_lang, published_at, fetched_at, sentiment, sentiment_score, category, summary, embedding(Vector 1024), is_duplicate, duplicate_of, thumbs_up, thumbs_down, raw_json, created_at
- User: id, username, password_hash, display_name, created_at
- AlertRule: id, game_id, keywords, channel, enabled, last_triggered_at, created_at
- ReportTask: id, game_id, type, date_range, schedule, status, file_path, created_at

### 前端技术栈
- Vue 3 + TypeScript + Vite
- Pinia 状态管理，Vue Router 路由
- Axios（token 自动注入 + 401 自动跳转登录）
- ECharts（Dashboard 图表），暗色主题 CSS 变量

## Testing Decisions

- 测试应验证外部行为，不测试实现细节
- 优先测试模块：AI router（容错降级）、告警冷却逻辑、jieba 词云（停用词过滤 + 中文分词）、Steam 爬虫（HTML 解析 + 去重）
- AI 相关测试应 mock provider 避免真实 API 调用
- 测试方式：pytest + httpx AsyncClient（后端接口），vitest（前端）

## Out of Scope

- 多用户权限/角色系统（当前为单人使用）
- Discord/QQ/小黑盒爬虫实现（已预留代码桩和扩展接口）
- Alembic 数据库迁移（现阶段使用 `create_all` 初始化）
- Redis 缓存层（当前数据量小，实时查询够用）
- 前端 E2E 测试
- CI/CD 流水线
- Steam API 方案（当前只用 HTML 爬虫，API 方案后续补充）

## Further Notes

- MVP 目标游戏：背包闯江湖（Steam App ID: 3972650）
- 预期数据量：1 款游戏，每天最多 100 条新评论
- 运行环境：单机 Docker Compose（pgvector + FastAPI + Vue）
- DeepSeek API: `api.deepseek.com`，模型 `deepseek-v4-flash`
- Qwen Embedding: `dashscope.aliyuncs.com/compatible-mode/v1`，模型 `text-embedding-v3`
- `deepseek-chat` / `deepseek-reasoner` 别名将于 2026 年 7 月弃用，新代码直接使用 `deepseek-v4-flash`
