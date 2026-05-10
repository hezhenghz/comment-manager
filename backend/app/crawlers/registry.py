from app.crawlers.base import BaseCrawler
from app.crawlers.steam.store import SteamStoreCrawler
from app.crawlers.steam.hub import SteamHubCrawler

_registry: dict[str, type[BaseCrawler]] = {
    "steam_store": SteamStoreCrawler,
    "steam_hub": SteamHubCrawler,
    # "discord": DiscordCrawler,   # reserved
    # "qq": QQCrawler,             # reserved
    # "xiaoheihe": XiaoheiheCrawler, # reserved
}


def get_crawler(platform: str) -> BaseCrawler | None:
    cls = _registry.get(platform)
    return cls() if cls else None


def available_platforms() -> list[str]:
    return list(_registry.keys())


def register_crawler(name: str, crawler_cls: type[BaseCrawler]) -> None:
    _registry[name] = crawler_cls
