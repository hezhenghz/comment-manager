from app.ai.router import get_ai_router


async def generate_embedding(text: str) -> list[float]:
    router = get_ai_router()
    return await router.embed(text)
