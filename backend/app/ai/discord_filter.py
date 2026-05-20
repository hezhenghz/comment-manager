"""
Discord 消息游戏反馈过滤器

对 Discord 频道消息批量判断是否为玩家对游戏的评价/反馈，
只有真正的游戏反馈（评测、bug、建议、投诉、夸赞）才会入库，
闲聊、问候、无关内容会被丢弃。

支持多语言（中文、英文、日文、韩文等），由 LLM 直接判断。
"""

import logging
from app.ai.router import get_ai_router

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20

_SYSTEM_PROMPT = (
    "You are a strict content filter for a game's Discord channel.\n"
    "Keep ONLY messages where a player expresses substantive, specific feedback about the game.\n"
    "\n"
    "Output 1 ONLY for:\n"
    "- Bug reports or technical issues with specific details\n"
    "- Feature suggestions or improvement requests\n"
    "- Specific complaints about mechanics, balance, or design\n"
    "- Meaningful reviews or opinions about gameplay experience\n"
    "\n"
    "Output 0 for everything else:\n"
    "- Greetings, reactions, short exclamations (gg, lol, nice, omg, xd)\n"
    "- Vague one-liners with no substance (\"this game is great\", \"I hate this\")\n"
    "- Questions asking for help or information (\"how do I...\", \"where is...\")\n"
    "- Announcements, links, image-only messages\n"
    "- Casual game chat, strategy discussion, or off-topic content\n"
    "\n"
    "Reply with ONLY a comma-separated list of 0s and 1s, one per message, same order. No explanation.\n"
    "Example: 1,0,0,1,0"
)


async def filter_game_feedback(texts: list[str]) -> list[bool]:
    """
    批量判断消息列表中哪些是游戏反馈。

    Args:
        texts: 消息内容列表

    Returns:
        与 texts 等长的 bool 列表。True=游戏反馈（入库），False=闲聊（丢弃）。
        LLM 出错时保守策略：全部返回 True（宁可多存，不漏重要反馈）。
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
            # LLM 返回条数不足时，默认保留剩余条目
            flags += [True] * (len(batch) - len(flags))
            results.extend(flags)
            kept = sum(flags)
            logger.info(
                f"[discord_filter] batch {i // _BATCH_SIZE + 1}: "
                f"{kept}/{len(batch)} 条被识别为游戏反馈"
            )
        except Exception as e:
            logger.warning(f"[discord_filter] LLM 分类失败，保留全部: {e}")
            results.extend([True] * len(batch))

    return results
