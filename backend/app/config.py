from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# .env 固定在项目根目录（config.py → app/ → backend/ → 项目根）
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


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

    # AI - Chat 备用（OpenAI 兼容格式，Key 留空则不启用）
    ai_chat_backup_api_key: str = ""
    ai_chat_backup_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_chat_backup_model: str = "qwen-turbo"

    # AI - Embedding (Qwen / DashScope)
    ai_embedding_api_key: str = ""
    ai_embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_embedding_model: str = "text-embedding-v3"

    # DingTalk
    dingtalk_webhook_url: str = ""

    # Crawler
    crawler_interval_minutes: int = 120

    # Proxy（用于访问 Steam 等被墙的接口，留空则不使用）
    steam_proxy: str = ""

    # 小黑盒（暂停，详见 docs/xiaoheihe-crawl-research.md）
    xiaoheihe_cookie: str = ""

    # Discord
    discord_bot_token: str = ""

    # QQ (NapCat / LagRange OneBot v11 HTTP API)
    qq_napcat_url: str = ""        # e.g. http://127.0.0.1:3000
    qq_access_token: str = ""      # access_token，留空则不带 Authorization 头
    qq_at_always_include: str = "" # 逗号分隔的 QQ 号，@ 任意一个则无条件入库，例：86114262,10001

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
