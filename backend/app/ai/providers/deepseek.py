from openai import AsyncOpenAI
from app.ai.providers.base import BaseProvider
from app.config import get_settings


class DeepSeekProvider(BaseProvider):
    name = "deepseek"

    def __init__(self):
        s = get_settings()
        self.client = AsyncOpenAI(api_key=s.ai_chat_api_key, base_url=s.ai_chat_base_url)
        self.model = s.ai_chat_model

    async def chat(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 1024) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("DeepSeek does not provide embedding. Use QwenProvider instead.")
