import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_dingtalk_alert(keywords: list[str], comment_text: str, game_name: str, platform: str) -> None:
    settings = get_settings()
    webhook = settings.dingtalk_webhook_url
    if not webhook:
        logger.warning("DingTalk webhook not configured, skipping alert")
        return

    kw_str = ", ".join(keywords)
    text = f"## Alert: {game_name} ({platform})\n\n"
    text += f"**Triggered keywords**: {kw_str}\n\n"
    text += f"**Comment**:\n> {comment_text[:500]}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"[Comment Manager] Alert - {game_name}",
            "text": text,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook, json=payload)
            if resp.status_code == 200:
                logger.info("DingTalk alert sent successfully")
            else:
                logger.error(f"DingTalk alert failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"DingTalk alert error: {e}")
