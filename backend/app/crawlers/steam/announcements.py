"""Steam 官方更新公告抓取器。

数据源：商店活动分页接口（allnews 页面背后的接口），加 l=schinese 时
若开发者发布了中文版公告会直接返回中文标题与正文。

只保留「更新公告」：event_type==12 且标题命中更新类关键词，
过滤掉活动 / 上新 / 促销等其他类型。
"""
import logging
from datetime import datetime

from app.crawlers.base import make_steam_client

logger = logging.getLogger(__name__)

_EVENTS_API = "https://store.steampowered.com/events/ajaxgetpartnereventspageable/"
# 单次抓取条数（接口单页），足够覆盖增量
_COUNT = 50
# 更新公告的 event_type
# 促销类事件（type=28 为打折促销），不属于更新公告，直接排除
_SALE_EVENT_TYPE = 28
# 标题命中以下任一关键词才视为「更新公告」（大小写不敏感）。
# 注意：不同游戏的 event_type 不统一（12/13/14 都可能是更新），
# 因此以标题关键词为主判定，只排除明确的促销类型。
_UPDATE_KEYWORDS = (
    "更新", "更新说明", "更新公告", "更新日志", "版本", "补丁", "修复",
    "维护", "平衡", "bug",
    "update", "patch", "hotfix", "version", "changelog", "fix", "ver.",
)


def _is_update_announcement(event_type: int, title: str) -> bool:
    if event_type == _SALE_EVENT_TYPE:
        return False
    t = (title or "").lower()
    return any(kw.lower() in t for kw in _UPDATE_KEYWORDS)


def _build_source_url(appid: str, gid: str) -> str:
    return f"https://store.steampowered.com/news/app/{appid}/view/{gid}?l=schinese"


async def fetch_announcements(appid: str) -> list[dict]:
    """抓取单个游戏的官方更新公告，返回标准化 dict 列表（已过滤非更新类）。"""
    if not appid:
        return []

    params = {
        "clan_accountid": "0",
        "appid": appid,
        "offset": "0",
        "count": str(_COUNT),
        "l": "schinese",
    }

    async with make_steam_client(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(_EVENTS_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[announcements] appid={appid} 抓取失败: {e}")
            return []

    results: list[dict] = []
    for ev in data.get("events", []):
        event_type = ev.get("event_type")
        gid = str(ev.get("gid") or "")
        body_obj = ev.get("announcement_body") or {}
        title = ev.get("event_name") or body_obj.get("headline") or ""

        if not gid or not _is_update_announcement(event_type, title):
            continue

        posttime = body_obj.get("posttime") or ev.get("rtime32_start_time")
        published_at = (
            datetime.utcfromtimestamp(int(posttime)) if posttime else None
        )

        results.append({
            "external_id": gid,
            "title": title,
            "body": body_obj.get("body") or "",
            "language": body_obj.get("language"),
            "published_at": published_at,
            "source_url": _build_source_url(appid, gid),
        })

    logger.info(f"[announcements] appid={appid} 命中更新公告 {len(results)} 条")
    return results
