from app.ai.router import get_ai_router

_SYSTEM = (
    "You are a translator. Translate the following game community comment into "
    "Simplified Chinese (简体中文). Output ONLY the translated text, no explanation."
)


async def translate_to_chinese(text: str) -> str:
    router = get_ai_router()
    result = await router.chat(_SYSTEM, text, temperature=0.3, max_tokens=500)
    return result.strip()
