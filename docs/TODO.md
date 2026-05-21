# Comment Manager — 待办事项

> 记录聊过但还没做的需求和技术债。已实现的移入底部 ✅ 区域。

---

## 🔴 待处理

### Qwen Embedding API 400 错误
- **问题**：调用 `dashscope.aliyuncs.com/compatible-mode/v1/embeddings` 持续返回 400
- **影响**：embedding 字段无法写入，向量搜索功能不可用（当前已禁用，不影响主流程）
- **操作**：检查 DashScope API Key 是否有效，或确认接口地址 / 模型名是否正确

---

## 🟡 功能补全

### Embedding / 向量去重
- **现状**：`embedding` 字段存在，Qwen API 返回 400，功能暂停
- **待做**：修复 API 问题后，在 pipeline 中启用 embedding 生成，前端加重复评论过滤开关

### 语义搜索
- **前提**：Embedding 功能启用后才能做
- **现状**：`/api/search` 关键词全文搜索已实现，向量搜索未做

---

## 🟢 优化项

### 累积趋势查询性能
- **问题**：数据量大时，累积模式每个日期点需全表扫描
- **方案**：按天预聚合写入缓存表，或加 Redis 缓存

### Alembic 数据库迁移
- **现状**：用 `create_all` 初始化，Schema 变更手动执行 SQL
- **待做**：引入 Alembic，生成迁移脚本

### 告警端到端测试
- 关键词规则：爬到含关键词评论 → alert_events 有记录 → 侧边栏红点出现
- 阈值规则：24h 负面率超阈值 → 触发一次（1小时冷却）
- 标记已读 → 红点消失

---

## ✅ 已完成

### 2026-05-21
- **QQ 群爬虫**：基于 NapCat / LagRange OneBot v11 HTTP API 实现；`Game` 表加 `qq_group_ids` 字段；CQ 码解析提取纯文本；`get_group_msg_history` 翻页 + `since` 增量截断
- **QQ 消息分级过滤**：@ 指定 QQ 号（`QQ_AT_ALWAYS_INCLUDE`，逗号分隔多个）的消息无条件入库；其余消息走更严格的 AI 过滤（提高门槛，出错时丢弃而非保留）
- **仪表盘来源分布饼图**：扇区颜色改为与评论列表平台徽章一致；去掉右侧图例
- **仪表盘评论分类饼图**：去掉右侧图例，改为指引线 + 分类名 + 百分比标注
- **一键启动升级为 Windows Terminal 多标签**：`启动.bat` 改用 `wt` 打开单个 Windows Terminal 窗口，NapCat / 后端 / 前端各占一个标签页；新增 `start-napcat.ps1` 辅助脚本（解决 wt 命令行中 `;` 歧义问题）；最小化窗口可保持服务运行
- **游戏管理爬取时间 UTC 修复**：`formatTime` 补加 `Z` 后缀，修复完成时间比本地时间早 8 小时的问题（后端 `datetime.utcnow()` 序列化无时区标识，JS 误当本地时间）
- **爬取完成时间实时更新**：手动爬取完成后 `fetchTrackedJob` 主动调用 `loadJobs` 刷新显示时间；定时爬取依赖 3s `pollTimer` 自动更新
- **进度条预计时间改为历史实际耗时**：新增 `crawlDurationSec` ref，页面加载及每次爬取完成时记录实际耗时（按 game+platform 区分），无历史记录时回落硬编码默认值
- **游戏管理配置提示精简**：移除 Discord 频道 ID 和 QQ 群号配置区域下方的两行说明文字

### 2026-05-20
- **小黑盒分页修复**：`total_page` 固定返回 100 不可信，改用签名 URL 里的 `limit=10` 作为 offset 步长，连续 2 次无新增才终止，从只抓 19 条恢复到全量抓取
- **评分字段统一**：小黑盒 1–5 星改存 `thumbs_up`（与 Steam 0/1 共用同一列），移除 `rating` 字段
- **管理员权限系统**：`User` 表加 `is_admin` 字段；`manage.py setadmin <用户名>` 命令；路由守卫阻止非管理员访问 `/games`；侧边栏"游戏管理"仅管理员可见
- **侧边栏用户信息**：底部退出登录左侧显示当前登录用户的 display_name（或 username）
- **仪表盘 UI 优化**：移除 BugFeed 模块；最新评论的来源徽章改为按平台区分颜色（与评论列表一致）；情感标签改为中文（正面/负面/中性）
- **全局滚动条美化**：4px 细条，深色主题配色，Webkit 和 Firefox 均覆盖
- **Auth 状态修复**：AppShell 挂载时自动 `fetchMe`，页面刷新后正确恢复 `is_admin` 状态

### 2026-05-19
- 删游戏外键约束修复：`CrawlJob` 加 relationship cascade，删游戏 API 先清 crawl_jobs
- AI 双备份：主 Provider（model.om.dianhun.cn）熔断后自动切换备用（deepseek-v4-flash），均失败时情感/分类留 null，前端显示"—"
- 小黑盒爬虫：Playwright 持久 Profile 方案实现完成（代码层面），待用户完成浏览器登录初始化

### 2026-05-14
- 试爬逻辑修复：`full=True` + `fetch_limit = existing_count + limit`，每次试爬稳定新增 5 条
- 按钮闪烁修复：`startTracking` 同步写入初始 running 状态，消除轮询间隙
- AI 分析管线优化：并行执行情感分析 + 分类；删除摘要（summary）和向量去重（find_similar）；`max_tokens` 从 512 → 10
- 爬取两阶段解耦：Phase1（爬取+插入）提交后 Phase2（AI分析）再开始，前端可实时看到双进度
- 按 job_id 轮询：`/run` 和 `/trial` 返回 `job_id`，前端轮询 `/crawlers/jobs/{job_id}`，不受 APScheduler 干扰

### 2026-05-11 及之前
- 图表 autoresize 无限循环 bug 修复
- 情感趋势图改为健康分（0-100），支持累积/今日切换
- 词云情感着色（绿/红/灰，饱和度代表强度）
- 词云停用词两层机制（内置 + 游戏自定义）
- 仪表盘底部 Bug 反馈列表，统计卡可滚动定位
- 评论分类 / 来源分布改中文标签
- 评论行点击展开（内容 + 情感评分 + 分类）
- 告警模块：keyword + threshold 两种规则
- 告警事件历史（alert_events），侧边栏未读红点
- 游戏管理：爬虫状态面板（CrawlJob），两阶段进度条
- 游戏管理：自定义停用词标签编辑器
- 删除报表 / 导出 / 设置模块
- 侧边栏精简为 4 个入口
- APScheduler 定时任务（120分钟间隔全平台爬取）
