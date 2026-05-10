import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Game, User
from app.auth import get_current_user
from app.schemas.schemas import GameCreate, GameUpdate, GameOut

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("", response_model=list[GameOut])
async def list_games(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    games = result.scalars().all()
    out = []
    for g in games:
        cnt_result = await db.execute(select(func.count()).select_from(g.comments))
        comment_count = cnt_result.scalar() or 0
        out.append(GameOut(
            id=g.id, name=g.name, steam_app_id=g.steam_app_id,
            icon_url=g.icon_url, comment_count=comment_count, created_at=g.created_at
        ))
    return out


@router.post("", response_model=GameOut, status_code=status.HTTP_201_CREATED)
async def create_game(body: GameCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    game = Game(name=body.name, steam_app_id=body.steam_app_id, icon_url=body.icon_url)
    db.add(game)
    await db.flush()
    await db.refresh(game)
    return GameOut(id=game.id, name=game.name, steam_app_id=game.steam_app_id,
                   icon_url=game.icon_url, comment_count=0, created_at=game.created_at)


@router.put("/{game_id}", response_model=GameOut)
async def update_game(game_id: uuid.UUID, body: GameUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if body.name is not None:
        game.name = body.name
    if body.steam_app_id is not None:
        game.steam_app_id = body.steam_app_id
    if body.icon_url is not None:
        game.icon_url = body.icon_url
    await db.flush()
    await db.refresh(game)
    cnt_result = await db.execute(select(func.count()).select_from(game.comments))
    comment_count = cnt_result.scalar() or 0
    return GameOut(id=game.id, name=game.name, steam_app_id=game.steam_app_id,
                   icon_url=game.icon_url, comment_count=comment_count, created_at=game.created_at)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game(game_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    await db.delete(game)
