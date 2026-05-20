# Comment Manager — 产品文档

> 最后更新：2026-05-20

---

## 一、产品定位

内部小团队工具（1–3 名游戏运营），用于跨平台聚合、分析和监控玩家反馈。

支持管理员 / 普通用户两种角色：管理员可管理游戏、触发爬虫；普通用户只读查看。

**解决的问题**：玩家反馈散落在 Steam 评论区、Steam 讨论区、小黑盒、Discord 等多个平台，运营者无法高效收集、分析和响应。本工具解决"玩家说了什么、哪些是 BUG/负面反馈"的问题。

**GitHub**：https://github.com/hezhenghz/comment-manager.git

---

## 二、术语定义

| 术语 | 定义 | 避免使用 |
|------|------|---------|
| **评价 (Review)** | 玩家在 Steam 商店页发布的推荐/不推荐内容 | 评论、留言 |
| **帖子 (Discussion)** | 玩家在 Steam 论坛（Hub）发起的话题，只含楼主原帖，不含回复 | 评论、讨论 |
| **Comment** | 系统内统一存储单元，所有平台内容都映射为 Comment，通过 `platform` 字段区分来源 | 消息、内容 |
| **全量爬取 (Full crawl)** | 忽略 `since`，从头抓到底。手动触发或首次运行时使用 | |
| **增量爬取 (Incremental crawl)** | 以上次爬取最新内容的 `published_at` 为截止点，只抓新内容。定时任务使用 | |

**数据关系**：
- 一个 **Game** 对应多个平台的 **Comment**
- 每次爬取产生一条 **CrawlJob** 记录，分两阶段：爬取（crawl）→ AI 分析（ai）

---

## 三、用户故事

1. 管理员添加监控的游戏（通过 Steam App ID 搜索）
2. 在游戏管理页手动触发各平台爬虫，实时查看爬取进度和 AI 分析进度
3. 系统定时自动爬取评论（APScheduler，默认 120 分钟）
4. 仪表盘看评论总量、今日新增、BUG 数量、差评率
5. 查看评论分类分布（Bug / 建议 / 投诉 / 好评 / 其他）
6. 查看评论来源分布（各平台占比）
7. 仪表盘底部查看最新评论滚动列表
8. 关键词搜索评论，按平台 / 情感 / 分类 / 语言 / 打分筛选
9. 点击评论行展开完整内容、翻译、情感评分、AI 摘要

---

## 四、侧边栏导航

| 页面 | 说明 | 权限 |
|------|------|------|
| 仪表盘 | 数据总览 | 所有用户 |
| 评论 | 全部评论列表 + 搜索筛选 | 所有用户 |
| BUG | 仅展示 category=bug 的评论 | 所有用户 |
| 建议 | 仅展示 category=suggestion 的评论 | 所有用户 |
| 游戏管理 | 游戏 CRUD + 爬虫触发 + 停用词配置 | 仅管理员 |

侧边栏顶部有游戏切换下拉框，所有数据视图均跟随所选游戏过滤。底部显示当前登录用户名 + 退出登录。

---

## 五、仪表盘

### 5.1 统计卡片（顶部 4 格）

| 格 | 指标 | 备注 |
|---|------|------|
| 1 | 总评论数 / 今日 | 当前游戏评论总量和今日新增 |
| 2 | Bug 反馈 / 今日 | 可点击跳转至 BUG 页 |
| 3 | 建议 / 今日 | 可点击跳转至建议页 |
| 4 | 差评率 | 差评率 > 30% 时显示红色警示 |

### 5.2 图表布局

```
第一行：来源分布饼图  |  分类分布饼图
底部：  最新评论滚动列表（最近 20 条，30s 自动刷新）
```

### 5.3 分类 / 来源标签映射

| 原始值 | 显示文案 |
|--------|----------|
| bug | Bug报告 |
| suggestion | 建议 |
| complaint | 投诉 |
| praise | 好评 |
| other | 其他 |
| steam_store | Steam评价 |
| steam_hub | Steam论坛 |
| discord | Discord |
| qq | QQ群 |
| xiaoheihe | 小黑盒 |

### 5.4 情感标签颜色

| 值 | 中文 | 颜色 |
|----|------|------|
| positive | 正面 | 绿色（`--positive`） |
| negative | 负面 | 红色（`--negative`） |
| neutral | 中性 | 灰色（`--neutral`） |

---

## 六、评论列表

- 筛选维度：平台 / 内容关键词搜索 / 情感 / 分类 / 语言 / 打分
- 行点击 → 原地展开：完整内容、翻译（非中文时）、AI 摘要、情感评分
- 再次点击 → 折叠
- 分页：每页 20 条

### 打分显示规则

| 平台 | thumbs_up 含义 | 显示方式 |
|------|---------------|---------|
| Steam | 1 = 推荐 / 0 = 不推荐 | 👍推荐 / 👎不推荐 |
| 小黑盒 | 1–5 星级评分 | ⭐N（≥4 绿色，≤2 红色） |

---

## 七、游戏管理（仅管理员）

### 游戏 CRUD
- 通过 Steam App ID 搜索游戏（自动填充名称 + 图标）
- 配置 Discord 频道 ID（多个）

### 爬虫状态面板

游戏列表每行可展开，展开后显示各平台状态：
- 每平台一行：平台名、累积总数、上次爬取时间、新增数、当前状态
- **两阶段进度**：爬取中（phase=crawl）→ AI分析中 X/N（phase=ai）→ 完成
- 手动触发按钮（运行中禁用）；试爬模式（限量 5 条，用于验证配置）
- 前端每 2 秒轮询 `/api/crawlers/jobs/{job_id}`

### 自定义停用词
标签式输入，回车添加，× 删除，保存调用 `PUT /api/games/{id}`。

---

## 八、AI 分析管线

触发时机：爬虫插入新评论后自动触发（异步，不阻塞 API）

**执行流程**：语言检测（本地，同步）→ 情感分析 + 分类（并行，DeepSeek）

| 产出字段 | 说明 |
|----------|------|
| `content_lang` | 语言检测（本地规则） |
| `sentiment` | positive / negative / neutral |
| `sentiment_score` | 0~1 浮点数 |
| `category` | bug / suggestion / complaint / praise / other |
| `translation` | 非中文时自动翻译 |
| `summary` | AI 摘要 |

**AI Provider**：优先使用主 Provider（model.om.dianhun.cn），熔断后自动切换备用（deepseek-v4-flash）；均失败时字段留 null，前端显示"—"。

---

## 九、爬虫支持平台

| 平台 | platform 值 | 状态 | 备注 |
|------|------------|------|------|
| Steam 商店评价 | steam_store | ✅ 可用 | 通过 Steamworks API |
| Steam 讨论区 | steam_hub | ✅ 可用 | 只含楼主原帖 |
| 小黑盒 | xiaoheihe | ✅ 可用 | Playwright 持久 Profile；首次需浏览器登录初始化 |
| Discord | discord | ✅ 可用 | 通过 Bot Token + 频道 ID 拉取消息 |
| QQ群 | qq | ⏳ 预留 | 接口已注册，爬虫未实现 |

---

## 十、数据库 Schema（核心表）

```
Game
  id                  UUID PK
  name                VARCHAR
  steam_app_id        VARCHAR NULLABLE
  icon_url            VARCHAR NULLABLE
  stopwords           TEXT[]
  discord_channel_ids TEXT[]
  created_at          DATETIME

Comment
  id              UUID PK
  game_id         UUID FK
  platform        VARCHAR   -- steam_store | steam_hub | xiaoheihe | discord | qq
  external_id     VARCHAR NULLABLE  -- 平台原始 ID，用于去重
  author_name     VARCHAR NULLABLE
  content         TEXT
  content_lang    VARCHAR NULLABLE
  published_at    DATETIME NULLABLE
  fetched_at      DATETIME
  sentiment       VARCHAR NULLABLE
  sentiment_score FLOAT NULLABLE
  category        VARCHAR NULLABLE
  summary         TEXT NULLABLE
  translation     TEXT NULLABLE
  thumbs_up       INT NULLABLE   -- Steam: 1=推荐/0=不推荐；小黑盒: 1-5 星
  thumbs_down     INT NULLABLE   -- Steam 专用

User
  id            UUID PK
  username      VARCHAR UNIQUE
  password_hash VARCHAR
  display_name  VARCHAR NULLABLE
  is_admin      BOOLEAN DEFAULT false
  created_at    DATETIME

CrawlJob
  id          UUID PK
  game_id     UUID FK
  platform    VARCHAR
  status      VARCHAR   -- running | done | failed
  phase       VARCHAR NULLABLE  -- crawl | ai | NULL（完成/失败）
  new_count   INT DEFAULT 0
  ai_total    INT DEFAULT 0
  ai_done     INT DEFAULT 0
  started_at  DATETIME
  finished_at DATETIME NULLABLE
  error_msg   TEXT NULLABLE
```

---

## 十一、API 路由

```
/api/auth              — 登录认证（/login, /me）
/api/games             — 游戏 CRUD + Steam 搜索
/api/comments          — 评论列表 + 筛选
/api/dashboard         — 统计 / 分类 / 来源
/api/crawlers          — 手动触发 + 状态查询
```

---

## 十二、技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + SQLAlchemy (async) + asyncpg + PostgreSQL |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| 图表 | ECharts |
| AI | DeepSeek API（OpenAI SDK 兼容，模型：`deepseek-chat`）；双 Provider 自动熔断切换 |
| 爬虫 | httpx（Steam/Discord）+ Playwright（小黑盒，ProactorEventLoop 线程隔离） |
| 分词 | jieba（中文） |
| 调度 | APScheduler（asyncio，定时全平台爬取） |
| 数据库 | PostgreSQL 16 + pgvector（向量字段预留） |
| 容器 | Docker Compose（仅 db 服务，后端/前端本地运行） |

---

## 十三、不做的事（Out of Scope）

- Embedding 及向量去重（pgvector 已安装，Qwen API 返回 400，功能延后）
- 语义搜索（依赖 Embedding）
- QQ 群爬虫（接口已预留）
- Alembic 数据库迁移（现阶段用 `create_all`，Schema 变更手动执行 SQL）
- Redis 缓存
- 钉钉 / 邮件等外部告警渠道
- CI/CD 流水线
