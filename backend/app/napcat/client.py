"""NapCat OneBot v11 HTTP 客户端（看门狗专用，轻量封装）。

只覆盖看门狗需要的两个动作：
  - get_status：查 QQ 号真实在线状态（被踢后会变 false）
  - send_private_msg：恢复在线后给管理员发私聊

注意：被踢下线时号本身离线，send_private_msg 会失败——这是 OneBot 的硬限制，
故"需扫码"场景由 watchdog 改走钉钉带外告警，不依赖这里发消息。
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    settings = get_settings()
    if settings.qq_access_token:
        return {"Authorization": f"Bearer {settings.qq_access_token}"}
    return {}


async def get_status() -> bool:
    """查 QQ 号真实在线状态。异常/超时一律视为离线返回 False。

    用 /get_status 的 data.online（被踢后变 false），不能用 /get_login_info
    （进程活着就永远 ok，反映不了真实在线）。
    """
    settings = get_settings()
    base_url = settings.qq_napcat_url.rstrip("/")
    if not base_url:
        return False
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=_headers(), timeout=10, trust_env=False) as client:
            r = await client.post("/get_status", json={})
            data = r.json()
            return bool(data.get("data", {}).get("online"))
    except Exception as e:
        logger.warning(f"[napcat] get_status 失败（视为离线）: {e}")
        return False


async def send_private_msg(user_id: int, text: str) -> bool:
    """给指定 QQ 发私聊。成功返回 True。"""
    settings = get_settings()
    base_url = settings.qq_napcat_url.rstrip("/")
    if not base_url or not user_id:
        return False
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=_headers(), timeout=10, trust_env=False) as client:
            r = await client.post("/send_private_msg", json={"user_id": int(user_id), "message": text})
            data = r.json()
            ok = data.get("status") == "ok" or data.get("retcode") == 0
            if not ok:
                logger.error(f"[napcat] send_private_msg 失败: {data.get('msg') or data}")
            return ok
    except Exception as e:
        logger.error(f"[napcat] send_private_msg 异常: {e}")
        return False
