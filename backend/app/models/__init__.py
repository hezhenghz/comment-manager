import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Boolean, Integer, DateTime, ForeignKey, Text as SAText, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, DATERANGE, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    steam_app_id: Mapped[str | None] = mapped_column(String(50))
    icon_url: Mapped[str | None] = mapped_column(String(1024))
    stopwords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    discord_channel_ids:   Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    discord_channel_names: Mapped[dict]      = mapped_column(JSONB, default=dict)  # {channel_id: 自定义名称}
    qq_group_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    comments: Mapped[list["Comment"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    alert_rules: Mapped[list["AlertRule"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(String(100), index=True)
    author_name: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_lang: Mapped[str | None] = mapped_column(String(10))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # AI analysis
    sentiment: Mapped[str | None] = mapped_column(String(20), index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    translation: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)
    # Metadata
    thumbs_up: Mapped[int | None] = mapped_column(Integer)
    thumbs_down: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, name="raw_json")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # BUG 处理状态：None=未处理, accepted=已接受, completed=已完成
    bug_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # ── AI 分析状态机（PR1：爬取与 AI 分析解耦）─────────────────────────
    # ai_status: pending=待 worker 分析 / done=分析完成 / failed=超过最大重试 / skipped=Discord 过滤器判为非游戏反馈
    ai_status:          Mapped[str]             = mapped_column(String(20), nullable=False, default="pending", index=True)
    ai_retry_count:     Mapped[int]             = mapped_column(Integer, nullable=False, default=0)
    # 指数退避用：worker 只挑 next_ai_attempt_at IS NULL 或 < utcnow() 的 pending
    next_ai_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_ai_error:      Mapped[str | None]      = mapped_column(Text, nullable=True)
    # Discord 过滤器结果：True=是游戏反馈走完整 pipeline / False=过滤掉 / None=其他平台或未判定
    is_game_feedback:   Mapped[bool | None]     = mapped_column(Boolean, nullable=True)

    game: Mapped["Game"] = relationship(back_populates="comments")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), default="keyword")  # keyword | threshold
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    threshold_value: Mapped[float | None] = mapped_column(Float)  # 负面率阈值 %
    channel: Mapped[str] = mapped_column(String(50), default="in_app")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    game: Mapped["Game"] = relationship(back_populates="alert_rules")
    events: Mapped[list["AlertEvent"]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_rules.id"), nullable=False)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    rule: Mapped["AlertRule"] = relationship(back_populates="events")


class QQTopic(Base):
    __tablename__ = "qq_topics"

    id:          Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id:     Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, index=True)
    title:       Mapped[str]             = mapped_column(String(255), nullable=False)
    summary:     Mapped[str]             = mapped_column(Text, nullable=False)
    category:    Mapped[str | None]      = mapped_column(String(50))
    sentiment:   Mapped[str | None]      = mapped_column(String(20))
    group_id:    Mapped[str | None]      = mapped_column(String(50))         # QQ group_id 或 Discord channel_id
    platform:    Mapped[str | None]      = mapped_column(String(50))         # "qq" | "discord" | None(旧数据)
    comment_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    started_at:  Mapped[datetime | None] = mapped_column(DateTime)
    ended_at:    Mapped[datetime | None] = mapped_column(DateTime)
    created_at:  Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow)


class RequirementCard(Base):
    __tablename__ = "requirement_cards"

    id:               Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, index=True)
    source_type:      Mapped[str]        = mapped_column(String(20), nullable=False)   # "comment" | "bug" | "suggestion" | "topic"
    source_id:        Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_snapshot:  Mapped[dict]       = mapped_column(JSONB, default=dict)
    requirement_text: Mapped[str]        = mapped_column(Text, default="")
    status:           Mapped[str]        = mapped_column(String(20), default="todo")   # todo | in_progress | verifying | done
    ticket_type:      Mapped[str]        = mapped_column(String(20), default="requirement")  # bug | requirement | optimization
    priority:         Mapped[str]        = mapped_column(String(10), default="medium")        # high | medium | low
    created_at:       Mapped[datetime]   = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:       Mapped[datetime]   = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CurationDecision(Base):
    """策划处理决定 + AI 影子预判（统一指向评论/话题/BUG上报任意条目）。

    采纳/不采纳 决定记录、AI 检索式预判、预判命中标记，集中在这张表，
    三个模块复用同一套逻辑。embedding 存这里供相似历史样本检索。
    """
    __tablename__ = "curation_decisions"
    # source_id 全局唯一：评论/话题/BUG上报 UUID 来自不同表，不会碰撞。
    # 同一条 bug 评论在 /comments 与 /bugs 两页都能处理，按 source_id 去重避免双记录。
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_curation_source_id"),
    )

    id:              Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id:         Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, index=True)
    # 'comment' | 'bug' | 'suggestion' | 'topic' | 'bugreport'
    source_type:     Mapped[str]        = mapped_column(String(20), nullable=False, index=True)
    source_id:       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # 'pending' | 'adopted' | 'rejected'
    decision:        Mapped[str]        = mapped_column(String(12), nullable=False, default="pending", index=True)
    decided_by:      Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    decided_at:      Mapped[datetime | None]  = mapped_column(DateTime, nullable=True)
    # AI 影子预判：'adopted' | 'rejected' | None
    ai_prediction:   Mapped[str | None]       = mapped_column(String(12), nullable=True)
    ai_predicted_at: Mapped[datetime | None]  = mapped_column(DateTime, nullable=True)
    # 预判与策划决定是否一致（策划决定时回填，None=无预判可比）
    ai_hit:          Mapped[bool | None]      = mapped_column(Boolean, nullable=True, index=True)
    embedding:       Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    source_snapshot: Mapped[dict]       = mapped_column(JSONB, default=dict)
    created_at:      Mapped[datetime]   = mapped_column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id:      Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, index=True)
    user_id:      Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    display_name: Mapped[str]        = mapped_column(String(255), nullable=False, default="")
    content:      Mapped[str]        = mapped_column(Text, nullable=False)
    created_at:   Mapped[datetime]   = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | failed
    game: Mapped["Game"] = relationship(back_populates="crawl_jobs")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text)
    # 解耦后只剩 crawl 阶段：phase ∈ {"crawl", None}；'ai' 不再使用，AI 由独立 worker 跑。
    # ai_total/ai_done 字段保留但不再写入（前端不再展示 AI 进度条，改在评论列表用 ai_status 角标）。
    phase:    Mapped[str | None] = mapped_column(String(20))
    ai_total: Mapped[int]        = mapped_column(Integer, default=0)
    ai_done:  Mapped[int]        = mapped_column(Integer, default=0)


class BugReport(Base):
    """BUG上报（来自 ZenTao dump.om.dianhun.cn）"""
    __tablename__ = "bug_reports"

    id:           Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id:  Mapped[str]          = mapped_column(String(50), unique=True, index=True)
    title:        Mapped[str]          = mapped_column(String(500), nullable=False)
    description:  Mapped[str | None]   = mapped_column(Text)
    status:       Mapped[str | None]   = mapped_column(String(50), index=True)
    priority:     Mapped[int | None]   = mapped_column(Integer)
    severity:     Mapped[int | None]   = mapped_column(Integer)
    module:       Mapped[str | None]   = mapped_column(String(200))
    submitter:    Mapped[str | None]   = mapped_column(String(100))
    assignee:     Mapped[str | None]   = mapped_column(String(100))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    resolved_at:  Mapped[datetime | None] = mapped_column(DateTime)
    closed_at:    Mapped[datetime | None] = mapped_column(DateTime)
    source_url:   Mapped[str | None]   = mapped_column(String(1024))
    product:      Mapped[str]          = mapped_column(String(50), default="xkbb")
    fetched_at:   Mapped[datetime]     = mapped_column(DateTime, default=datetime.utcnow)
    raw_json:     Mapped[dict | None]  = mapped_column(JSONB)
    # 4 个关联文件的下载链接（同一玩家反馈聚合）
    screenshot_url: Mapped[str | None] = mapped_column(String(1024))   # 截图 .png
    save_url:       Mapped[str | None] = mapped_column(String(1024))   # 存档 PlayerData.bytes
    log_url:        Mapped[str | None] = mapped_column(String(1024))   # 日志 Player.log
    prev_log_url:   Mapped[str | None] = mapped_column(String(1024))   # 前一次日志 Player-prev.log


class GameAnnouncement(Base):
    """游戏更新公告（来自 Steam 社区官方公告 events 接口）。
    中文优先：接口返回中文则直接用；否则翻译原文并标记 is_translated。
    body_zh 存的是已由 BBCode 转好的 HTML 片段，前端直接 v-html 渲染。"""
    __tablename__ = "game_announcements"

    id:            Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id:       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, index=True)
    external_id:   Mapped[str]        = mapped_column(String(50), nullable=False, index=True)  # Steam 顶层 gid
    title:         Mapped[str]        = mapped_column(String(500), nullable=False)             # 原始标题
    title_zh:      Mapped[str]        = mapped_column(String(500), nullable=False, default="") # 中文标题
    body:          Mapped[str | None] = mapped_column(Text)                                     # 原始 BBCode 正文
    body_zh:       Mapped[str | None] = mapped_column(Text)                                     # 转好的中文 HTML 正文
    is_translated: Mapped[bool]       = mapped_column(Boolean, default=False, nullable=False)   # 是否机翻
    lang:          Mapped[str | None] = mapped_column(String(20))                               # 原文语言
    published_at:  Mapped[datetime | None] = mapped_column(DateTime, index=True)
    source_url:    Mapped[str | None] = mapped_column(String(1024))
    fetched_at:    Mapped[datetime]   = mapped_column(DateTime, default=datetime.utcnow)
    raw_json:      Mapped[dict | None] = mapped_column(JSONB)


# ── 阵容物品使用率分析模块（独立于评论业务，无 game_id 外键）─────────────
class LineupSnapshot(Base):
    """玩家阵容快照：每条 = 一个玩家的一份离线大码（去重键=大码内容 sha1）。
    item_counts 预聚合该玩家所有回合的 itemId→出现次数，查询使用率时直接合并，
    避免每次查询都重新解析 protobuf。"""
    __tablename__ = "lineup_snapshots"

    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_hash:    Mapped[str]        = mapped_column(String(40), unique=True, nullable=False, index=True)  # 大码 sha1
    raw_code:     Mapped[str]        = mapped_column(Text, nullable=False)                                  # 大码 base64 原文
    player_name:  Mapped[str | None] = mapped_column(String(255))
    men_pai:      Mapped[int]        = mapped_column(Integer, index=True)      # 门派枚举值 2~11
    rank_level:   Mapped[int]        = mapped_column(Integer, index=True)      # 段位 1~10
    fail_round:   Mapped[int | None] = mapped_column(Integer)                  # 失败回合
    round_count:  Mapped[int]        = mapped_column(Integer, default=0)       # 该局回合数（大码内 rounds 条目数）
    # 该玩家所有回合累计的物品出现次数：{ "itemId(str)": count(int) }
    item_counts:  Mapped[dict]       = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at:  Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)


class LineupFetchJob(Base):
    """一轮拉取任务的状态/进度（仿 CrawlJob，但独立）。"""
    __tablename__ = "lineup_fetch_jobs"

    id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status:      Mapped[str]        = mapped_column(String(20), default="running")  # running | done | failed
    started_at:  Mapped[datetime]   = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    req_total:   Mapped[int]        = mapped_column(Integer, default=0)   # 计划请求数（如 300）
    req_done:    Mapped[int]        = mapped_column(Integer, default=0)   # 已完成请求数
    new_count:   Mapped[int]        = mapped_column(Integer, default=0)   # 本轮新增快照数
    error_msg:   Mapped[str | None] = mapped_column(Text)
    # 触发来源：manual=手动「立即拉取」 / auto=定时任务
    trigger:     Mapped[str]        = mapped_column(String(20), default="auto", index=True)


class LineupScheduleConfig(Base):
    """阵容自动拉取调度配置（单行，id 固定为 1）。"""
    __tablename__ = "lineup_schedule_config"

    id:             Mapped[int]      = mapped_column(Integer, primary_key=True, default=1)
    enabled:        Mapped[bool]     = mapped_column(Boolean, default=True)
    interval_hours: Mapped[int]      = mapped_column(Integer, default=1)
    updated_at:     Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
