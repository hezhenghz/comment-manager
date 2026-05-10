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
    name: str
    steam_app_id: str | None = None
    icon_url: str | None = None


class GameUpdate(BaseModel):
    name: str | None = None
    steam_app_id: str | None = None
    icon_url: str | None = None


class GameOut(BaseModel):
    id: uuid.UUID
    name: str
    steam_app_id: str | None = None
    icon_url: str | None = None
    comment_count: int = 0
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
    is_duplicate: bool = False
    game_name: str | None = None

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
    negative_ratio: float


class TrendPoint(BaseModel):
    date: str
    count: int
    positive: int
    negative: int
    neutral: int


class CategoryDist(BaseModel):
    category: str
    count: int


class SourceDist(BaseModel):
    platform: str
    count: int


class WordCloudItem(BaseModel):
    word: str
    weight: int


# ── Alert ──
class AlertRuleCreate(BaseModel):
    game_id: uuid.UUID
    keywords: list[str]
    channel: str = "in_app"


class AlertRuleUpdate(BaseModel):
    keywords: list[str] | None = None
    channel: str | None = None
    enabled: bool | None = None


class AlertRuleOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    keywords: list[str]
    channel: str
    enabled: bool
    last_triggered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Report ──
class ReportTaskCreate(BaseModel):
    game_id: uuid.UUID
    type: str
    date_from: str | None = None
    date_to: str | None = None
    schedule: str | None = None


class ReportTaskOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    type: str
    date_range: str | None = None
    schedule: str | None = None
    status: str
    file_path: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
