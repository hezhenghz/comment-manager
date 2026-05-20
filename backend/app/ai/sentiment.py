from app.ai.router import get_ai_router

SYSTEM = "Classify the sentiment of this game community comment. Reply with exactly one word: positive, negative, or neutral. Then a confidence score 0-1."


async def analyze_sentiment(text: str) -> tuple[str, float]:
    router = get_ai_router()
    result = await router.chat(SYSTEM, text, temperature=0.1, max_tokens=10)
    if not result.strip():
        raise ValueError("Empty response from AI")
    parts = result.strip().split()
    label = parts[0].lower() if parts else "neutral"
    score = float(parts[1]) if len(parts) > 1 else 0.5
    if label not in ("positive", "negative", "neutral"):
        label = "neutral"
    return label, score
