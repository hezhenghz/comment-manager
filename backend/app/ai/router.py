import logging
import time
from app.ai.providers.deepseek import DeepSeekProvider
from app.config import get_settings

logger = logging.getLogger(__name__)

_FAILURE_THRESHOLD = 3    # 连续失败几次后熔断
_COOLDOWN_SECONDS  = 120  # 熔断后暂停多少秒


class AIRouter:
    def __init__(self):
        s = get_settings()
        self.chat_primary = DeepSeekProvider(timeout=10.0)
        self.chat_backup = (
            DeepSeekProvider(
                api_key=s.ai_chat_backup_api_key,
                base_url=s.ai_chat_backup_base_url,
                model=s.ai_chat_backup_model,
                timeout=25.0,
            )
            if s.ai_chat_backup_api_key
            else None
        )
        self._primary_failures = 0
        self._primary_disabled_until = 0.0

    async def chat(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 1024) -> str:
        now = time.monotonic()

        if now > self._primary_disabled_until:
            try:
                result = await self.chat_primary.chat(system, user, temperature, max_tokens)
                if not result.strip():
                    raise ValueError("Empty response from primary")
                if self._primary_failures:
                    logger.info("AI chat primary recovered")
                    self._primary_failures = 0
                return result
            except Exception as e:
                self._primary_failures += 1
                if self._primary_failures >= _FAILURE_THRESHOLD:
                    self._primary_disabled_until = now + _COOLDOWN_SECONDS
                    logger.warning(
                        f"AI chat primary circuit open after {self._primary_failures} failures "
                        f"(paused {_COOLDOWN_SECONDS}s): {e}"
                    )
                else:
                    logger.warning(f"AI chat primary failed ({self._primary_failures}/{_FAILURE_THRESHOLD}): {e}")
        else:
            remaining = int(self._primary_disabled_until - now)
            logger.debug(f"AI chat primary in cooldown ({remaining}s left), using backup")

        if self.chat_backup:
            # deepseek-v4-flash is a reasoning model: <think> blocks consume tokens
            # before visible output, so enforce a minimum to avoid empty responses
            backup_max_tokens = max(max_tokens, 500)
            try:
                result = await self.chat_backup.chat(system, user, temperature, backup_max_tokens)
                if not result.strip():
                    raise ValueError("Empty response from backup")
                return result
            except Exception as e:
                logger.error(f"AI chat backup failed: {e}")

        raise RuntimeError("All AI chat providers failed")


_router: AIRouter | None = None


def get_ai_router() -> AIRouter:
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
