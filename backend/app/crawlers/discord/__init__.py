import asyncio
import logging
from datetime import datetime

import httpx

from app.config import get_settings
from app.crawlers.base import BaseCrawler, FetchedComment

logger = logging.getLogger(__name__)

_API_BASE = "https://discord.com/api/v10"
_PAGE_SIZE = 100
_PAGE_DELAY = 0.5
_MAX_RETRIES = 3
_RETRY_BASE = 2.0
_DISCORD_EPOCH_MS = 1420070400000
_ALLOWED_MSG_TYPES = {0, 19}


def _dt_to_snowflake(dt: datetime) -> str:
    ms = int(dt.timestamp() * 1000)
    return str((ms - _DISCORD_EPOCH_MS) << 22)


class DiscordCrawler(BaseCrawler):
    platform = "discord"

    async def fetch(self, game_app_id, since=None, limit=None):
        token = get_settings().discord_bot_token
        if not token:
            logger.warning("[discord] 未配置 DISCORD_BOT_TOKEN")
            return []
        channel_ids = [c.strip() for c in game_app_id.split(",") if c.strip()]
        if not channel_ids:
            return []
        headers = {
            "Authorization": f"Bot {token}",
            "User-Agent": "DiscordBot (comment-manager, 1.0)",
        }
        all_raw = []
        async with httpx.AsyncClient(base_url=_API_BASE, headers=headers, timeout=30) as client:
            for cid in channel_ids:
                gid = await self._get_guild_id(client, cid)
                raw = await self._fetch_channel(client, cid, gid, since, limit)
                all_raw.extend(raw)
                logger.info(f"[discord] 频道 {cid} 原始消息 {len(raw)} 条")
        candidates = [self._parse_message(m, c, g) for m, c, g in all_raw]
        candidates = [fc for fc in candidates if fc is not None]
        if not candidates:
            return []
        from app.ai.discord_filter import filter_game_feedback
        flags = await filter_game_feedback([fc.content for fc in candidates])
        results = [fc for fc, keep in zip(candidates, flags) if keep]
        logger.info(f"[discord] AI 过滤保留 {len(results)}/{len(candidates)} 条")
        return results[:limit] if limit else results

    async def validate(self, game_app_id):
        token = get_settings().discord_bot_token
        if not token or not game_app_id:
            return False
        cid = game_app_id.split(",")[0].strip()
        headers = {"Authorization": f"Bot {token}", "User-Agent": "DiscordBot (comment-manager, 1.0)"}
        async with httpx.AsyncClient(base_url=_API_BASE, headers=headers, timeout=10) as client:
            try:
                return (await client.get(f"/channels/{cid}")).status_code == 200
            except Exception:
                return False

    async def _get_guild_id(self, client, channel_id):
        try:
            r = await client.get(f"/channels/{channel_id}")
            if r.status_code == 200:
                return r.json().get("guild_id")
        except Exception as e:
            logger.warning(f"[discord] 获取频道 {channel_id} 信息失败: {e}")
        return None

    async def _fetch_channel(self, client, channel_id, guild_id, since, limit):
        if since:
            return await self._fetch_after(client, channel_id, guild_id, _dt_to_snowflake(since), limit)
        return await self._fetch_all(client, channel_id, guild_id, limit)

    async def _fetch_all(self, client, channel_id, guild_id, limit):
        collected, before = [], None
        while True:
            params = {"limit": _PAGE_SIZE}
            if before:
                params["before"] = before
            batch = await self._request(client, f"/channels/{channel_id}/messages", params)
            if not batch:
                break
            collected.extend((m, channel_id, guild_id) for m in batch)
            if len(batch) < _PAGE_SIZE or (limit and len(collected) >= limit):
                break
            before = batch[-1]["id"]
            await asyncio.sleep(_PAGE_DELAY)
        return collected

    async def _fetch_after(self, client, channel_id, guild_id, after_snowflake, limit):
        collected, after = [], after_snowflake
        while True:
            batch = await self._request(client, f"/channels/{channel_id}/messages", {"limit": _PAGE_SIZE, "after": after})
            if not batch:
                break
            collected.extend((m, channel_id, guild_id) for m in batch)
            if len(batch) < _PAGE_SIZE or (limit and len(collected) >= limit):
                break
            after = batch[-1]["id"]
            await asyncio.sleep(_PAGE_DELAY)
        return collected

    async def _request(self, client, path, params):
        for attempt in range(_MAX_RETRIES):
            try:
                r = await client.get(path, params=params)
                if r.status_code == 429:
                    await asyncio.sleep(float(r.headers.get("Retry-After", "1")))
                    continue
                if r.status_code in (403, 404):
                    logger.warning(f"[discord] {path} {r.status_code}，跳过")
                    return []
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError:
                raise
            except Exception as e:
                wait = _RETRY_BASE ** attempt
                logger.warning(f"[discord] 请求失败({attempt+1}/{_MAX_RETRIES}): {e}，等待{wait:.1f}s")
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
        return None

    def _parse_message(self, msg, channel_id, guild_id):
        author = msg.get("author", {})
        if author.get("bot") or msg.get("type", 0) not in _ALLOWED_MSG_TYPES:
            return None
        content = (msg.get("content") or "").strip()
        if not content:
            return None
        msg_id = msg["id"]
        published_at = None
        ts = msg.get("timestamp", "")
        if ts:
            try:
                published_at = datetime.fromisoformat(ts).replace(tzinfo=None)
            except ValueError:
                pass
        author_name = author.get("global_name") or author.get("username") or "匿名"
        source_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{msg_id}" if guild_id else None
        total_reactions = sum(r.get("count", 0) for r in msg.get("reactions", [])) or None
        ref_msg = msg.get("referenced_message") or {}
        return FetchedComment(
            platform="discord", source_type="message", external_id=msg_id,
            source_url=source_url, author_name=author_name, content=content,
            published_at=published_at, thumbs_up=total_reactions,
            raw_json={"channel_id": channel_id, "guild_id": guild_id,
                      "type": msg.get("type", 0), "referenced_message_id": ref_msg.get("id")},
        )