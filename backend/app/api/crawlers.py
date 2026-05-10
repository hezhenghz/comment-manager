import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Game, User
from app.auth import get_current_user
from app.crawlers.registry import get_crawler, available_platforms
from app.crawlers.scheduler import run_crawl

router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])


@router.post("/{platform}/run")
async def trigger_crawl(
    platform: str,
    game_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if platform not in available_platforms():
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    game_uuid = uuid.UUID(game_id)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    await run_crawl(platform, game.steam_app_id or "", str(game.id))
    return {"status": "ok", "platform": platform, "game_id": game_id}
