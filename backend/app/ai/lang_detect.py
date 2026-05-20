from app.ai.router import get_ai_router

_SYSTEM = (
    "Identify the language of the following text.\n"
    "Reply with ONLY one language code:\n"
    "  zh-cn  (Simplified Chinese)\n"
    "  zh-tw  (Traditional Chinese)\n"
    "  en     (English)\n"
    "  ja     (Japanese)\n"
    "  ko     (Korean)\n"
    "If none of the above match, reply with the BCP-47 code (e.g. fr, de, ru).\n"
    "Reply with the code only, no explanation."
)

_NORMALIZE = {
    "chinese": "zh-cn", "mandarin": "zh-cn",
    "simplified chinese": "zh-cn", "simplified": "zh-cn",
    "traditional chinese": "zh-tw", "traditional": "zh-tw",
    "english": "en", "japanese": "ja", "korean": "ko",
}


async def detect_lang(text: str) -> str:
    router = get_ai_router()
    result = await router.chat(_SYSTEM, text[:500], temperature=0.1, max_tokens=10)
    if not result.strip():
        raise ValueError("Empty response from AI")
    code = result.strip().lower()
    return _NORMALIZE.get(code, code) or "unknown"
