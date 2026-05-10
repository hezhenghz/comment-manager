from openai import AsyncOpenAI
from app.ai.providers.base import BaseProvider
from app.config import get_settings


class QwenProvider(BaseProvider):
    name = "qwen"

    def __init__(self):
        s = get_settings()
        self.client = AsyncOpenAI(api_key=s.ai_embedding_api_key, base_url=s.ai_embedding_base_url)
        self.embedding_model = s.ai_embedding_model

    async def chat(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 1024) -> str:
        raise NotImplementedError("Qwen provider is embedding-only. Use DeepSeekProvider for chat.")

    async def embed(self, text: str) -> list[float]:
        resp = await self.client.embeddings.create(model=self.embedding_model, input=text)
        return resp.data[0].embedding
