from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from dataclasses import dataclass
import httpx


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


@asynccontextmanager
async def make_steam_client(timeout: int = 30, follow_redirects: bool = False):
    """统一创建带代理的 httpx 客户端（读取 settings.steam_proxy）。"""
    from app.config import get_settings
    proxy = get_settings().steam_proxy or None
    kwargs: dict = {
        "timeout": timeout,
        "headers": _HEADERS,
        "follow_redirects": follow_redirects,
    }
    if proxy:
        kwargs["proxy"] = proxy
    async with httpx.AsyncClient(**kwargs) as client:
        yield client


@dataclass
class FetchedComment:
    platform: str
    source_type: str
    source_url: str | None
    author_name: str | None
    content: str
    published_at: datetime | None
    external_id: str | None = None   # 平台侧唯一 ID（steam_store: recommendationid）
    thumbs_up: int | None = None
    thumbs_down: int | None = None
    raw_json: dict | None = None


class BaseCrawler(ABC):
    platform: str

    @abstractmethod
    async def fetch(self, game_app_id: str, since: datetime | None = None, limit: int | None = None) -> list[FetchedComment]:
        ...

    @abstractmethod
    async def validate(self, game_app_id: str) -> bool:
        ...
