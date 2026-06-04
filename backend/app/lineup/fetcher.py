# -*- coding: utf-8 -*-
"""阵容拉取器：遍历 门派×段位×失败回合区间，拉取玩家大码并去重落库。

一轮全量 = 10 门派 × 10 段位 × 3 失败回合区间 = 300 次请求，每次 count=50。
去重键 = 大码内容 sha1；ON CONFLICT(code_hash) 时仅更新 last_seen_at（累积，不重复插入）。
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.database import async_session
from app.models import LineupSnapshot, LineupFetchJob
from app.lineup.parser import parse_snapshot, code_hash

logger = logging.getLogger(__name__)

# 参数空间（来自游戏 ConstValue，已确认）
MENPAI_LIST = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
RANK_LEVELS = list(range(1, 11))                 # 1..10
FAIL_RANGES = [(7, 12), (13, 16), (17, 19)]

# 进程内并发锁，防止定时任务与手动触发重叠
_running = False


def is_running() -> bool:
    return _running


async def cleanup_old_snapshots() -> int:
    """删除 last_seen_at 超过保留期的陈旧快照，返回删除行数。"""
    s = get_settings()
    cutoff = datetime.utcnow() - timedelta(days=s.lineup_retention_days)
    async with async_session() as db:
        result = await db.execute(
            delete(LineupSnapshot).where(LineupSnapshot.last_seen_at < cutoff)
        )
        await db.commit()
    deleted = result.rowcount or 0
    if deleted:
        logger.info(f"[lineup] 清理过期快照 {deleted} 条（保留 {s.lineup_retention_days} 天内）")
    return deleted


async def _fetch_one(client: httpx.AsyncClient, men_pai: int, rank: int,
                     min_fr: int, max_fr: int) -> list[dict]:
    """拉取单个(门派,段位,回合区间)，返回 data 列表（每项含 'data' 大码）。"""
    s = get_settings()
    params = {
        "uniq_id": s.lineup_uniq_id,
        "areaId": s.lineup_area_id,
        "menPai": str(men_pai),
        "rankLevel": str(rank),
        "count": str(s.lineup_count),
        "minFailRound": str(min_fr),
        "maxFailRound": str(max_fr),
    }
    try:
        resp = await client.get(s.lineup_api_base, params=params, timeout=25)
        j = resp.json()
        if isinstance(j, dict) and isinstance(j.get("data"), list):
            return j["data"]
    except Exception as e:
        logger.warning(f"[lineup] 请求失败 menPai={men_pai} rank={rank} "
                       f"fr={min_fr}-{max_fr}: {e}")
    return []


async def fetch_all_lineups(job_id: str | None = None, trigger: str = "auto") -> dict:
    """执行一轮全量拉取。返回 {req_total, req_done, new_count}。

    trigger: 来源标记，manual=手动「立即拉取」 / auto=定时任务。仅新建 job 时写入；
    接管已存在 job（job_id 不为 None）时由调用方负责设置 trigger。
    """
    global _running
    if _running:
        logger.info("[lineup] 已有拉取在运行，跳过本次触发")
        return {"skipped": True}
    _running = True

    s = get_settings()
    delay = s.lineup_request_delay_ms / 1000.0
    req_total = len(MENPAI_LIST) * len(RANK_LEVELS) * len(FAIL_RANGES)
    req_done = 0
    new_count = 0

    # 创建/接管 job
    async with async_session() as db:
        if job_id:
            job = await db.get(LineupFetchJob, uuid.UUID(job_id))
            if job is None:
                job = LineupFetchJob(id=uuid.UUID(job_id))
                db.add(job)
        else:
            job = LineupFetchJob(trigger=trigger)
            db.add(job)
        job.status = "running"
        job.req_total = req_total
        job.req_done = 0
        job.new_count = 0
        job.started_at = datetime.utcnow()
        job.finished_at = None
        job.error_msg = None
        await db.commit()
        job_uuid = job.id

    try:
        async with httpx.AsyncClient(headers={"User-Agent": "lineup-fetcher/1.0"}) as client:
            for men_pai in MENPAI_LIST:
                for rank in RANK_LEVELS:
                    for (min_fr, max_fr) in FAIL_RANGES:
                        items = await _fetch_one(client, men_pai, rank, min_fr, max_fr)
                        # 逐条 upsert；用「先查 code_hash 是否存在」判定新增
                        async with async_session() as db:
                            for it in items:
                                big = it.get("data")
                                if not big:
                                    continue
                                try:
                                    snap = parse_snapshot(big)
                                except Exception:
                                    continue
                                h = code_hash(big)
                                now = datetime.utcnow()
                                exists = await db.execute(
                                    select(LineupSnapshot.id).where(
                                        LineupSnapshot.code_hash == h).limit(1)
                                )
                                if exists.scalar_one_or_none() is not None:
                                    # 已存在：仅更新 last_seen_at
                                    await db.execute(
                                        pg_insert(LineupSnapshot).values(
                                            id=uuid.uuid4(), code_hash=h, raw_code=big,
                                            player_name=snap["player_name"], men_pai=men_pai,
                                            rank_level=(snap["rank_level"] or 0),
                                            fail_round=snap["fail_round"],
                                            round_count=snap["round_count"],
                                            item_counts=snap["item_counts"],
                                            first_seen_at=now, last_seen_at=now,
                                        ).on_conflict_do_update(
                                            index_elements=[LineupSnapshot.code_hash],
                                            set_={"last_seen_at": now},
                                        )
                                    )
                                else:
                                    db.add(LineupSnapshot(
                                        code_hash=h, raw_code=big,
                                        player_name=snap["player_name"], men_pai=men_pai,
                                        rank_level=(snap["rank_level"] or 0),
                                        fail_round=snap["fail_round"],
                                        round_count=snap["round_count"],
                                        item_counts=snap["item_counts"],
                                        first_seen_at=now, last_seen_at=now,
                                    ))
                                    new_count += 1
                            await db.commit()

                        req_done += 1
                        # 周期性更新进度（每 10 次请求写一次，减少 DB 压力）
                        if req_done % 10 == 0 or req_done == req_total:
                            async with async_session() as db:
                                j = await db.get(LineupFetchJob, job_uuid)
                                if j:
                                    j.req_done = req_done
                                    j.new_count = new_count
                                    await db.commit()
                        await asyncio.sleep(delay)

        async with async_session() as db:
            j = await db.get(LineupFetchJob, job_uuid)
            if j:
                j.status = "done"
                j.req_done = req_done
                j.new_count = new_count
                j.finished_at = datetime.utcnow()
                await db.commit()
        logger.info(f"[lineup] 拉取完成：请求 {req_done}/{req_total}，新增 {new_count} 条快照")

        # 拉取完成后清理过期快照（失败分支不清理，避免数据异常时误删）
        try:
            await cleanup_old_snapshots()
        except Exception as e:
            logger.warning(f"[lineup] 清理过期快照失败（忽略）：{e}")

        return {"req_total": req_total, "req_done": req_done, "new_count": new_count}

    except Exception as e:
        import traceback
        logger.error(f"[lineup] 拉取异常：{e}\n{traceback.format_exc()}")
        async with async_session() as db:
            j = await db.get(LineupFetchJob, job_uuid)
            if j:
                j.status = "failed"
                j.error_msg = str(e)
                j.finished_at = datetime.utcnow()
                await db.commit()
        return {"error": str(e)}
    finally:
        _running = False
