from app.ai.providers.base import BaseProvider
from app.ai.providers.deepseek import DeepSeekProvider
from app.ai.providers.qwen import QwenProvider


class AIRouter:
    def __init__(self):
        self.chat_provider: BaseProvider = DeepSeekProvider()
        self.embed_provider: BaseProvider = QwenProvider()

    async def chat(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 1024) -> str:
        try:
            return await self.chat_provider.chat(system, user, temperature, max_tokens)
        except Exception:
            return ""

    async def embed(self, text: str) -> list[float]:
        try:
            return await self.embed_provider.embed(text)
        except Exception:
            return []


_router: AIRouter | None = None


def get_ai_router() -> AIRouter:
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
