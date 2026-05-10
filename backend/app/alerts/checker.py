import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Comment, AlertRule, Game
from app.alerts.dingtalk import send_dingtalk_alert

logger = logging.getLogger(__name__)

COOLDOWN = timedelta(minutes=5)


async def check_comment_for_alerts(comment: Comment, db: AsyncSession) -> None:
    from sqlalchemy import select

    if not comment.content:
        return

    result = await db.execute(
        select(AlertRule).where(
            AlertRule.game_id == comment.game_id,
            AlertRule.enabled == True,
        )
    )
    rules = result.scalars().all()

    now = datetime.utcnow()
    lower_content = comment.content.lower()
    for rule in rules:
        matched = any(kw.lower() in lower_content for kw in rule.keywords)
        if not matched:
            continue

        if rule.last_triggered_at and (now - rule.last_triggered_at) < COOLDOWN:
            continue

        logger.info(f"Alert rule {rule.id} triggered by comment {comment.id}")

        if rule.channel == "dingtalk":
            game_result = await db.execute(select(Game).where(Game.id == comment.game_id))
            game = game_result.scalar_one_or_none()
            game_name = game.name if game else "Unknown"
            await send_dingtalk_alert(
                keywords=rule.keywords,
                comment_text=comment.content[:300],
                game_name=game_name,
                platform=comment.platform,
            )

        rule.last_triggered_at = now
