import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Game, Comment, User, CrawlJob
from app.auth import get_current_user
from app.schemas.schemas import GameCreate, GameUpdate, GameOut
from app.config import get_settings

router = APIRouter(prefix="/api/games", tags=["games"])


# ── Steam Lookup（必须在 /{game_id} 路由之前定义）──────────────────────────────

@router.get("/steam-lookup")
async def steam_lookup(
    app_id: str | None = Query(None),
    name: str | None = Query(None),
    _: User = Depends(get_current_user),
):
    """
    按 app_id 查单个游戏，或按 name 搜索 Steam 商店。
    返回 [{ app_id, name, icon_url }] 列表（最多 5 条）。
    """
    if not app_id and not name:
        raise HTTPException(400, "请提供 app_id 或 name 参数")

    settings = get_settings()
    proxy = settings.steam_proxy or None  # "" → None，不传代理

    client_kwargs: dict = {
        "timeout": 12,
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    }
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        try:
            if app_id:
                resp = await client.get(
                    "https://store.steampowered.com/api/appdetails",
                    params={"appids": app_id, "filters": "basic"},
                )
                data = resp.json()
                entry = data.get(str(app_id), {})
                if entry.get("success") and entry.get("data"):
                    d = entry["data"]
                    return [{
                        "app_id": str(d.get("steam_appid", app_id)),
                        "name": d.get("name", ""),
                        "icon_url": d.get("header_image"),
                    }]
                return []

            else:
                resp = await client.get(
                    "https://store.steampowered.com/api/storesearch/",
                    params={"term": name, "l": "schinese", "cc": "CN"},
                )
                data = resp.json()
                items = data.get("items", [])[:5]
                return [
                    {
                        "app_id": str(item["id"]),
                        "name": item.get("name", ""),
                        "icon_url": item.get("tiny_image"),
                    }
                    for item in items
                ]
        except Exception:
            return []


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[GameOut])
async def list_games(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    games = result.scalars().all()
    out = []
    for g in games:
        cnt_result = await db.execute(select(func.count()).select_from(Comment).where(Comment.game_id == g.id))
        comment_count = cnt_result.scalar() or 0
        out.append(GameOut(
            id=g.id, name=g.name, steam_app_id=g.steam_app_id,
            icon_url=g.icon_url, comment_count=comment_count,
            stopwords=g.stopwords or [],
            discord_channel_ids=g.discord_channel_ids or [],
            created_at=g.created_at,
        ))
    return out


@router.post("", response_model=GameOut, status_code=status.HTTP_201_CREATED)
async def create_game(body: GameCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    if not body.name and not body.steam_app_id:
        raise HTTPException(400, "游戏名称或 Steam App ID 至少填写一项")

    # name 为空时用 App ID 兜底
    effective_name = body.name or f"App {body.steam_app_id}"

    # ── 去重检查 ──
    if body.steam_app_id:
        dup = (await db.execute(
            select(Game).where(Game.steam_app_id == body.steam_app_id)
        )).scalar_one_or_none()
        if dup:
            raise HTTPException(409, f"Steam App ID {body.steam_app_id} 已存在（{dup.name}）")

    dup_name = (await db.execute(
        select(Game).where(func.lower(Game.name) == effective_name.lower())
    )).scalar_one_or_none()
    if dup_name:
        raise HTTPException(409, f"游戏「{effective_name}」已存在")

    game = Game(
        name=effective_name,
        steam_app_id=body.steam_app_id,
        icon_url=body.icon_url,
        discord_channel_ids=body.discord_channel_ids or [],
    )
    db.add(game)
    await db.flush()
    await db.refresh(game)
    return GameOut(
        id=game.id, name=game.name, steam_app_id=game.steam_app_id,
        icon_url=game.icon_url, comment_count=0,
        discord_channel_ids=game.discord_channel_ids or [],
        created_at=game.created_at,
    )


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
    if body.stopwords is not None:
        game.stopwords = body.stopwords
    if body.discord_channel_ids is not None:
        game.discord_channel_ids = body.discord_channel_ids
    await db.flush()
    await db.refresh(game)
    cnt_result = await db.execute(select(func.count()).select_from(Comment).where(Comment.game_id == game.id))
    comment_count = cnt_result.scalar() or 0
    return GameOut(
        id=game.id, name=game.name, steam_app_id=game.steam_app_id,
        icon_url=game.icon_url, comment_count=comment_count,
        stopwords=game.stopwords or [],
        discord_channel_ids=game.discord_channel_ids or [],
        created_at=game.created_at,
    )


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game(game_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    await db.execute(delete(CrawlJob).where(CrawlJob.game_id == game_id))
    await db.delete(game)
