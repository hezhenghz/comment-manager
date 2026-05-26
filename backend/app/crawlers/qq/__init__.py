import asyncio
import logging
import re
import unicodedata
from datetime import datetime

import httpx

from app.config import get_settings
from app.crawlers.base import BaseCrawler, FetchedComment

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100
_PAGE_DELAY = 0.5
_MAX_EMPTY_STREAK = 2

# ── 规则过滤（替代原 AI qq_filter）────────────────────────────────────────
_URL_RE = re.compile(r'^https?://\S+$', re.IGNORECASE)


def _is_emoji_only(text: str) -> bool:
    """True 表示文本只有 emoji/标点/空白，不含汉字或字母数字。"""
    for char in text:
        cat = unicodedata.category(char)
        # L=字母, N=数字；CJK 统一汉字（一～鿿）
        if cat.startswith('L') or cat.startswith('N') or '一' <= char <= '鿿':
            return False
    return True


def _rule_filter(content: str) -> bool:
    """True=入库，False=丢弃。纯规则，无 AI。"""
    stripped = content.strip()
    if len(stripped) < 2:
        return False
    if _URL_RE.match(stripped):   # 纯链接
        return False
    if _is_emoji_only(stripped):  # 纯表情包/符号
        return False
    return True


def _extract_text(message) -> str:
    """从 OneBot message 字段提取纯文本，兼容字符串和 segment 列表两种格式。"""
    if isinstance(message, str):
        return re.sub(r"\[CQ:[^\]]*\]", "", message).strip()
    if isinstance(message, list):
        parts = [seg.get("data", {}).get("text", "") for seg in message if seg.get("type") == "text"]
        return "".join(parts).strip()
    return ""


async def _fetch_target_names(
    client: httpx.AsyncClient, group_id: str, target_ids: set[str]
) -> set[str]:
    """查询白名单 QQ 号在指定群的群名片和昵称，用于文本 @名字 匹配。"""
    names: set[str] = set()
    for uid in target_ids:
        try:
            r = await client.post(
                "/get_group_member_info",
                json={"group_id": int(group_id), "user_id": int(uid)},
            )
            info = (r.json().get("data") or {})
            for field in ("card", "nickname"):
                v = info.get(field, "").strip()
                if v:
                    names.add(v)
        except Exception:
            pass  # API 失败时跳过，CQ 码匹配仍生效
    return names


def _has_at_mention(message, target_ids: set[str], target_names: set[str] = frozenset()) -> bool:
    """检测消息是否 @ 了 target_ids 中的任意一个 QQ 号，或在纯文本中提及了对应昵称。"""
    if not target_ids and not target_names:
        return False
    if isinstance(message, str):
        if any(f"[CQ:at,qq={uid}]" in message for uid in target_ids):
            return True
        if target_names:
            text = re.sub(r"\[CQ:[^\]]*\]", "", message)
            return any(f"@{name}" in text for name in target_names)
    if isinstance(message, list):
        at_targets = {str(seg.get("data", {}).get("qq", "")) for seg in message if seg.get("type") == "at"}
        if at_targets & target_ids:
            return True
        if target_names:
            text = "".join(seg.get("data", {}).get("text", "") for seg in message if seg.get("type") == "text")
            return any(f"@{name}" in text for name in target_names)
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

        # 规则过滤（不再调 AI）：丢弃纯链接/纯表情包/过短内容
        results = [fc for fc in all_raw if _rule_filter(fc.content)]
        logger.info(f"[qq] 规则过滤后保留 {len(results)}/{len(all_raw)} 条消息")

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
        target_names = await _fetch_target_names(client, group_id, target_ids)
        if target_names:
            logger.info(f"[qq] 群 {group_id} 白名单昵称: {target_names}")
        else:
            logger.info(f"[qq] 群 {group_id} 未获取到白名单昵称（CQ码匹配仍有效），target_ids={target_ids}")

        collected: list[FetchedComment] = []
        message_seq = 0
        empty_streak = 0
        seen_ids: set[str] = set()
        page_num = 0

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

            # ── 统一排序为降序（最新消息优先）──────────────────────────────────
            # NapCat 不同版本可能返回升序或降序；降序后：
            #   - since 截断可安全 break（后续消息更老）
            #   - messages[-1] 始终是最旧消息，用其 seq 向更早翻页
            messages = sorted(messages, key=lambda m: m.get("time", 0), reverse=True)
            page_num += 1
            ts_newest = messages[0].get("time", 0)
            ts_oldest = messages[-1].get("time", 0)
            logger.info(
                f"[qq] 群 {group_id} 第{page_num}页: {len(messages)}条消息，"
                f"时间 {datetime.fromtimestamp(ts_oldest) if ts_oldest else '?'} ~ "
                f"{datetime.fromtimestamp(ts_newest) if ts_newest else '?'}，"
                f"message_seq={message_seq}"
            )

            new_this_page = 0
            stop_early = False

            for msg in messages:
                mid = str(msg.get("message_id", ""))
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)

                ts = msg.get("time", 0)
                published_at = datetime.fromtimestamp(ts) if ts else None

                # 降序迭代：遇到第一条 <= since 的消息，后续只会更老，安全 break
                if since and published_at and published_at <= since:
                    stop_early = True
                    break

                raw_msg = msg.get("message", "")
                content = _extract_text(raw_msg)
                if not content or len(content) < 2:
                    continue

                at_mention = _has_at_mention(raw_msg, target_ids, target_names)
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

            # messages[-1] 在降序排列后是最旧的消息，用其 seq 向更早翻页
            oldest_msg = messages[-1]
            last_seq = oldest_msg.get("message_seq") or oldest_msg.get("message_id")
            if not last_seq or last_seq == message_seq:
                logger.info(f"[qq] 群 {group_id} 翻页终止: last_seq={last_seq}, message_seq={message_seq}")
                break
            message_seq = last_seq

            await asyncio.sleep(_PAGE_DELAY)

        logger.info(f"[qq] 群 {group_id} 共抓取 {len(collected)} 条原始消息（{page_num}页）")
        return collected
