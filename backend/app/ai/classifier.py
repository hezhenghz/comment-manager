from app.ai.router import get_ai_router

SYSTEM = "Classify this game community comment into exactly one category: bug, suggestion, complaint, praise, other. Reply with only the category word."


async def classify(text: str) -> str:
    router = get_ai_router()
    try:
        result = await router.chat(SYSTEM, text, temperature=0.1, max_tokens=16)
        cat = result.strip().lower()
        valid = {"bug", "suggestion", "complaint", "praise", "other"}
        return cat if cat in valid else "other"
    except Exception:
        lower = text.lower()
        bug_words = ["bug", "crash", "broken", "error", "glitch", "not working", "崩溃", "闪退", "报错", "卡死"]
        suggestion_words = ["suggest", "should", "please add", "wish", "would be nice", "建议", "希望", "能不能"]
        complaint_words = ["trash", "garbage", "sucks", "scam", "refund", "垃圾", "骗钱", "退款", "弃坑"]
        praise_words = ["great", "love", "amazing", "best game", "好玩", "推荐", "好评", "神作"]
        if any(w in lower for w in bug_words):
            return "bug"
        if any(w in lower for w in suggestion_words):
            return "suggestion"
        if any(w in lower for w in complaint_words):
            return "complaint"
        if any(w in lower for w in praise_words):
            return "praise"
        return "other"
