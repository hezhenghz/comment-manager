import asyncio
import logging
from datetime import datetime
from app.crawlers.base import BaseCrawler, FetchedComment, make_steam_client

logger = logging.getLogger(__name__)

_REVIEW_API = "https://store.steampowered.com/appreviews/{appid}"

# 每页最大条数（Steam API 上限）
_NUM_PER_PAGE = 100
# 翻页间延迟（秒），避免被 Steam 限速
_PAGE_DELAY = 0.8
# 单次请求最大重试次数
_MAX_RETRIES = 3
# 重试初始等待（秒），指数退避
_RETRY_BASE = 2.0


class SteamStoreCrawler(BaseCrawler):
    platform = "steam_store"

    async def fetch(self, game_app_id: str, since: datetime | None = None, limit: int | None = None) -> list[FetchedComment]:
        """
        全量/增量/试爬抓取 Steam 商店评价。

        - 使用官方 Review JSON API（cursor 翻页），每次最多 100 条。
        - 增量模式：遇到 timestamp_created <= since 时停止翻页。
        - 全量模式：since=None，翻到 cursor 耗尽为止。
        - 试爬模式：limit=N，抓到 N 条后立即停止。
        - external_id = recommendationid，配合 DB 唯一约束彻底防重。
        - 请求失败时指数退避重试（最多 3 次），重试耗尽才终止翻页。
        - 每页之间休眠 0.8 秒，避免被 Steam 限速。
        """
        if not game_app_id:
            logger.warning("SteamStoreCrawler: game_app_id 为空，跳过")
            return []

        comments: list[FetchedComment] = []
        cursor = "*"
        params_base = {
            "json": "1",
            "filter": "recent",      # 按最新排序，保证增量截断可靠
            "language": "all",       # 抓所有语言
            "num_per_page": str(_NUM_PER_PAGE),
            "purchase_type": "all",
        }

        async with make_steam_client(timeout=30) as client:
            while True:
                params = {**params_base, "cursor": cursor}
                url = _REVIEW_API.format(appid=game_app_id)

                # ── 带重试的单页请求 ──────────────────────────────────────
                data = await self._fetch_page(client, url, params)
                if data is None:
                    # 重试耗尽，终止
                    break

                if data.get("success") != 1:
                    logger.error(
                        f"[steam_store] appid={game_app_id} API 返回非成功状态: "
                        f"{data.get('success')}"
                    )
                    break

                reviews = data.get("reviews", [])
                if not reviews:
                    break  # 没有更多数据

                # ── 解析评价 ─────────────────────────────────────────────
                stop_early = False
                for review in reviews:
                    ts_created = review.get("timestamp_created")
                    published_at = (
                        datetime.utcfromtimestamp(ts_created) if ts_created else None
                    )

                    # 增量截断：按时间戳判断，后续只会更旧，直接停止
                    if since and published_at and published_at <= since:
                        stop_early = True
                        break

                    rec_id = str(review.get("recommendationid", ""))
                    author = review.get("author", {})
                    author_steamid = str(author.get("steamid", ""))
                    voted_up = review.get("voted_up")

                    comments.append(FetchedComment(
                        platform="steam_store",
                        source_type="review",
                        external_id=rec_id or None,
                        source_url=(
                            f"https://steamcommunity.com/profiles/{author_steamid}/recommended/{game_app_id}"
                            if author_steamid else None
                        ),
                        author_name=author_steamid or None,
                        content=review.get("review", "").strip(),
                        published_at=published_at,
                        thumbs_up=1 if voted_up is True else (0 if voted_up is False else None),
                        raw_json={
                            "source": "steam_store_review",
                            "recommendationid": rec_id,
                            "voted_up": voted_up,
                            "language": review.get("language"),
                            "votes_up": review.get("votes_up"),
                        },
                    ))

                if stop_early:
                    break

                # 试爬：达到上限后停止
                if limit and len(comments) >= limit:
                    comments = comments[:limit]
                    break

                # cursor 不变或为空 → 已到末尾
                new_cursor = data.get("cursor", "")
                if not new_cursor or new_cursor == cursor:
                    break
                cursor = new_cursor

                # 翻页间延迟，避免触发 Steam 限速
                await asyncio.sleep(_PAGE_DELAY)

        logger.info(
            f"[steam_store] appid={game_app_id} 抓取完成，共 {len(comments)} 条评价"
        )
        return comments

    async def _fetch_page(self, client, url: str, params: dict) -> dict | None:
        """单页请求，失败时指数退避重试，重试耗尽返回 None。"""
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                wait = _RETRY_BASE ** attempt
                logger.warning(
                    f"[steam_store] 请求失败（cursor={params.get('cursor')}，"
                    f"第 {attempt + 1}/{_MAX_RETRIES} 次）: {e}，"
                    f"{'重试中' if attempt < _MAX_RETRIES - 1 else '放弃'}，"
                    f"等待 {wait:.1f}s"
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
        return None

    async def validate(self, game_app_id: str) -> bool:
        if not game_app_id:
            return False
        async with make_steam_client(timeout=10) as client:
            try:
                resp = await client.get(
                    _REVIEW_API.format(appid=game_app_id),
                    params={"json": "1", "num_per_page": "1"},
                )
                return resp.status_code == 200 and resp.json().get("success") == 1
            except Exception:
                return False
