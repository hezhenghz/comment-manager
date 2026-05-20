import asyncio
import logging
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from app.crawlers.base import BaseCrawler, FetchedComment, make_steam_client

logger = logging.getLogger(__name__)

# 最多抓 20 页
_MAX_PAGES = 20
# 翻页间延迟（秒）
_PAGE_DELAY = 1.0
# 详情页请求延迟（秒）
_DETAIL_DELAY = 1.5
# 重试次数
_MAX_RETRIES = 3
# 重试退避基数（秒）
_RETRY_BASE = 2.0

# 从帖子 URL 提取 thread_id 的正则
# URL 格式：.../discussions/{subforum_id}/{thread_id}/
_THREAD_ID_RE = re.compile(r"/discussions/\d+/(\d+)/?")


class SteamHubCrawler(BaseCrawler):
    platform = "steam_hub"

    async def fetch(self, game_app_id: str, since: datetime | None = None, limit: int | None = None) -> list[FetchedComment]:
        """
        全量/增量抓取 Steam 社区讨论版帖子（楼主原帖）。

        修复点：
        1. 分页参数改为 fp=N*15（每页 15 帖，步长必须是 15）
        2. 客户端开启 follow_redirects=True，避免 302 导致异常
        3. 从帖子 URL 提取 thread_id 作为 external_id，防止重复
        4. 请求失败时指数退避重试（最多 3 次）
        5. 跳过空 game_app_id
        """
        if not game_app_id:
            logger.warning("[steam_hub] game_app_id 为空，跳过")
            return []

        comments: list[FetchedComment] = []
        base_url = f"https://steamcommunity.com/app/{game_app_id}/discussions/"

        # follow_redirects=True：Steam 社区偶尔 302 跳转，必须跟随
        async with make_steam_client(timeout=30, follow_redirects=True) as client:
            for fp in range(1, _MAX_PAGES + 1):
                # fp=1 → 首页（不带参数），fp=2 → 第2页，fp=3 → 第3页，…
                page_url = f"{base_url}?fp={fp}" if fp > 1 else base_url

                html = await self._fetch_html(client, page_url, f"列表页 fp={fp}")
                if html is None:
                    break  # 重试耗尽，终止

                soup = BeautifulSoup(html, "lxml")
                rows = soup.select(".forum_topic")
                if not rows:
                    logger.info(f"[steam_hub] fp={fp} 无更多帖子，结束翻页")
                    break

                page_has_new = False
                for row in rows:
                    title_el = row.select_one(".forum_topic_name")
                    author_el = row.select_one(".forum_topic_op")
                    link_el = row.select_one("a.forum_topic_overlay")

                    title = title_el.get_text(strip=True) if title_el else ""
                    author = author_el.get_text(strip=True) if author_el else None
                    href = link_el["href"] if link_el and link_el.get("href") else None

                    # 优先用帖子创建时间，其次用最后回复时间
                    published_at = self._parse_timestamp(
                        row.select_one(".forum_topic_firstpost[data-timestamp]")
                        or row.select_one(".forum_topic_lastpost[data-timestamp]")
                    )

                    # 增量截断
                    if since and published_at and published_at <= since:
                        continue  # 跳过旧帖，不 break，因为列表不保证严格时间排序

                    # 从 URL 提取 thread_id 作为 external_id
                    external_id = None
                    if href:
                        m = _THREAD_ID_RE.search(href)
                        if m:
                            external_id = m.group(1)

                    # 拉取帖子正文
                    content = title
                    if href:
                        detail_html = await self._fetch_html(
                            client, href, f"详情页 {external_id or href}"
                        )
                        if detail_html:
                            detail_soup = BeautifulSoup(detail_html, "lxml")
                            op_post = detail_soup.select_one(".forum_op .content")
                            if op_post:
                                content = op_post.get_text(strip=True)
                        await asyncio.sleep(_DETAIL_DELAY)

                    if not content.strip():
                        continue

                    if limit and len(comments) >= limit:
                        break

                    comments.append(FetchedComment(
                        platform="steam_hub",
                        source_type="discussion",
                        external_id=external_id,
                        source_url=href,
                        author_name=author,
                        content=f"{title}\n\n{content}" if content != title else title,
                        published_at=published_at,
                        raw_json={"source": "steam_hub_discussion", "title": title},
                    ))
                    page_has_new = True

                # 试爬：达到上限后停止翻页
                if limit and len(comments) >= limit:
                    break

                # 整页都是旧帖，可以停止翻页
                if since and not page_has_new and fp > 1:
                    logger.info(f"[steam_hub] fp={fp} 整页均为旧帖，停止翻页")
                    break

                if fp < _MAX_PAGES:
                    await asyncio.sleep(_PAGE_DELAY)

        logger.info(f"[steam_hub] appid={game_app_id} 抓取完成，共 {len(comments)} 个帖子")
        return comments

    async def _fetch_html(self, client, url: str, label: str) -> str | None:
        """带指数退避重试的 HTML 获取，失败超限返回 None。"""
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                wait = _RETRY_BASE ** attempt
                logger.warning(
                    f"[steam_hub] {label} 请求失败（第 {attempt + 1}/{_MAX_RETRIES} 次）: {e}，"
                    f"{'重试' if attempt < _MAX_RETRIES - 1 else '放弃'}，等待 {wait:.1f}s"
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
        return None

    @staticmethod
    def _parse_timestamp(el) -> datetime | None:
        """从 data-timestamp 属性解析 UTC datetime。"""
        if el is None:
            return None
        ts_str = el.get("data-timestamp")
        if not ts_str:
            return None
        try:
            return datetime.fromtimestamp(int(ts_str), tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OSError):
            return None

    async def validate(self, game_app_id: str) -> bool:
        if not game_app_id:
            return False
        async with make_steam_client(timeout=10, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    f"https://steamcommunity.com/app/{game_app_id}/discussions/"
                )
                return resp.status_code == 200
            except Exception:
                return False
