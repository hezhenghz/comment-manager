from app.ai.router import get_ai_router

SYSTEM = "Summarize this game community comment in one short sentence (max 50 words). Output only the summary, no prefix."


async def summarize(text: str) -> str:
    if len(text) <= 200:
        return ""
    router = get_ai_router()
    try:
        return await router.chat(SYSTEM, text, temperature=0.2, max_tokens=80)
    except Exception:
        return text[:200] + ("..." if len(text) > 200 else "")
