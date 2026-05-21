"""
QQ 群消息游戏反馈过滤器（仅处理非 @ 指定 QQ 号的普通消息）

@ 指定 QQ 号的消息已在爬虫层无条件入库，不经过此过滤器。
此处对普通消息使用严格标准：必须包含具体、可操作的游戏反馈才入库。
"""

import logging
from app.ai.router import get_ai_router

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20

_SYSTEM_PROMPT = (
    "You are a strict content filter for a game's QQ group chat.\n"
    "Your job is to identify ONLY messages with substantive, specific game feedback.\n"
    "\n"
    "Output 1 ONLY for messages that meet ALL of the following:\n"
    "- Clearly about THIS game (not general chat or off-topic)\n"
    "- Contains a specific, actionable point: a named bug, a concrete feature suggestion,\n"
    "  a detailed complaint about a specific mechanic, or a substantive gameplay review\n"
    "- At least 2 sentences or 20 Chinese characters of relevant game content\n"
    "\n"
    "Output 0 for everything else, including:\n"
    "- Greetings, reactions, short exclamations (gg, 666, 哈哈, 好的, 收到, 谢谢)\n"
    "- Vague praise or complaints without specifics (\"好玩\", \"太难了\", \"不好玩\", \"游戏不错\")\n"
    "- Questions about how to play, where to buy, or account/technical support\n"
    "- Off-topic content, links, announcements, memes\n"
    "- Messages that MIGHT be game-related but lack enough detail to act on\n"
    "- Single-sentence opinions with no actionable substance\n"
    "\n"
    "Be strict. When in doubt, output 0.\n"
    "Reply with ONLY a comma-separated list of 0s and 1s, one per message, same order. No explanation.\n"
    "Example: 1,0,0,1,0"
)


async def filter_game_feedback(texts: list[str]) -> list[bool]:
    """
    批量判断消息列表中哪些是有价值的游戏反馈。

    Returns:
        与 texts 等长的 bool 列表。True=入库，False=丢弃。
        LLM 出错时保守策略：全部丢弃（@ 消息已在上游保留，普通闲聊误丢无妨）。
    """
    if not texts:
        return []

    router = get_ai_router()
    results: list[bool] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        numbered = "\n".join(f"{j + 1}. {t[:300]}" for j, t in enumerate(batch))

        try:
            resp = await router.chat(
                _SYSTEM_PROMPT,
                numbered,
                temperature=0.1,
                max_tokens=_BATCH_SIZE * 3,
            )
            parts = resp.strip().split(",")
            flags = [p.strip() == "1" for p in parts[: len(batch)]]
            flags += [False] * (len(batch) - len(flags))
            results.extend(flags)
            kept = sum(flags)
            logger.info(
                f"[qq_filter] batch {i // _BATCH_SIZE + 1}: "
                f"{kept}/{len(batch)} 条被识别为游戏反馈"
            )
        except Exception as e:
            logger.warning(f"[qq_filter] LLM 分类失败，丢弃本批: {e}")
            results.extend([False] * len(batch))

    return results
