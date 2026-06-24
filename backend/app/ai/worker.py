"""AI 分析独立后台 worker（与爬取解耦）。

爬虫只负责把原始评论入库（ai_status='pending'），本 worker 每隔 N 分钟扫一批
pending 评论：
  - 其他平台（steam_store / steam_hub / xiaoheihe / discord）：逐条 run_pipeline
  - Discord：pipeline 跑完后整批再做话题聚合
  - QQ：整批联合分析（单条 sentiment/category + 话题聚合同步完成）

失败处理：retry_count 累加 + 指数退避；超过 ai_max_retries 标 'failed'。
评论本身已在库里、前端可见，AI 服务挂掉只是"分析延迟"，不影响业务。

并发模型：当前串行（一批内 for 循环 await）。后续若延迟过高再加 Semaphore；
扩展到多进程时把 `_fetch_pending_batch` 改成 `FOR UPDATE SKIP LOCKED`。
"""
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)
ai_scheduler = AsyncIOScheduler()

# 防止两次 worker tick 重叠（APScheduler 的 max_instances=1 已是保险绳，
# 此处的 in-process flag 用于 manual 触发或测试时的二次保护）
_worker_running = False


# ─────────────────────────────────────────────────────────────────────────────
# 入口：APScheduler 注册 + 单次跑
# ─────────────────────────────────────────────────────────────────────────────

def start_ai_worker() -> None:
    settings = get_settings()
    ai_scheduler.add_job(
        run_ai_worker_once,
        "interval",
        minutes=settings.ai_worker_interval_minutes,
        id="ai_worker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.utcnow() + timedelta(seconds=30),  # 启动 30s 后跑首次，避免和 cleanup 抢锁
    )
    ai_scheduler.start()
    logger.info(
        f"[ai_worker] 已启动，间隔={settings.ai_worker_interval_minutes}min，"
        f"batch={settings.ai_worker_batch_size}，max_retries={settings.ai_max_retries}"
    )


async def run_ai_worker_once() -> None:
    """单次扫描 + 处理一批 pending。"""
    global _worker_running
    if _worker_running:
        logger.info("[ai_worker] 上一轮还在跑，跳过本次触发")
        return
    _worker_running = True
    try:
        await _run_once_inner()
    except Exception as e:
        import traceback
        logger.error(f"[ai_worker] 未捕获异常: {e}\n{traceback.format_exc()}")
    finally:
        _worker_running = False


async def _run_once_inner() -> None:
    from app.database import async_session

    settings = get_settings()
    async with async_session() as db:
        batch = await _fetch_pending_batch(db, limit=settings.ai_worker_batch_size)
        if not batch:
            return

        logger.info(f"[ai_worker] 取到 {len(batch)} 条 pending")

        # 按 (game_id, platform) 分组：方便后续整批聚合（QQ/Discord）
        grouped: dict[tuple[uuid.UUID, str], list] = defaultdict(list)
        for c in batch:
            grouped[(c.game_id, c.platform)].append(c)

        for (game_id, platform), comments in grouped.items():
            if platform == "qq":
                await _process_qq_batch(game_id, comments, db)
            elif platform == "discord":
                await _process_discord_batch(game_id, comments, db)
            else:
                await _process_generic_batch(comments, db)

        await db.commit()

        # AI 影子预判（采纳/不采纳）：对本批已完成分析的评论，挑选有反馈价值的类别
        # 静默预判。失败不影响主流程；冷启动门槛与样本检索在 predictor 内部处理。
        await _shadow_predict_batch(batch, db)


async def _shadow_predict_batch(batch: list, db: AsyncSession) -> None:
    """对本批 done 的评论做策划采纳/不采纳影子预判（只新条目）。"""
    from app.ai.curation_predictor import predict_decision

    # 只对真正完成分析、且属于需策划处理类别（bug/suggestion/complaint）的评论预判
    _PREDICT_CATEGORIES = {"bug", "suggestion", "complaint"}
    for c in batch:
        if c.ai_status != "done":
            continue
        if c.category not in _PREDICT_CATEGORIES:
            continue
        # source_type 与前端一致：bug/suggestion 单列，其余归 comment
        source_type = c.category if c.category in ("bug", "suggestion") else "comment"
        try:
            await predict_decision(source_type, c.id, c.content, c.game_id, db)
        except Exception as e:
            logger.warning(f"[ai_worker] 影子预判失败 comment={c.id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 取批：partial index 上 ORDER BY next_ai_attempt_at NULLS FIRST, fetched_at
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_pending_batch(db: AsyncSession, limit: int) -> list:
    from app.models import Comment

    now = datetime.utcnow()
    q = (
        select(Comment)
        .where(
            Comment.ai_status == "pending",
            or_(
                Comment.next_ai_attempt_at.is_(None),
                Comment.next_ai_attempt_at < now,
            ),
        )
        .order_by(
            Comment.next_ai_attempt_at.asc().nulls_first(),
            Comment.fetched_at.asc(),
        )
        .limit(limit)
    )
    return list((await db.execute(q)).scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# 平台分发
# ─────────────────────────────────────────────────────────────────────────────

async def _process_generic_batch(comments: list, db: AsyncSession) -> None:
    """steam_store / steam_hub / xiaoheihe：逐条 run_pipeline。"""
    from app.ai.pipeline import run_pipeline

    for c in comments:
        try:
            await run_pipeline(c, db)
            _mark_done(c)
        except Exception as e:
            _mark_retry_or_fail(c, e)


async def _process_discord_batch(
    game_id: uuid.UUID, comments: list, db: AsyncSession,
) -> None:
    """Discord：先逐条 pipeline（含 is_game_feedback 过滤），再整批话题聚合。"""
    from app.ai.pipeline import run_pipeline

    succeeded_ids: list[uuid.UUID] = []
    for c in comments:
        try:
            await run_pipeline(c, db)
            # 注意：pipeline 内部可能把 ai_status 改成 'skipped'（非游戏反馈）
            # 此时不要覆盖回 'done'
            if c.ai_status != "skipped":
                _mark_done(c)
            # 只有"真做了完整分析"的进入话题聚合
            if c.is_game_feedback:
                succeeded_ids.append(c.id)
        except Exception as e:
            _mark_retry_or_fail(c, e)

    # 话题聚合失败不影响单条状态：单条已是 done，topic 是锦上添花
    if succeeded_ids:
        try:
            from app.ai.topic_cluster import analyze_new_discord_topics
            await analyze_new_discord_topics(str(game_id), succeeded_ids, db)
        except Exception as e:
            logger.warning(f"[ai_worker] Discord 话题聚合失败 game={game_id}: {e}")


async def _process_qq_batch(
    game_id: uuid.UUID, comments: list, db: AsyncSession,
) -> None:
    """QQ：整批联合分析（单条分类 + 话题聚合一次完成）。

    qq_analyzer 返回 (processed_ids, skipped_ids)——明确告诉 worker：
      - processed_ids 里的：AI 真分析过且判为游戏反馈 → _mark_done
      - skipped_ids   里的：AI 真分析过但判为水群/广告 → ai_status='skipped'（不重试、不污染统计）
      - 都不在的       ：AI 调用失败或漏返回           → _mark_retry_or_fail
    """
    from app.ai.qq_analyzer import analyze_new_qq_comments

    ids = [c.id for c in comments]
    try:
        processed_ids, skipped_ids, batch_failed_ids = await analyze_new_qq_comments(
            str(game_id), ids, db
        )
    except Exception as e:
        # analyze_new_qq_comments 理论上不 raise；万一 raise（DB 故障等），整批延后重试兜底
        for c in comments:
            _mark_batch_deferred(c, e)
        return

    drop_fail = Exception(
        "qq_analyzer AI 调用成功但漏返回本条 index（疑似 AI 输出截断/格式问题）"
    )
    done_cnt = skip_cnt = defer_cnt = drop_cnt = 0
    for c in comments:
        if c.id in processed_ids:
            _mark_done(c)
            done_cnt += 1
        elif c.id in skipped_ids:
            _mark_skipped(c)
            skip_cnt += 1
        elif c.id in batch_failed_ids:
            # 整批 AI 调用失败连坐 → 延后重试，不计 max_retries、永不标 failed
            _mark_batch_deferred(c, Exception("所属批次 AI 调用整体失败，延后重试"))
            defer_cnt += 1
        else:
            # AI 调用成功但漏返回这一条 index → 单条真失败，走 retry/failed
            _mark_retry_or_fail(c, drop_fail)
            drop_cnt += 1
    logger.info(
        f"[ai_worker] QQ 批 game={game_id} 结果："
        f"done={done_cnt} skipped={skip_cnt} "
        f"batch_deferred={defer_cnt} retry/failed={drop_cnt}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 状态机辅助
# ─────────────────────────────────────────────────────────────────────────────

def _mark_done(comment) -> None:
    comment.ai_status = "done"
    comment.last_ai_error = None
    comment.next_ai_attempt_at = None


def _mark_skipped(comment) -> None:
    """AI 真分析过但判为非游戏反馈（水群/广告/图片）。不再重试、不计入情感/分类统计。"""
    comment.ai_status = "skipped"
    comment.last_ai_error = None
    comment.next_ai_attempt_at = None


def _mark_batch_deferred(comment, exc: Exception) -> None:
    """整批 AI 调用失败时的连坐保护：保持 pending、固定延后一个退避窗口再试，
    **不累加 retry_count、永不标 failed**。

    语义：AI 服务挂了不是这条评论的错，不该消耗它的重试额度。这是解耦设计的核心——
    AI 长期挂只导致"分析延迟"，评论始终是 pending、前端可见，AI 一恢复就会被处理。
    """
    settings = get_settings()
    comment.ai_status = "pending"
    comment.last_ai_error = str(exc)[:500]
    # 用固定基数退避（不指数增长，因为没累加 retry_count）；给 router 熔断窗口留出恢复时间
    comment.next_ai_attempt_at = datetime.utcnow() + timedelta(
        seconds=settings.ai_retry_backoff_base_seconds
    )


def _mark_retry_or_fail(comment, exc: Exception) -> None:
    settings = get_settings()
    comment.ai_retry_count = (comment.ai_retry_count or 0) + 1
    comment.last_ai_error = str(exc)[:500]
    if comment.ai_retry_count >= settings.ai_max_retries:
        comment.ai_status = "failed"
        comment.next_ai_attempt_at = None
        logger.warning(
            f"[ai_worker] comment={comment.id} 达到最大重试 "
            f"{settings.ai_max_retries}，标 failed: {exc}"
        )
    else:
        backoff = settings.ai_retry_backoff_base_seconds * (
            2 ** (comment.ai_retry_count - 1)
        )
        comment.next_ai_attempt_at = datetime.utcnow() + timedelta(seconds=backoff)
        logger.info(
            f"[ai_worker] comment={comment.id} 第 {comment.ai_retry_count} 次失败，"
            f"{backoff}s 后重试: {exc}"
        )
