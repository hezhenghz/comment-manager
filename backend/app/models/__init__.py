import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Boolean, Integer, DateTime, ForeignKey, Text as SAText
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
    # 两阶段进度
    phase:    Mapped[str | None] = mapped_column(String(20))        # "crawl" | "ai" | None
    ai_total: Mapped[int]        = mapped_column(Integer, default=0) # Phase2 需处理总数
    ai_done:  Mapped[int]        = mapped_column(Integer, default=0) # Phase2 已完成数
