import asyncio
import logging
import re
from datetime import datetime

import httpx

from app.config import get_settings
from app.crawlers.base import BaseCrawler, FetchedComment

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20
_PAGE_DELAY = 0.5
_MAX_EMPTY_STREAK = 2


def _extract_text(message) -> str:
    """从 OneBot message 字段提取纯文本，兼容字符串和 segment 列表两种格式。"""
    if isinstance(message, str):
        return re.sub(r"\[CQ:[^\]]*\]", "", message).strip()
    if isinstance(message, list):
        parts = [seg.get("data", {}).get("text", "") for seg in message if seg.get("type") == "text"]
        return "".join(parts).strip()
    return ""


def _has_at_mention(message, target_ids: set[str]) -> bool:
    """检测消息是否 @ 了 target_ids 中的任意一个 QQ 号。"""
    if not target_ids:
        return False
    if isinstance(message, str):
        return any(f"[CQ:at,qq={uid}]" in message for uid in target_ids)
    if isinstance(message, list):
        at_targets = {str(seg.get("data", {}).get("qq", "")) for seg in message if seg.get("type") == "at"}
        return bool(at_targets & target_ids)
    return False


class QQCrawler(BaseCrawler):
    platform = "qq"

    async def fetch(self, game_app_id: str, since: datetime | None = None, limit: int | None = None) -> list[FetchedComment]:
        settings = get_settings()
        if not settings.qq_napcat_url:
            logger.warning("[qq] 未配置 QQ_NAPCAT_URL，跳过")
            return []

        group_ids = [g.strip() for g in game_app_id.split(",") if g.strip()]
        if not group_ids:
            return []

        target_ids = {uid.strip() for uid in settings.qq_at_always_include.split(",") if uid.strip()}

        headers: dict[str, str] = {}
        if settings.qq_access_token:
            headers["Authorization"] = f"Bearer {settings.qq_access_token}"

        all_raw: list[FetchedComment] = []
        base_url = settings.qq_napcat_url.rstrip("/")

        async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30) as client:
            for gid in group_ids:
                items = await self._fetch_group(client, gid, since, limit, target_ids)
                all_raw.extend(items)
                logger.info(f"[qq] 群 {gid} 原始消息 {len(items)} 条")

        if not all_raw:
            return []

        # 分流：@ 指定 QQ 号的消息直接入库，其余走 AI 过滤
        at_msgs    = [fc for fc in all_raw if (fc.raw_json or {}).get("at_mention")]
        other_msgs = [fc for fc in all_raw if not (fc.raw_json or {}).get("at_mention")]

        from app.ai.qq_filter import filter_game_feedback
        flags = await filter_game_feedback([fc.content for fc in other_msgs])
        filtered = [fc for fc, keep in zip(other_msgs, flags) if keep]

        results = at_msgs + filtered
        logger.info(f"[qq] @提及直接入库 {len(at_msgs)} 条，普通消息过滤保留 {len(filtered)}/{len(other_msgs)} 条")

        return results[:limit] if limit else results

    async def validate(self, game_app_id: str) -> bool:
        settings = get_settings()
        if not settings.qq_napcat_url or not game_app_id:
            return False
        gid = game_app_id.split(",")[0].strip()
        headers: dict[str, str] = {}
        if settings.qq_access_token:
            headers["Authorization"] = f"Bearer {settings.qq_access_token}"
        base_url = settings.qq_napcat_url.rstrip("/")
        try:
            async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10) as client:
                r = await client.post("/get_group_info", json={"group_id": int(gid)})
                data = r.json()
                return data.get("status") == "ok" or data.get("retcode") == 0
        except Exception:
            return False

    async def _fetch_group(self, client: httpx.AsyncClient, group_id: str, since: datetime | None, limit: int | None, target_ids: set[str]) -> list[FetchedComment]:
        collected: list[FetchedComment] = []
        message_seq = 0
        empty_streak = 0
        seen_ids: set[str] = set()

        while True:
            try:
                r = await client.post(
                    "/get_group_msg_history",
                    json={"group_id": int(group_id), "message_seq": message_seq, "count": _PAGE_SIZE},
                )
                data = r.json()
            except Exception as e:
                logger.warning(f"[qq] 群 {group_id} 请求失败: {e}")
                break

            if data.get("status") != "ok" and data.get("retcode") != 0:
                logger.warning(f"[qq] 群 {group_id} 接口错误: {data.get('msg') or data}")
                break

            messages = (data.get("data") or {}).get("messages") or []
            if not messages:
                break

            new_this_page = 0
            stop_early = False

            for msg in messages:
                mid = str(msg.get("message_id", ""))
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)

                ts = msg.get("time", 0)
                published_at = datetime.fromtimestamp(ts) if ts else None

                if since and published_at and published_at <= since:
                    stop_early = True
                    break

                raw_msg = msg.get("message", "")
                content = _extract_text(raw_msg)
                if not content or len(content) < 5:
                    continue

                at_mention = _has_at_mention(raw_msg, target_ids)
                sender = msg.get("sender", {})
                author_name = sender.get("card") or sender.get("nickname") or str(sender.get("user_id", "匿名"))

                collected.append(FetchedComment(
                    platform="qq",
                    source_type="group_message",
                    source_url=None,
                    external_id=mid,
                    author_name=author_name,
                    content=content,
                    published_at=published_at,
                    thumbs_up=None,
                    raw_json={"group_id": group_id, "sender_id": sender.get("user_id"), "at_mention": at_mention},
                ))
                new_this_page += 1

                if limit and len(collected) >= limit:
                    stop_early = True
                    break

            if stop_early:
                break

            if new_this_page == 0:
                empty_streak += 1
                if empty_streak >= _MAX_EMPTY_STREAK:
                    break
            else:
                empty_streak = 0

            last_seq = messages[-1].get("message_seq") or messages[-1].get("message_id")
            if not last_seq or last_seq == message_seq:
                break
            message_seq = last_seq

            await asyncio.sleep(_PAGE_DELAY)

        return collected
