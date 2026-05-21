from app.crawlers.base import BaseCrawler
from app.crawlers.steam.store import SteamStoreCrawler
from app.crawlers.steam.hub import SteamHubCrawler
from app.crawlers.xiaoheihe import XiaoheiheCrawler
from app.crawlers.discord import DiscordCrawler
from app.crawlers.qq import QQCrawler

_registry: dict[str, type[BaseCrawler]] = {
    "steam_store": SteamStoreCrawler,
    "steam_hub": SteamHubCrawler,
    "xiaoheihe": XiaoheiheCrawler,
    "discord": DiscordCrawler,
    "qq": QQCrawler,
}


def get_crawler(platform: str) -> BaseCrawler | None:
    cls = _registry.get(platform)
    return cls() if cls else None


def available_platforms() -> list[str]:
    return list(_registry.keys())


def register_crawler(name: str, crawler_cls: type[BaseCrawler]) -> None:
    _registry[name] = crawler_cls
