# Comment Manager — 产品文档

> 最后更新：2026-06-04

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
| 话题 | QQ / Discord 群聊话题聚合（AI 自动提取） | 所有用户 |
| 需求板 | 从评论/BUG/建议/话题采集的需求看板（敏捷故事板） | 所有用户 |
| 群聊 | 同一游戏下登录用户的团队聊天室 | 所有用户 |
| 阵容分析 | 阵容数据看板 | 所有用户 |
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

## 六·一、话题聚合

QQ / Discord 群聊消息按对话聚类成"话题"，由 AI 自动提取标题、摘要、分类、情感。

- 数据表：`qq_topics`（含 QQ 和 Discord 两种平台，`platform` 字段区分）
- 列表展示：标题、平台徽章（QQ 绿 / Discord 紫）、所属群/频道、分类、情感、时间范围、消息条数
- 行点击展开 → 拉取该话题关联的原始消息列表
- "重新聚合话题"按钮：手动触发 AI 重新聚类（约 30 秒）
- 每条话题可"📌 采集"到需求板

---

## 六·二、需求板（敏捷故事板）

从 评论 / BUG / 建议 / 话题 四类来源采集的需求，以便利贴卡片形式管理，模仿敏捷开发故事板。

- **采集入口**：评论/BUG/建议在展开行底部有"📌 采集到需求板"按钮；话题在话题行内有"📌 采集"按钮。已采集显示"✅ 已安排需求"。
- **三栏看板**：未开始（todo）/ 进行中（in_progress）/ 已完成（done），按状态分列
- **顶部筛选**：全部 / 评论 / BUG / 建议 / 话题
- **卡片字段**：
  1. **玩家原始内容**：展开后懒加载来源上下文（QQ/Discord 聊天前后文，或话题原始消息）
  2. **需求描述**：可编辑文本框，默认由 AI 生成——方案/开发者视角，可直接作为 Claude Code 输入（非文字润色）
  3. **状态**：下拉选择，乐观更新
- **快照机制**：采集时把来源内容存入 `source_snapshot`（JSONB），来源被删除也不影响卡片
- **去重**：同一来源重复采集返回 409，前端标记为已采集
- AI 需求生成模型：`dianhun/claude-sonnet-4-6`（主 Provider）

---

## 六·三、群聊

同一游戏下的不同登录用户实时沟通的团队聊天室，每个游戏独立。

- 方案：HTTP 短轮询（每 3 秒），不使用 WebSocket
- 数据表：`chat_messages`
- 发送：Enter 发送、Shift+Enter 换行；乐观更新（消息立即出现，失败回滚并恢复输入）
- 气泡：自己的消息靠右蓝色，他人靠左灰色，显示发送者名称 + 时间
- 拉取：初始加载最近 50 条；之后按最后一条 `created_at` 增量轮询
- 切换游戏时清空并重置轮询；离开页面停止轮询

---

## 六·四、阵容分析（《侠客2》物品选用率）

独立模块，从游戏 API 拉取玩家"离线大码"（Base64 编码的对局阵容数据），解析后统计各门派/段位下的物品选用率并可视化。与评论业务无关。

### 6.4.1 数据采集

- **来源**：游戏接口 `gateway-client.17m3.com`，遍历 10 门派 × 10 段位 × 3 失败回合区间 = 300 次请求/轮，每次最多 50 条大码。
- **解析**：手写 protobuf 解析大码，提取玩家名、门派、段位、失败回合、**回合数**、各物品累计出现次数（`item_counts`）。一条大码 = 一局 = 一条 `lineup_snapshots`。
- **去重**：大码内容 sha1（`code_hash`），重复只刷新 `last_seen_at`。
- **定时拉取**：默认每 1 小时一轮（可在页面开关/调间隔）。每轮结束自动清理 `last_seen_at` 超 7 天的陈旧快照。
- **物品元数据**：从 `ItemCfg.bytes` + `LocalizeTable.bytes` 解析物品中文名、类型（招式/内功/武器/配饰/侠客…）、品质（rank 1~5）、是否职业物品，进程内缓存。

### 6.4.2 统计口径

- **使用率%** = 物品累计出现次数 ÷ 总回合数 × 100（不去重，可 >100%，含义为"平均每回合出现 N 次"）。总回合数 = 当前筛选范围内所有快照 `round_count` 之和。
- **系列折叠**：同一物品的不同等级合并为一个"系列"统计（野球拳系列、修罗印系列、巡捕令系列）。系列 rank 取成员最高、任一成员职业则系列算职业。维护表见 `lineup/series.py`。
- **顶部统计卡**：总局数、总回合数、覆盖门派、当前筛选样本。
- **筛选**：门派 / 段位 / 显示数量 / 仅职业物品，多数图表跟随联动。

### 6.4.3 可视化模块（页面自上而下）

| 模块 | 说明 |
|------|------|
| 物品使用率柱状图 | 横向柱，Top N；物品名按品质着色，职业物品名带 ★，柱长按次数，标签显示「次数（百分比%）」 |
| 职业物品占比饼图 | 独立拉取（不依赖"仅职业物品"勾选），扇区为职业物品 |
| 各门派样本分布 | 竖向柱，各门派快照数量 |
| 按类型分组 Top/Last | 每个有数据的物品类型一行，左 Top20 / 右 Last20；空类型整行隐藏 |
| 各门派职业物品占比 | 5×2 网格，每格一个门派的职业物品饼图，前 3 名在扇区旁标名 |
| 选用失衡度 | 见下 |

### 6.4.4 选用失衡度分析（统计学方法）

评估"物品选用率低到什么程度算失衡"，采用两个标准统计指标：

- **基尼系数**：衡量某类型内部选用集中度（0=均衡，1=极端集中）。等级：<0.4 均衡（绿）/ 0.4~0.6 中度（橙）/ ≥0.6 严重（红）。
- **相对公平份额法**：某类型 N 个物品，公平份额 = 1/N；物品份额 < 公平份额×25% = 偏冷，< 10% = 严重偏冷。自适应物品数量。

模块分两部分：
1. **按类型失衡**：每类型一行，基尼系数 + 严重偏冷/偏冷数（严重偏冷后括号列出物品名），可展开看偏冷清单。
2. **职业物品前3失衡**：每门派只统计选用最高的前 3 个职业物品（其余为跨门派抓取的杂质），固定对比 10 门派，按前3基尼排序。

- **排除名单**：BOSS 掉落等稀缺物品（用得少是因为掉得少，非被冷落）不计入失衡统计，维护表见 `lineup/exclusions.py`。仅影响失衡统计，不影响使用率图表。失衡模块顶部只读展示已排除物品。

### 6.4.5 性能

聚合端点（usage / usage-by-type / stats / 失衡）加内存缓存，用「数据指纹 =（快照行数, max(last_seen_at)）」做失效信号。数据未变时切页签命中缓存（毫秒级）；拉取/清理改变指纹自动失效重算。

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
| QQ群 | qq | ✅ 可用 | NapCat / LagRange OneBot v11 HTTP API；专用小号登录；@ 指定 QQ 号无条件入库 |

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
  qq_group_ids        TEXT[]
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
  bug_status         VARCHAR NULLABLE  -- NULL=未处理 | accepted=已接受 | completed=已完成
  -- AI 分析状态机（爬取与分析解耦）
  ai_status          VARCHAR DEFAULT 'pending'  -- pending | done | failed | skipped
  ai_retry_count     INT DEFAULT 0
  next_ai_attempt_at DATETIME NULLABLE   -- 指数退避调度时间
  last_ai_error      TEXT NULLABLE
  is_game_feedback   BOOLEAN NULLABLE    -- Discord 过滤器：是否游戏反馈

QQTopic
  id          UUID PK
  game_id     UUID FK
  title       VARCHAR
  summary     TEXT
  category    VARCHAR NULLABLE
  sentiment   VARCHAR NULLABLE
  group_id    VARCHAR NULLABLE   -- QQ group_id 或 Discord channel_id
  platform    VARCHAR NULLABLE   -- qq | discord | NULL(旧数据)
  comment_ids UUID[]             -- 关联的 Comment id 列表
  started_at  DATETIME NULLABLE
  ended_at    DATETIME NULLABLE
  created_at  DATETIME

RequirementCard
  id               UUID PK
  game_id          UUID FK
  source_type      VARCHAR   -- comment | bug | suggestion | topic
  source_id        UUID      -- 来源记录 id
  source_snapshot  JSONB     -- 采集时的内容快照
  requirement_text TEXT      -- AI 生成的需求描述（可编辑）
  status           VARCHAR DEFAULT 'todo'  -- todo | in_progress | done
  created_at       DATETIME
  updated_at       DATETIME

ChatMessage
  id           UUID PK
  game_id      UUID FK
  user_id      UUID FK
  display_name VARCHAR   -- 发送时的用户名快照
  content      TEXT
  created_at   DATETIME  -- 与 game_id 组成复合索引

LineupSnapshot                  -- 阵容分析：一条大码 = 一局玩家阵容
  id            UUID PK
  code_hash     VARCHAR UNIQUE  -- 大码 sha1，去重键
  raw_code      TEXT            -- 大码 base64 原文
  player_name   VARCHAR NULLABLE
  men_pai       INT INDEX       -- 门派枚举 2~11
  rank_level    INT INDEX       -- 段位 1~10
  fail_round    INT NULLABLE
  round_count   INT DEFAULT 0   -- 该局回合数
  item_counts   JSONB           -- { "itemId": 累计出现次数 }
  first_seen_at DATETIME
  last_seen_at  DATETIME        -- 清理依据（超 7 天删除）

LineupFetchJob                  -- 阵容拉取任务状态
  id          UUID PK
  status      VARCHAR    -- running | done | failed
  req_total   INT DEFAULT 0   -- 计划请求数（300）
  req_done    INT DEFAULT 0
  new_count   INT DEFAULT 0
  started_at  DATETIME
  finished_at DATETIME NULLABLE
  error_msg   TEXT NULLABLE

LineupScheduleConfig            -- 阵容自动拉取配置（开关 / 间隔）
  id             UUID PK
  enabled        BOOLEAN
  interval_hours INT

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
/api/topics            — 话题聚合列表 / 重新聚合
/api/requirements      — 需求板卡片 CRUD
/api/chat              — 群聊消息收发（短轮询）
/api/bugreports        — BUG 上报（禅道同步）
/api/lineup            — 阵容分析：拉取 / 调度 / 使用率 / 按类型 / 失衡度等
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
- Alembic 数据库迁移（现阶段用 `create_all`，Schema 变更手动执行 SQL）
- Redis 缓存
- 钉钉 / 邮件等外部告警渠道
- CI/CD 流水线
