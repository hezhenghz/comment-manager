import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, delete, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Comment, Game, User
from app.auth import get_current_user
from app.schemas.schemas import CommentOut, CommentListOut

router = APIRouter(prefix="/api/comments", tags=["comments"])


async def _chat_dedup_ids(
    db: AsyncSession,
    game_id: uuid.UUID,
    platform: str,
    channel_field: str,
    extra_filters: list,
) -> list[uuid.UUID]:
    """
    对满足 extra_filters 的群聊/频道评论按频道内行号去重。
    行号基于该游戏全量该平台消息计算（保证位置准确），
    同一频道内两条消息行号差 ≤ 20（互在对方 ±10 上下文窗口内）则只保留较早一条。
    返回去重后应保留的评论 ID 列表。
    """
    # 全量该平台消息的频道内行号子查询
    rn_subq = (
        select(
            Comment.id.label("id"),
            Comment.raw_json[channel_field].astext.label("channel_id"),
            func.row_number().over(
                partition_by=Comment.raw_json[channel_field].astext,
                order_by=Comment.published_at.asc(),
            ).label("rn"),
        )
        .where(Comment.game_id == game_id, Comment.platform == platform)
        .subquery()
    )

    # 目标评论（满足 extra_filters）的行号
    q = (
        select(Comment.id, rn_subq.c.channel_id, rn_subq.c.rn)
        .join(rn_subq, Comment.id == rn_subq.c.id)
        .where(Comment.platform == platform, Comment.game_id == game_id)
    )
    for f in extra_filters:
        q = q.where(f)
    q = q.order_by(rn_subq.c.channel_id, rn_subq.c.rn)

    rows = (await db.execute(q)).all()

    # 贪心去重：同频道内行号差 ≤ 20 则跳过（被前一条上下文覆盖）
    kept: list[uuid.UUID] = []
    last_rn: dict[str, int] = {}
    for row in rows:
        cid = str(row.channel_id) if row.channel_id else "__none__"
        rn = row.rn
        if cid not in last_rn or rn - last_rn[cid] > 20:
            kept.append(row.id)
            last_rn[cid] = rn

    return kept


@router.get("", response_model=CommentListOut)
async def list_comments(
    game_id: uuid.UUID | None = Query(None),
    platform: str | None = Query(None),
    exclude_platform: str | None = Query(None),  # 排除指定平台，支持逗号分隔（如 "qq,discord"）
    sentiment: str | None = Query(None),
    category: str | None = Query(None),
    content_lang: str | None = Query(None),
    recommended: bool | None = Query(None),  # True=推荐, False=不推荐
    bug_status: str | None = Query(None),    # BUG 处理状态筛选（accepted/completed/unprocessed）
    q: str | None = Query(None),             # 关键词全文搜索（ILIKE）
    dedupe_chat: bool = Query(False),        # 对群聊消息（QQ/Discord）按频道内位置去重（BUG/建议模式用）
    # 向下兼容旧参数名
    dedupe_qq: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Comment).options(selectinload(Comment.game))
    count_q = select(func.count(Comment.id))

    filters = []
    if game_id:
        filters.append(Comment.game_id == game_id)
    if platform:
        filters.append(Comment.platform == platform)
    if exclude_platform:
        excluded = [p.strip() for p in exclude_platform.split(',')]
        filters.append(Comment.platform.notin_(excluded))
    if sentiment:
        filters.append(Comment.sentiment == sentiment)
    if category:
        filters.append(Comment.category == category)
    if content_lang:
        filters.append(Comment.content_lang == content_lang)
    if recommended is True:
        # Steam/其他平台：thumbs_up == 1；小黑盒：4-5 星
        filters.append(or_(
            and_(Comment.platform != "xiaoheihe", Comment.thumbs_up == 1),
            and_(Comment.platform == "xiaoheihe", Comment.thumbs_up >= 4),
        ))
    elif recommended is False:
        # Steam/其他平台：thumbs_up == 0；小黑盒：1-3 星
        filters.append(or_(
            and_(Comment.platform != "xiaoheihe", Comment.thumbs_up == 0),
            and_(Comment.platform == "xiaoheihe", Comment.thumbs_up >= 1, Comment.thumbs_up <= 3),
        ))
    if q:
        filters.append(Comment.content.ilike(f"%{q}%"))
    if bug_status == "unprocessed":
        filters.append(Comment.bug_status.is_(None))
    elif bug_status in ("accepted", "completed"):
        filters.append(Comment.bug_status == bug_status)

    # 群聊消息去重：同一频道内行号差 ≤ 20 的只保留最早一条
    # 兼容旧参数名 dedupe_qq
    do_dedup = dedupe_chat or dedupe_qq
    if do_dedup and game_id:
        qq_kept      = await _chat_dedup_ids(db, game_id, "qq",      "group_id",   filters)
        discord_kept = await _chat_dedup_ids(db, game_id, "discord", "channel_id", filters)
        all_kept = qq_kept + discord_kept
        if all_kept:
            filters.append(or_(
                Comment.platform.notin_(["qq", "discord"]),
                Comment.id.in_(all_kept),
            ))
        else:
            filters.append(Comment.platform.notin_(["qq", "discord"]))

    for f in filters:
        query = query.where(f)
        count_q = count_q.where(f)

    total = (await db.execute(count_q)).scalar() or 0
    query = query.order_by(desc(Comment.published_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    items = [
        CommentOut(
            id=c.id, game_id=c.game_id, platform=c.platform, source_type=c.source_type,
            source_url=c.source_url, author_name=c.author_name, content=c.content,
            content_lang=c.content_lang, published_at=c.published_at, sentiment=c.sentiment,
            sentiment_score=c.sentiment_score, category=c.category, summary=c.summary,
            translation=c.translation, is_duplicate=c.is_duplicate,
            game_name=c.game.name if c.game else None, thumbs_up=c.thumbs_up,
            bug_status=c.bug_status,
        )
        for c in rows
    ]
    return CommentListOut(total=total, items=items, page=page, page_size=page_size)


@router.post("/clear", status_code=204)
async def clear_comments(
    game_id: uuid.UUID = Query(...),
    platform: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await db.execute(
        delete(Comment)
        .where(Comment.game_id == game_id, Comment.platform == platform)
        .execution_options(synchronize_session=False)
    )
    await db.commit()


@router.get("/{comment_id}", response_model=CommentOut)
async def get_comment(comment_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Comment).options(selectinload(Comment.game)).where(Comment.id == comment_id))
    c = result.scalar_one_or_none()
    if c is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return CommentOut(
        id=c.id, game_id=c.game_id, platform=c.platform, source_type=c.source_type,
        source_url=c.source_url, author_name=c.author_name, content=c.content,
        content_lang=c.content_lang, published_at=c.published_at, sentiment=c.sentiment,
        sentiment_score=c.sentiment_score, category=c.category, summary=c.summary,
        translation=c.translation, is_duplicate=c.is_duplicate,
        game_name=c.game.name if c.game else None, thumbs_up=c.thumbs_up,
        bug_status=c.bug_status,
    )


@router.patch("/{comment_id}/bug-status", status_code=204)
async def update_bug_status(
    comment_id: uuid.UUID,
    status: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """更新 BUG 处理状态。status 传 'accepted'、'completed' 或 'unprocessed'（重置为未处理）。"""
    VALID = {"accepted", "completed", "unprocessed"}
    if status not in VALID:
        raise HTTPException(status_code=400, detail=f"Invalid status, must be one of {VALID}")
    c = await db.get(Comment, comment_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Not found")
    c.bug_status = None if status == "unprocessed" else status
    await db.commit()


@router.get("/{comment_id}/chat-context")
async def get_chat_context(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回 QQ 或 Discord 评论的上下文：发送者信息 + 该频道/群的前10条 + 本条 + 后10条消息（时间升序）。"""
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    c = result.scalar_one_or_none()
    if c is None or not c.raw_json:
        raise HTTPException(status_code=404, detail="Not found or no raw_json")

    if c.platform == "qq":
        channel_id    = str(c.raw_json.get("group_id",   ""))
        sender_id     = str(c.raw_json.get("sender_id",  ""))
        channel_field = "group_id"
    elif c.platform == "discord":
        channel_id    = str(c.raw_json.get("channel_id", ""))
        sender_id     = ""   # Discord 未存 sender_id
        channel_field = "channel_id"
    else:
        raise HTTPException(status_code=404, detail="Not a chat platform comment")

    prev: list[Comment] = []
    nxt:  list[Comment] = []
    if channel_id and c.published_at:
        r2 = await db.execute(
            select(Comment)
            .where(
                Comment.game_id == c.game_id,
                Comment.platform == c.platform,
                Comment.raw_json[channel_field].astext == channel_id,
                Comment.published_at < c.published_at,
            )
            .order_by(Comment.published_at.desc())
            .limit(10)
        )
        prev = list(reversed(r2.scalars().all()))  # 时间升序展示

        r3 = await db.execute(
            select(Comment)
            .where(
                Comment.game_id == c.game_id,
                Comment.platform == c.platform,
                Comment.raw_json[channel_field].astext == channel_id,
                Comment.published_at > c.published_at,
            )
            .order_by(Comment.published_at.asc())
            .limit(10)
        )
        nxt = list(r3.scalars().all())

    def _msg(m: Comment) -> dict:
        return {
            "content":      m.content,
            "published_at": m.published_at.isoformat() if m.published_at else None,
            "author_name":  m.author_name,
        }

    return {
        "platform":        c.platform,
        "sender_id":       sender_id,
        "sender_name":     c.author_name,
        "group_id":        channel_id,   # 统一字段名，前端统一取此字段
        "prev_messages":   [_msg(m) for m in prev],
        "current_message": _msg(c),
        "next_messages":   [_msg(m) for m in nxt],
    }


# 向下兼容旧路由（qq-context → chat-context）
@router.get("/{comment_id}/qq-context")
async def get_qq_context_compat(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """旧路由别名，重定向到 chat-context。"""
    return await get_chat_context(comment_id, db, _)


@router.post("/{comment_id}/translate")
async def translate_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from fastapi import HTTPException
    from app.ai.translate import translate_to_chinese

    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Not found")

    # 优先返回已存储的翻译
    if c.translation:
        return {"translated": c.translation}

    try:
        translated = await translate_to_chinese(c.content)
        c.translation = translated
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"translated": translated}
