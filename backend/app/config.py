from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://comment_manager:comment_manager@localhost:5432/comment_manager"
    database_url_sync: str = "postgresql://comment_manager:comment_manager@localhost:5432/comment_manager"

    # JWT
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # AI - Chat (DeepSeek)
    ai_chat_api_key: str = ""
    ai_chat_base_url: str = "https://api.deepseek.com"
    ai_chat_model: str = "deepseek-v4-flash"

    # AI - Embedding (Qwen / DashScope)
    ai_embedding_api_key: str = ""
    ai_embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_embedding_model: str = "text-embedding-v3"

    # DingTalk
    dingtalk_webhook_url: str = ""

    # Crawler
    crawler_interval_minutes: int = 120

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
