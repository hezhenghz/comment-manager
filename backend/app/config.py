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
    # 并发锁 TTL（秒）：_running 字典里超过该时间的锁视为残留自动释放。
    # 解耦后 crawl 阶段不会再被 AI 拖死，正常 crawl 几秒~几分钟内完成；
    # TTL 用于兜底真·crawl 卡死（如 Discord API 挂、网络断），防止前端永远点不动按钮。
    crawler_lock_ttl_seconds: int = 1800

    # AI Worker（解耦后的独立后台任务）
    ai_worker_interval_minutes: int = 5          # APScheduler 触发间隔
    ai_worker_batch_size: int = 50               # 单次最多处理多少条 pending
    ai_max_retries: int = 3                      # 超过即标 ai_status='failed'
    ai_retry_backoff_base_seconds: int = 300     # 指数退避基数：300 → 600 → 1200

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

    # ZenTao BUG上报（dump.om.dianhun.cn）
    zentao_url:           str = "http://dump.om.dianhun.cn"
    zentao_username:      str = ""
    zentao_password:      str = ""
    zentao_product_id:    str = ""
    zentao_cookie:        str = ""
    zentao_sync_interval: int = 60   # 同步间隔（分钟）

    # BUG上报 异地推送端点的鉴权 Token
    # 若设置，则启用 POST /api/bugreports/_push（接收外部爬虫推送）
    # 远程主机：设置此 Token 用于鉴权；本地爬虫：用同一 Token 推送
    bug_push_token:       str = ""

    # 本地推送服务的 HTTP 触发地址（异地架构下，远程后端用它转发"手动同步"请求）
    # 例：http://192.168.216.45:9000
    # 留空 → 手动同步走本机 ZenTao 凭据（单机架构）
    local_pusher_url:     str = ""

    # ── 阵容物品使用率分析模块 ──────────────────────────────────────────
    lineup_api_base: str = "https://gateway-client.17m3.com/NHSmV"  # 离线玩家数据接口
    lineup_uniq_id: str = "87fc14b1"        # 接口固定标识（写死在游戏里）
    lineup_area_id: str = "1001"            # 区服 ID
    lineup_count: int = 50                  # 单次请求条数（接口上限 50）
    lineup_interval_hours: int = 1          # 定时拉取间隔（小时）
    lineup_retention_days: int = 7          # 快照保留天数：last_seen_at 超过此天数即清理
    lineup_request_delay_ms: int = 200      # 每次请求之间的节流延时（毫秒）
    # ItemCfg.bytes 路径（itemId→NameKey/职业物品标志/价格的数据源）
    lineup_itemcfg_path: str = r"F:\xiake2\trunk\Client\XiaKe2_U3DProj\Assets\PackRes\TableData\ItemCfg.bytes"
    # LocalizeTable.bytes 路径（NameKey→中文名）
    lineup_localize_path: str = r"F:\xiake2\trunk\Client\XiaKe2_U3DProj\Assets\PackRes\TableData\LocalizeTable.bytes"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
