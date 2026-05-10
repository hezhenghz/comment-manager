from abc import ABC, abstractmethod


class BaseProvider(ABC):
    name: str

    @abstractmethod
    async def chat(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 1024) -> str:
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...
