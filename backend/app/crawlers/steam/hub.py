import logging
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from app.crawlers.base import BaseCrawler, FetchedComment

logger = logging.getLogger(__name__)


class SteamHubCrawler(BaseCrawler):
    platform = "steam_hub"

    async def fetch(self, game_app_id: str, since: datetime | None = None) -> list[FetchedComment]:
        """Fetch Steam community hub discussions."""
        comments: list[FetchedComment] = []
        url = f"https://steamcommunity.com/app/{game_app_id}/discussions/"

        async with httpx.AsyncClient(timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }) as client:
            for page in range(5):  # Max 5 pages per run
                page_url = f"{url}?p={page + 1}"
                try:
                    resp = await client.get(page_url)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Failed fetching Steam hub discussions page {page}: {e}")
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                rows = soup.select(".forum_topic")
                if not rows:
                    break

                for row in rows:
                    title_el = row.select_one(".forum_topic_name")
                    author_el = row.select_one(".forum_topic_author")
                    date_el = row.select_one(".forum_topic_date")
                    link_el = row.select_one("a.forum_topic_overlay")

                    title = title_el.get_text(strip=True) if title_el else ""
                    author = author_el.get_text(strip=True) if author_el else None
                    href = link_el["href"] if link_el else None

                    # Fetch the discussion content
                    content = title
                    if href:
                        try:
                            detail_resp = await client.get(href)
                            detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                            op_post = detail_soup.select_one(".forum_op .content")
                            if op_post:
                                content = op_post.get_text(strip=True)
                        except Exception:
                            pass

                    published_at = None
                    if date_el:
                        try:
                            published_at = datetime.strptime(date_el.get_text(strip=True), "%d %B, %Y @ %I:%M%p")
                        except ValueError:
                            pass

                    if since and published_at and published_at <= since:
                        continue

                    comments.append(FetchedComment(
                        platform="steam_hub",
                        source_type="discussion",
                        source_url=href,
                        author_name=author,
                        content=f"{title}\n\n{content}" if content != title else title,
                        published_at=published_at,
                        raw_json={"source": "steam_hub_discussion"},
                    ))

        logger.info(f"Steam hub crawler fetched {len(comments)} comments for app {game_app_id}")
        return comments

    async def validate(self, game_app_id: str) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"https://steamcommunity.com/app/{game_app_id}/discussions/")
                return resp.status_code == 200
            except Exception:
                return False
