import uuid
from datetime import datetime
from pydantic import BaseModel


# ── Auth ──
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    display_name: str


# ── Game ──
class GameCreate(BaseModel):
    name: str | None = None
    steam_app_id: str | None = None
    icon_url: str | None = None
    discord_channel_ids: list[str] = []
    qq_group_ids: list[str] = []


class GameUpdate(BaseModel):
    name: str | None = None
    steam_app_id: str | None = None
    icon_url: str | None = None
    stopwords: list[str] | None = None
    discord_channel_ids: list[str] | None = None
    discord_channel_names: dict | None = None   # {channel_id: 自定义名称}
    qq_group_ids: list[str] | None = None


class GameOut(BaseModel):
    id: uuid.UUID
    name: str
    steam_app_id: str | None = None
    icon_url: str | None = None
    comment_count: int = 0
    stopwords: list[str] = []
    discord_channel_ids: list[str] = []
    discord_channel_names: dict = {}            # {channel_id: 自定义名称}
    qq_group_ids: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Comment ──
class CommentOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    platform: str
    source_type: str
    source_url: str | None = None
    author_name: str | None = None
    content: str
    content_lang: str | None = None
    published_at: datetime | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    category: str | None = None
    summary: str | None = None
    translation: str | None = None
    is_duplicate: bool = False
    game_name: str | None = None
    # thumbs_up: Steam=0/1(不推荐/推荐), 小黑盒=1-5(星级), 其他来源=None
    thumbs_up: int | None = None
    # BUG 处理状态：None=未处理, accepted=已接受, completed=已完成
    bug_status: str | None = None

    model_config = {"from_attributes": True}


class CommentSearchParams(BaseModel):
    q: str | None = None
    game_id: uuid.UUID | None = None
    platform: str | None = None
    sentiment: str | None = None
    category: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = 1
    page_size: int = 20


class CommentListOut(BaseModel):
    total: int
    items: list[CommentOut]
    page: int
    page_size: int


# ── Dashboard ──
class DashboardStats(BaseModel):
    total_comments: int
    today_new: int
    bug_count: int
    today_bug_count: int
    suggestion_count: int
    today_suggestion_count: int
    topic_count: int = 0
    negative_review_rate: float | None  # None = 无 steam_store 数据


class TrendPoint(BaseModel):
    date: str
    count: int
    health_score: float  # (positive + neutral*0.5) / count * 100, range 0-100


class CategoryDist(BaseModel):
    category: str
    count: int


class SourceDist(BaseModel):
    platform: str
    count: int


class WordCloudItem(BaseModel):
    word: str
    weight: int
    sentiment_score: float = 0.0  # -1 ~ +1: (正面-负面) / 总数


# ── Alert ──
# ── RequirementCard ──
class RequirementCardCreate(BaseModel):
    game_id: uuid.UUID
    source_type: str              # "comment" | "bug" | "suggestion" | "topic"
    source_id: uuid.UUID
    source_snapshot: dict = {}


class RequirementCardUpdate(BaseModel):
    requirement_text: str | None = None
    status: str | None = None     # "todo" | "in_progress" | "done"


class RequirementCardOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    source_snapshot: dict
    requirement_text: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Alert ──
class AlertRuleCreate(BaseModel):
    game_id: uuid.UUID
    rule_type: str = "keyword"       # keyword | threshold
    keywords: list[str] = []
    threshold_value: float | None = None
    channel: str = "in_app"


class AlertRuleUpdate(BaseModel):
    keywords: list[str] | None = None
    threshold_value: float | None = None
    channel: str | None = None
    enabled: bool | None = None


class AlertRuleOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    rule_type: str
    keywords: list[str]
    threshold_value: float | None = None
    channel: str
    enabled: bool
    last_triggered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertEventOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    comment_id: uuid.UUID | None = None
    triggered_at: datetime
    is_read: bool
    # Denormalized for display
    rule_type: str | None = None
    keywords: list[str] | None = None
    threshold_value: float | None = None
    comment_content: str | None = None
    game_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


