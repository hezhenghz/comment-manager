from app.ai.router import get_ai_router
from app.ai.categories import CATEGORIES, CATEGORY_GUIDE_ZH

SYSTEM = (
    "你是游戏社区评论分类助手。把下面这条评论分到且仅分到一个类别。\n\n"
    + CATEGORY_GUIDE_ZH
    + "\n\n只回复类别英文单词本身（bug / suggestion / complaint / praise / other），不要解释。"
)


async def classify(text: str) -> str:
    router = get_ai_router()
    result = await router.chat(SYSTEM, text, temperature=0.1, max_tokens=10)
    if not result.strip():
        raise ValueError("Empty response from AI")
    cat = result.strip().lower()
    return cat if cat in CATEGORIES else "other"
