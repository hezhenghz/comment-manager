from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass


@dataclass
class FetchedComment:
    platform: str
    source_type: str
    source_url: str | None
    author_name: str | None
    content: str
    published_at: datetime | None
    thumbs_up: int | None = None
    thumbs_down: int | None = None
    raw_json: dict | None = None


class BaseCrawler(ABC):
    platform: str

    @abstractmethod
    async def fetch(self, game_app_id: str, since: datetime | None = None) -> list[FetchedComment]:
        ...

    @abstractmethod
    async def validate(self, game_app_id: str) -> bool:
        ...
