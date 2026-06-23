# 需策划处理 + AI 影子学习（采纳/不采纳）设计文档

> 日期：2026-06-23
> 状态：已批准，待实施

## 背景与目标

当前各模块（评论/话题/BUG上报）的「采集」是单一动作——点了就采集进需求板。本设计将其升级为一套**策划处理闭环 + AI 影子学习**：

1. **统一交互**：各模块「采集」改为【需策划处理】，处理结果有两种——**采纳 / 不采纳**（不采纳也是一种处理）。按钮位置统一到本行最右侧。
2. **采纳=旧采集超集**：采纳的条目自动采集进需求板（复用现有逻辑）；不采纳只记录决定，不进需求板。
3. **待处理计数**：左侧导航栏每个模块入口标「待处理 X / 共 Y」。
4. **AI 影子学习**：后台 AI 对新条目静默预判「采纳/不采纳」（**检索式学习**：检索历史上策划处理过的相似条目作为 few-shot 参考），记录预判与策划决定是否一致，逐步逼近"AI 自动判断、撤掉人工"的目标。本期只做到"影子预判 + 准确率可见"，不做自动模式。

## 关键约束

- AI 学习走**检索式**（无训练/微调），复用现有 embedding + pgvector。
- AI 预判结果**不显示**在策划操作行旁（影子模式，避免锚定偏差影响判断）。
- 准确率统计放**游戏管理界面**，偶尔查看。
- AI 预判**只覆盖新抓取条目**，历史存量不回溯。
- **冷启动门槛 = 100**：某游戏已被策划处理的样本 < 100 时，AI 完全不预判。
- 接入模块：评论（含 BUG/建议）、话题、BUG上报。**更新公告不接入**。

## 复用的现有机制

- 需求板创建：`backend/app/api/requirements.py` `create_requirement`（含 AI 生成需求描述 `generate_requirement_text`）
- 向量检索：`backend/app/ai/dedup.py` 的 `embedding.cosine_distance` 写法（pgvector）；补上相似度阈值过滤
- 生成向量：`backend/app/ai/embedding.py` `generate_embedding`（Qwen，1024 维）
- AI 调用：`backend/app/ai/router.py` `chat(system, user, temperature, max_tokens)`，分类模式参考 `classifier.py`
- AI 流水线接入点：`backend/app/ai/pipeline.py` `run_pipeline()` 末尾
- 现有采集前端：`CommentTable.vue`(table,展开区)、`TopicList.vue`(card,头部meta)、`BugReportList.vue`(table,最右操作列)
- 侧边栏计数：`Sidebar.vue` `fetchCounts()` + `dashboard.py` `/stats`

## 数据模型 — 新表 `curation_decision`

```
curation_decision
├── id              UUID 主键
├── game_id         UUID index（BUG上报为全局，用默认游戏 id）
├── source_type     String(20)  'comment'|'bug'|'suggestion'|'topic'|'bugreport'
├── source_id       UUID index  指向原条目
├── decision        String(12)  'pending'|'adopted'|'rejected'，默认 'pending'
├── decided_by      UUID?       处理人 user id
├── decided_at      DateTime?
├── ai_prediction   String(12)? 'adopted'|'rejected'（影子预判，可空）
├── ai_predicted_at DateTime?
├── ai_hit          Boolean?    预判与策划决定是否一致（决定时回填）
├── embedding       Vector(1024)? 条目文本向量
├── source_snapshot JSONB       条目快照（标题/内容，供 AI few-shot 与需求板用）
└── created_at      DateTime
```

- 唯一约束 `(source_type, source_id)`，防重复处理。
- 记录**惰性创建**：在「AI 预判时」或「策划首次处理时」创建，不为每条新条目预建 pending 行。
- `ai_hit` 在策划决定时计算定格：`ai_prediction == decision`。
- 表由 `Base.metadata.create_all`（main.py lifespan）自动建。

**历史数据迁移（一次性脚本）**：已有 `RequirementCard` 的每条记录，按其 `(source_type, source_id)` 补一条 `curation_decision`，`decision='adopted'`、`ai_prediction` 留空、不计入准确率。

## AI 影子预判

新文件 `backend/app/ai/curation_predictor.py`，`predict_decision(source_type, source_id, text, game_id, db)`：

1. `generate_embedding(text)` → 1024 维向量
2. 冷启动门槛：查该 `game_id` 在 `curation_decision` 中 `decision != 'pending'` 的样本数；**< 100 直接返回**（不预判）
3. 检索历史样本：同 game_id、`decision != 'pending'`、按 `embedding.cosine_distance` 取最近 K=5 条
4. few-shot：把"相似历史条目 + 当时采纳/不采纳"作为示例 + 当前条目，`router.chat()` 返回 `采纳/不采纳`
5. 写回 `curation_decision`：`ai_prediction` + `ai_predicted_at` + `embedding` + `source_snapshot`（惰性建行）
6. 全程 `try/except` 静默，失败不影响主流程

**接入时机（只新条目）**：
- 评论：`pipeline.py` `run_pipeline()` 末尾追加 `_predict_curation()`
- 话题、BUG上报：各自 AI 分析/同步入库后挂一次轻量预判调用

## 后端处理 API

新文件 `backend/app/api/curation.py`，`prefix="/api/curation"`：

- `POST /decide`：body `{source_type, source_id, game_id, decision}`。
  - 写/更新 `curation_decision`（decided_by/decided_at；若已有 ai_prediction 则回填 ai_hit）
  - `decision='adopted'` → 复用 `create_requirement` 逻辑采集进需求板（已存在则跳过）
  - `decision='rejected'` → 仅记录
- `GET /decisions?game_id=&source_type=`：返回该范围内各 source_id 的处理状态（供前端渲染徽章）
- `GET /accuracy?game_id=`：返回 `{processed_count, predicting, total, hit, rate}`——最近 100 条 `ai_hit` 非空记录的一致率

## 前端三模块处理交互

统一原则：每行最右侧【需策划处理】→ 展开「采纳」「不采纳」；处理后显示徽章「✅已采纳」/「⛔已不采纳」，可点击改判。采纳=旧采集超集。

| 模块 | 文件 | 落地 |
|------|------|------|
| 评论 | `CommentTable.vue` | 展开区放【采纳】【不采纳】；行内最右加状态徽章列 |
| BUG上报 | `BugReportList.vue` | 最右操作列改【需策划处理】下拉两选项，列宽加大 |
| 话题 | `TopicList.vue` | 头部 meta「采集」换【需策划处理】小按钮，弹出两选项 |

## 侧边栏待处理计数

- `dashboard.py` `/stats` 增加 `comment_pending`/`suggestion_pending`/`topic_pending`
- `bugreports.py` `/stats` 增加 `pending`（全局）
- `Sidebar.vue`：`counts` 扩展，模板渲染「待处理 X / 共 Y」；待处理为 0 时仅显示总数
- 待处理 = 该模块条目中 `curation_decision` 无记录或 `decision='pending'` 的数量

## 游戏管理界面准确率展示

- `GameList.vue` 每个游戏卡片加一行（复用 `.detail-section` 样式），随 `loadAllJobs` 轮询：
  - 已达预判阶段：`AI 预判准确率（影子模式）近 N 条：一致 X%（hit/total）`
  - 未达标：`样本积累中（已处理 X/100）`
- 数据来自 `GET /curation/accuracy`

## 不做（本期 YAGNI）

- 不做"自动采纳"模式——留待下一期，待准确率稳定达标后加开关
- 不做微调/训练
- 历史存量条目不回溯预判
- 更新公告不接入

## 验证（端到端）

1. 迁移脚本：已有 RequirementCard 对应的 curation_decision 都为 adopted，待处理计数正确。
2. 处理动作：三模块各做一次采纳/不采纳；采纳进需求板、不采纳不进；徽章正确；侧边栏待处理数减少。
3. 预判（直连测试）：构造 ≥100 条历史决定后对新条目预判；< 100 时不预判。
4. ai_hit 回填正确。
5. 准确率接口返回正确；游戏管理界面展示两种状态。
6. 前端 `vue-tsc` + `vite build` 通过。
