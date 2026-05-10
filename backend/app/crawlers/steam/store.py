import logging
from datetime import datetime
from typing import List
import httpx
from bs4 import BeautifulSoup
from app.crawlers.base import BaseCrawler, FetchedComment

logger = logging.getLogger(__name__)


class SteamStoreCrawler(BaseCrawler):
    platform = "steam_store"

    async def fetch(self, game_app_id: str, since: datetime | None = None) -> list[FetchedComment]:
        """Fetch Steam store reviews. Uses the public review page (HTML scraping)."""
        comments: list[FetchedComment] = []
        cursor = "*"
        page = 0

        async with httpx.AsyncClient(timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }) as client:
            while page < 10:  # Max 10 pages per run
                url = f"https://steamcommunity.com/app/{game_app_id}/reviews/?browsefilter=mostrecent&p={page + 1}"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Failed fetching Steam store reviews page {page}: {e}")
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select(".apphub_Card")
                if not cards:
                    break

                for card in cards:
                    content_el = card.select_one(".apphub_CardTextContent")
                    if not content_el:
                        continue
                    content = content_el.get_text(strip=True)
                    # Skip the "Posted: ..." prefix text from steam
                    if "\n" in content:
                        content = content.split("\n", 1)[-1].strip()

                    date_el = card.select_one(".date_posted")
                    author_el = card.select_one(".apphub_CardContentAuthorName a")
                    thumbs_up_el = card.select_one(".title")
                    source_el = card.select_one("a.apphub_CardContentMoreLink")

                    published_at = None
                    if date_el:
                        try:
                            published_at = datetime.strptime(date_el.get_text(strip=True), "%d %B, %Y")
                        except ValueError:
                            pass

                    if since and published_at and published_at <= since:
                        page = 999  # stop
                        break

                    comments.append(FetchedComment(
                        platform="steam_store",
                        source_type="review",
                        source_url=source_el["href"] if source_el else None,
                        author_name=author_el.get_text(strip=True) if author_el else None,
                        content=content,
                        published_at=published_at,
                        raw_json={"source": "steam_store_review"},
                    ))

                page += 1

        logger.info(f"Steam store crawler fetched {len(comments)} comments for app {game_app_id}")
        return comments

    async def validate(self, game_app_id: str) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"https://store.steampowered.com/app/{game_app_id}/")
                return resp.status_code == 200
            except Exception:
                return False
