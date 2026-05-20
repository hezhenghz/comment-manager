from app.ai.router import get_ai_router

SYSTEM = "Classify this game community comment into exactly one category: bug, suggestion, complaint, praise, other. Reply with only the category word."


async def classify(text: str) -> str:
    router = get_ai_router()
    result = await router.chat(SYSTEM, text, temperature=0.1, max_tokens=10)
    if not result.strip():
        raise ValueError("Empty response from AI")
    cat = result.strip().lower()
    valid = {"bug", "suggestion", "complaint", "praise", "other"}
    return cat if cat in valid else "other"
