# -*- coding: utf-8 -*-
"""阵容物品使用率分析 API。

- POST /api/lineup/fetch      手动触发一轮拉取（后台任务）
- GET  /api/lineup/job        最近一次拉取任务的状态/进度
- GET  /api/lineup/usage      物品使用率聚合（可按门派/段位筛选）
- GET  /api/lineup/menpais    门派列表（给前端下拉）
"""
import asyncio
import uuid
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, LineupSnapshot, LineupFetchJob, LineupScheduleConfig
from app.auth import get_current_user
from app.lineup.fetcher import fetch_all_lineups, is_running, MENPAI_LIST, RANK_LEVELS
from app.lineup.schedule import get_or_create_config
from app.lineup import meta
from app.lineup.series import fold_counter
from app.lineup.exclusions import is_excluded, EXCLUDED_ITEMS

router = APIRouter(prefix="/api/lineup", tags=["lineup"])


# ── 聚合结果内存缓存 ──────────────────────────────────────────────────
# 数据只在每小时拉取一轮时变化，其余时间不变。用「数据指纹」做失效信号：
# 指纹 = (快照行数, max(last_seen_at))，查询仅 ~16ms，远快于 1.3s 的聚合。
# 拉取的 upsert 刷新 last_seen_at、清理减少行数，都会改变指纹 → 缓存自动失效。
_agg_cache: dict[tuple, tuple] = {}   # key -> (fingerprint, result)


async def _data_fingerprint(db: AsyncSession) -> tuple:
    """数据指纹：行数 + 最新 last_seen_at。数据变则指纹变。"""
    row = (await db.execute(
        select(func.count(LineupSnapshot.id), func.max(LineupSnapshot.last_seen_at))
    )).one()
    return (row[0], row[1].isoformat() if row[1] else None)


def _cache_get(key: tuple, fp: tuple):
    hit = _agg_cache.get(key)
    return hit[1] if hit and hit[0] == fp else None


def _cache_put(key: tuple, fp: tuple, result) -> None:
    # 指纹变化时整体清空（旧指纹下所有条目均已失效，顺带防止无限增长）
    if _agg_cache and next(iter(_agg_cache.values()))[0] != fp:
        _agg_cache.clear()
    _agg_cache[key] = (fp, result)


def _since_cond(since_days: int | None):
    """按 first_seen_at 过滤的时间条件；since_days 为空或<=0 时返回 None（不过滤）。

    口径：first_seen_at >= now - since_days 天，即「近 N 天内首次出现的阵容」。
    用 first_seen_at 而非 last_seen_at —— 后者会被重复抓取持续刷新，无法反映新旧。
    """
    if not since_days or since_days <= 0:
        return None
    cutoff = datetime.utcnow() - timedelta(days=since_days)
    return LineupSnapshot.first_seen_at >= cutoff


@router.post("/fetch")
async def trigger_fetch(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """手动触发一轮全量拉取。已在运行则拒绝。"""
    if is_running():
        raise HTTPException(status_code=409, detail="已有拉取任务在运行")
    job = LineupFetchJob(status="running", trigger="manual")
    db.add(job)
    await db.commit()
    asyncio.create_task(fetch_all_lineups(job_id=str(job.id), trigger="manual"))
    return {"status": "ok", "job_id": str(job.id)}


@router.get("/job")
async def latest_job(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """最近一次拉取任务的状态/进度。"""
    q = select(LineupFetchJob).order_by(LineupFetchJob.started_at.desc()).limit(1)
    job = (await db.execute(q)).scalar_one_or_none()
    if job is None:
        return {"job": None, "running": is_running()}
    return {
        "running": is_running(),
        "job": {
            "id": str(job.id),
            "status": job.status,
            "req_total": job.req_total,
            "req_done": job.req_done,
            "new_count": job.new_count,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "error_msg": job.error_msg,
        },
    }


class ScheduleUpdate(BaseModel):
    enabled: bool
    interval_hours: int = Field(ge=1, le=168)  # 1 小时 ~ 7 天


async def _schedule_payload(db: AsyncSession) -> dict:
    """组装调度状态返回体：DB 配置 + 下次执行时间 + 最近一次自动拉取结果。"""
    from app.crawlers.scheduler import scheduler

    cfg = await get_or_create_config(db)
    sched_job = scheduler.get_job("lineup_fetch")
    next_run = (
        sched_job.next_run_time.isoformat()
        if sched_job and sched_job.next_run_time else None
    )
    # 最近一次「自动」拉取结果（不含手动触发）
    q = (
        select(LineupFetchJob)
        .where(LineupFetchJob.trigger == "auto")
        .order_by(LineupFetchJob.started_at.desc())
        .limit(1)
    )
    last_auto = (await db.execute(q)).scalar_one_or_none()
    last_auto_payload = None
    if last_auto is not None:
        last_auto_payload = {
            "status": last_auto.status,
            "new_count": last_auto.new_count,
            "started_at": last_auto.started_at.isoformat() if last_auto.started_at else None,
            "finished_at": last_auto.finished_at.isoformat() if last_auto.finished_at else None,
            "error_msg": last_auto.error_msg,
        }
    return {
        "enabled": cfg.enabled,
        "interval_hours": cfg.interval_hours,
        "next_run_time": next_run,
        "last_auto_job": last_auto_payload,
    }


@router.get("/schedule")
async def schedule(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """自动拉取调度状态：开关 / 间隔 / 下次执行时间 / 上次自动拉取结果。"""
    return await _schedule_payload(db)


@router.put("/schedule")
async def update_schedule(
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """更新自动拉取配置并立即生效（无需重启后端）。"""
    from app.crawlers.scheduler import apply_lineup_schedule

    cfg = await get_or_create_config(db)
    cfg.enabled = body.enabled
    cfg.interval_hours = body.interval_hours
    await db.commit()
    apply_lineup_schedule(body.enabled, body.interval_hours)
    return await _schedule_payload(db)


@router.post("/reload-items")
async def reload_items(_: User = Depends(get_current_user)):
    """强制重新解析 ItemCfg/LocalizeTable（上线新物品后可手动刷新名表）。"""
    return meta.reload_now()


@router.get("/menpais")
async def menpais(_: User = Depends(get_current_user)):
    """门派/段位选项，给前端筛选下拉。"""
    return {
        "menpais": [{"value": m, "name": meta.menpai_name(m)} for m in MENPAI_LIST],
        "rank_levels": RANK_LEVELS,
    }


@router.get("/usage")
async def usage(
    menPai: int | None = None,
    rankLevel: int | None = None,
    top: int = 50,
    careerOnly: bool = False,
    sinceDays: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """物品使用率聚合：按筛选条件合并 item_counts，返回降序 Top N。

    使用率% = 该物品累计出现次数 / 总回合数 × 100（不去重，可 >100%，
    含义为"平均每回合该物品出现 N 次"）。总回合数 = 当前筛选范围内所有快照
    round_count 之和。

    返回 {
      sample_players: 样本玩家(快照)数,
      total_uses: 所有物品出现总次数,
      total_rounds: 当前筛选范围内总回合数（百分比分母）,
      items: [{itemId, name, count, pct, isCareer}]  降序
    }
    """
    fp = await _data_fingerprint(db)
    ckey = ("usage", menPai, rankLevel, top, careerOnly, sinceDays)
    cached = _cache_get(ckey, fp)
    if cached is not None:
        return cached

    conds = []
    if menPai is not None:
        conds.append(LineupSnapshot.men_pai == menPai)
    if rankLevel is not None:
        conds.append(LineupSnapshot.rank_level == rankLevel)
    since = _since_cond(sinceDays)
    if since is not None:
        conds.append(since)

    q = select(LineupSnapshot.item_counts, LineupSnapshot.round_count)
    if conds:
        q = q.where(*conds)

    rows = (await db.execute(q)).all()
    sample_players = len(rows)

    counter: Counter = Counter()
    total_rounds = 0
    for item_counts, round_count in rows:
        total_rounds += (round_count or 0)
        if not item_counts:
            continue
        for item_id_str, cnt in item_counts.items():
            try:
                iid = int(item_id_str)
            except (TypeError, ValueError):
                continue
            counter[iid] += cnt   # 全量累加，系列折叠与 careerOnly 过滤延后

    # 折叠系列：成员合并为单一系列条目（key=系列 repId）
    folded, kmeta = fold_counter(counter)

    def _name(k):   return kmeta[k]["name"]     if k in kmeta else meta.item_name(k)
    def _rank(k):   return kmeta[k]["rank"]     if k in kmeta else meta.item_rank(k)
    def _career(k): return kmeta[k]["isCareer"] if k in kmeta else meta.is_career(k)

    # careerOnly 基于折叠后的系列级职业属性过滤（避免系列内非职业成员被提前剔除）
    if careerOnly:
        folded = {k: c for k, c in folded.items() if _career(k)}

    total_uses = sum(folded.values())

    def _pct(c: int) -> float:
        return round(c / total_rounds * 100, 2) if total_rounds else 0.0

    ranked = sorted(folded.items(), key=lambda x: x[1], reverse=True)
    if top and top > 0:
        ranked = ranked[:top]
    items = [
        {
            "itemId": k,
            "name": _name(k),
            "count": c,
            "pct": _pct(c),
            "isCareer": _career(k),
            "rank": _rank(k),
        }
        for k, c in ranked
    ]
    result = {
        "sample_players": sample_players,
        "total_uses": total_uses,
        "total_rounds": total_rounds,
        "items": items,
    }
    _cache_put(ckey, fp, result)
    return result


@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """概览统计：总局数(快照数)、总回合数、覆盖门派数、各门派快照分布。"""
    fp = await _data_fingerprint(db)
    ckey = ("stats",)
    cached = _cache_get(ckey, fp)
    if cached is not None:
        return cached

    total = (await db.execute(select(func.count(LineupSnapshot.id)))).scalar() or 0
    total_rounds = (await db.execute(select(func.coalesce(func.sum(LineupSnapshot.round_count), 0)))).scalar() or 0
    # 各门派分布
    by_menpai_q = (
        select(LineupSnapshot.men_pai, func.count(LineupSnapshot.id))
        .group_by(LineupSnapshot.men_pai)
    )
    by_menpai = [
        {"menPai": m, "name": meta.menpai_name(m), "count": c}
        for m, c in (await db.execute(by_menpai_q)).all()
    ]
    result = {
        "total_snapshots": total,
        "total_rounds": total_rounds,
        "menpai_count": len(by_menpai),
        "by_menpai": sorted(by_menpai, key=lambda x: x["menPai"]),
    }
    _cache_put(ckey, fp, result)
    return result


@router.get("/usage-by-type")
async def usage_by_type(
    menPai: int | None = None,
    rankLevel: int | None = None,
    topN: int = 20,
    sinceDays: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按物品类型分组的使用率：每个类型返回 Top N 与 Last N（出现过即 count>0）。

    - 分母 total_rounds = 当前筛选范围内所有快照 round_count 之和。
    - 仅返回至少含 1 个 count>0 物品的类型（空类型不返回，前端不渲染空行）。
    - 类型按枚举值升序排列。
    返回 { total_rounds, types: [{type, typeName, top:[...], last:[...]}] }
    其中每项 item = {itemId, name, count, pct, isCareer}。
    """
    fp = await _data_fingerprint(db)
    ckey = ("usage-by-type", menPai, rankLevel, topN, sinceDays)
    cached = _cache_get(ckey, fp)
    if cached is not None:
        return cached

    conds = []
    if menPai is not None:
        conds.append(LineupSnapshot.men_pai == menPai)
    if rankLevel is not None:
        conds.append(LineupSnapshot.rank_level == rankLevel)
    since = _since_cond(sinceDays)
    if since is not None:
        conds.append(since)

    q = select(LineupSnapshot.item_counts, LineupSnapshot.round_count)
    if conds:
        q = q.where(*conds)

    rows = (await db.execute(q)).all()

    counter: Counter = Counter()
    total_rounds = 0
    for item_counts, round_count in rows:
        total_rounds += (round_count or 0)
        if not item_counts:
            continue
        for item_id_str, cnt in item_counts.items():
            try:
                iid = int(item_id_str)
            except (TypeError, ValueError):
                continue
            counter[iid] += cnt

    # 折叠系列：成员合并为单一系列条目（key=系列 repId）
    folded, kmeta = fold_counter(counter)

    def _name(k):   return kmeta[k]["name"]     if k in kmeta else meta.item_name(k)
    def _rank(k):   return kmeta[k]["rank"]     if k in kmeta else meta.item_rank(k)
    def _career(k): return kmeta[k]["isCareer"] if k in kmeta else meta.is_career(k)
    def _type(k):   return kmeta[k]["type"]     if k in kmeta else meta.item_type(k)

    def _pct(c: int) -> float:
        return round(c / total_rounds * 100, 2) if total_rounds else 0.0

    # 按物品类型分桶（只放 count>0 的物品；系列按其代表类型归桶）
    by_type: dict[int, list[tuple[int, int]]] = {}
    for k, cnt in folded.items():
        if cnt <= 0:
            continue
        by_type.setdefault(_type(k), []).append((k, cnt))

    def _item(k: int, cnt: int) -> dict:
        return {
            "itemId": k,
            "name": _name(k),
            "count": cnt,
            "pct": _pct(cnt),
            "isCareer": _career(k),
            "rank": _rank(k),
        }

    types_out = []
    for t in sorted(by_type.keys()):
        bucket = sorted(by_type[t], key=lambda x: x[1], reverse=True)  # 按次数降序
        top = [_item(iid, cnt) for iid, cnt in bucket[:topN]]
        last = [_item(iid, cnt) for iid, cnt in bucket[-topN:]][::-1]  # 末 N，倒序成升序
        types_out.append({
            "type": t,
            "typeName": meta.item_type_name(t),
            "top": top,
            "last": last,
        })

    result = {"total_rounds": total_rounds, "types": types_out}
    _cache_put(ckey, fp, result)
    return result


def _gini(values: list[int]) -> float:
    """基尼系数：0=完全均衡，1=极端集中。"""
    v = sorted(values)
    n = len(v)
    s = sum(v)
    if s == 0 or n == 0:
        return 0.0
    cum = sum(i * x for i, x in enumerate(v, 1))
    return (2 * cum) / (n * s) - (n + 1) / n


@router.get("/usage-imbalance")
async def usage_imbalance(
    menPai: int | None = None,
    rankLevel: int | None = None,
    sinceDays: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按物品类型计算选用失衡度：基尼系数 + 偏冷物品清单。

    - 基尼系数：该类型内部选用集中度（>0.6 严重失衡 / 0.4~0.6 中度 / <0.4 均衡）。
    - 公平份额 = 1/N；偏冷 = 份额 < 公平份额×25%；严重偏冷 = < 公平份额×10%。
    - 仅返回物品数 N>=2 的类型，按基尼降序。统计口径与 usage-by-type 一致（折叠系列）。
    """
    fp = await _data_fingerprint(db)
    ckey = ("imbalance", menPai, rankLevel, sinceDays)
    cached = _cache_get(ckey, fp)
    if cached is not None:
        return cached

    conds = []
    if menPai is not None:
        conds.append(LineupSnapshot.men_pai == menPai)
    if rankLevel is not None:
        conds.append(LineupSnapshot.rank_level == rankLevel)
    since = _since_cond(sinceDays)
    if since is not None:
        conds.append(since)

    q = select(LineupSnapshot.item_counts)
    if conds:
        q = q.where(*conds)
    rows = (await db.execute(q)).all()

    counter: Counter = Counter()
    for (item_counts,) in rows:
        if not item_counts:
            continue
        for item_id_str, cnt in item_counts.items():
            try:
                iid = int(item_id_str)
            except (TypeError, ValueError):
                continue
            if is_excluded(iid):        # 稀缺物品不参与失衡统计
                continue
            counter[iid] += cnt

    folded, kmeta = fold_counter(counter)

    def _name(k):   return kmeta[k]["name"]     if k in kmeta else meta.item_name(k)
    def _rank(k):   return kmeta[k]["rank"]     if k in kmeta else meta.item_rank(k)
    def _type(k):   return kmeta[k]["type"]     if k in kmeta else meta.item_type(k)

    # 按类型分桶（只放 count>0）
    by_type: dict[int, list[tuple[int, int]]] = {}
    for k, cnt in folded.items():
        if cnt <= 0:
            continue
        by_type.setdefault(_type(k), []).append((k, cnt))

    types_out = []
    for t, bucket in by_type.items():
        N = len(bucket)
        if N < 2:
            continue
        tot = sum(c for _, c in bucket)
        fair = 1.0 / N
        gini = _gini([c for _, c in bucket])
        level = "severe" if gini >= 0.6 else "moderate" if gini >= 0.4 else "balanced"
        cold = []
        for k, c in sorted(bucket, key=lambda x: x[1]):   # 份额升序
            share = c / tot if tot else 0.0
            if share < fair * 0.25:
                cold.append({
                    "itemId": k,
                    "name": _name(k),
                    "rank": _rank(k),
                    "count": c,
                    "share": round(share * 100, 3),
                    "fairShare": round(fair * 100, 3),
                    "ratio": round(share / fair, 3) if fair else 0.0,
                    "severe": share < fair * 0.10,
                })
        types_out.append({
            "type": t,
            "typeName": meta.item_type_name(t),
            "itemCount": N,
            "gini": round(gini, 3),
            "level": level,
            "severeCount": sum(1 for x in cold if x["severe"]),
            "coldCount": len(cold),
            "cold": cold,
        })

    types_out.sort(key=lambda x: x["gini"], reverse=True)
    result = {"types": types_out, "excluded": EXCLUDED_ITEMS}
    _cache_put(ckey, fp, result)
    return result


@router.get("/career-top-imbalance")
async def career_top_imbalance(
    rankLevel: int | None = None,
    sinceDays: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """各门派职业物品「前3失衡」：每门派只取选用最高的前3个职业物品算基尼。

    业务依据：每门派职业物品里只有前3是本门派核心，第4名起是跨门派抓取的杂质。
    固定遍历全部门派（不接受 menPai 筛选），段位跟随 rankLevel。按基尼降序（最失衡置顶）。
    """
    fp = await _data_fingerprint(db)
    ckey = ("career-top", rankLevel, sinceDays)
    cached = _cache_get(ckey, fp)
    if cached is not None:
        return cached

    since = _since_cond(sinceDays)
    out = []
    for mp in MENPAI_LIST:
        conds = [LineupSnapshot.men_pai == mp]
        if rankLevel is not None:
            conds.append(LineupSnapshot.rank_level == rankLevel)
        if since is not None:
            conds.append(since)
        rows = (await db.execute(select(LineupSnapshot.item_counts).where(*conds))).all()

        counter: Counter = Counter()
        for (item_counts,) in rows:
            if not item_counts:
                continue
            for item_id_str, cnt in item_counts.items():
                try:
                    iid = int(item_id_str)
                except (TypeError, ValueError):
                    continue
                if is_excluded(iid):        # 稀缺物品不参与失衡统计
                    continue
                if meta.is_career(iid):
                    counter[iid] += cnt

        folded, kmeta = fold_counter(counter)

        def _name(k):  return kmeta[k]["name"] if k in kmeta else meta.item_name(k)
        def _rank(k):  return kmeta[k]["rank"] if k in kmeta else meta.item_rank(k)

        ranked = sorted(folded.items(), key=lambda x: x[1], reverse=True)[:3]
        if not ranked:
            continue
        tot3 = sum(c for _, c in ranked)
        gini = _gini([c for _, c in ranked])
        level = "severe" if gini >= 0.6 else "moderate" if gini >= 0.4 else "balanced"
        out.append({
            "menPai": mp,
            "menPaiName": meta.menpai_name(mp),
            "gini": round(gini, 3),
            "level": level,
            "items": [
                {
                    "itemId": k,
                    "name": _name(k),
                    "rank": _rank(k),
                    "count": c,
                    "share": round(c / tot3 * 100, 1) if tot3 else 0.0,
                }
                for k, c in ranked
            ],
        })

    out.sort(key=lambda x: x["gini"], reverse=True)
    result = {"menpais": out, "excluded": EXCLUDED_ITEMS}
    _cache_put(ckey, fp, result)
    return result
