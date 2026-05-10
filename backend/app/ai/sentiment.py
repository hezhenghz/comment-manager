from app.ai.router import get_ai_router

SYSTEM = "Classify the sentiment of this game community comment. Reply with exactly one word: positive, negative, or neutral. Then a confidence score 0-1."


async def analyze_sentiment(text: str) -> tuple[str, float]:
    router = get_ai_router()
    try:
        result = await router.chat(SYSTEM, text, temperature=0.1, max_tokens=16)
        parts = result.strip().split()
        label = parts[0].lower() if parts else "neutral"
        score = float(parts[1]) if len(parts) > 1 else 0.5
        if label not in ("positive", "negative", "neutral"):
            label = "neutral"
        return label, score
    except Exception:
        # Rule-based fallback
        neg_words = ["crash", "broken", "bug", "sucks", "terrible", "awful", "trash", "unplayable", "崩溃", "烂", "垃圾", "不行"]
        pos_words = ["great", "amazing", "love", "best", "awesome", "perfect", "好评", "好玩", "推荐", "牛逼"]
        lower = text.lower()
        if any(w in lower for w in neg_words):
            return ("negative", 0.6)
        if any(w in lower for w in pos_words):
            return ("positive", 0.6)
        return ("neutral", 0.5)
