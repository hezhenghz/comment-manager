"""AI 影子预判：判断一条新条目策划会"采纳"还是"不采纳"。

检索式学习（无训练）：
- 检索该游戏历史上策划处理过的、语义最相似的 K 条决定作为 few-shot 例子。
- 把例子 + 当前条目喂给 AI，返回 采纳/不采纳。
- 结果只写库（curation_decisions.ai_prediction），不返回给处理列表前端（影子模式）。

冷启动：该游戏已被策划处理（decision != 'pending'）的样本 < 100 时不预判。
只对新条目调用（评论 pipeline 末尾 / 话题 / BUG上报 入库后）。
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding import generate_embedding
from app.ai.router import get_ai_router
from app.models import CurationDecision

logger = logging.getLogger(__name__)

# 冷启动门槛：处理样本不足此数不预判
_COLD_START_MIN = 100
# few-shot 检索条数
_K = 5
# cosine 距离上限（> 此值视为不相似，丢弃；cosine_distance ∈ [0,2]，越小越像）
_MAX_DISTANCE = 0.4

_SYSTEM = (
    "你是游戏运营策划助手。根据历史上策划对相似玩家反馈的处理决定（采纳/不采纳），"
    "判断当前这条反馈策划会如何处理。\n"
    "“采纳”=值得排进需求/待办；“不采纳”=无需处理（无意义、重复、已知、不可行等）。\n"
    "只回复两个词之一：采纳 或 不采纳。不要解释。"
)

_DECISION_CN = {"adopted": "采纳", "rejected": "不采纳"}
_CN_DECISION = {"采纳": "adopted", "不采纳": "rejected"}


async def _processed_count(db: AsyncSession, game_id: uuid.UUID) -> int:
    q = select(func.count(CurationDecision.id)).where(
        CurationDecision.game_id == game_id,
        CurationDecision.decision != "pending",
    )
    return (await db.execute(q)).scalar() or 0


async def _get_or_create(db: AsyncSession, source_type: str, source_id: uuid.UUID,
                         game_id: uuid.UUID) -> CurationDecision:
    row = (await db.execute(
        select(CurationDecision).where(CurationDecision.source_id == source_id)
    )).scalar_one_or_none()
    if row is None:
        row = CurationDecision(
            game_id=game_id, source_type=source_type,
            source_id=source_id, decision="pending",
        )
        db.add(row)
    return row


async def predict_decision(
    source_type: str,
    source_id: uuid.UUID,
    text: str,
    game_id: uuid.UUID,
    db: AsyncSession,
) -> str | None:
    """对一条条目做影子预判并写库。返回 'adopted'/'rejected'/None（未预判）。
    全程容错，失败返回 None 不影响主流程。"""
    try:
        if not text or not text.strip():
            return None

        # 冷启动门槛
        if await _processed_count(db, game_id) < _COLD_START_MIN:
            return None

        # 生成向量
        emb = await generate_embedding(text[:1000])
        if not emb:
            return None
        vector_str = "[" + ",".join(str(v) for v in emb) + "]"

        # 检索相似历史决定（同游戏、已处理、带 embedding、距离够近）
        dist = CurationDecision.embedding.cosine_distance(vector_str)
        q = (
            select(CurationDecision.source_snapshot, CurationDecision.decision, dist.label("d"))
            .where(
                CurationDecision.game_id == game_id,
                CurationDecision.decision != "pending",
                CurationDecision.embedding.isnot(None),
                CurationDecision.source_id != source_id,
            )
            .order_by(dist)
            .limit(_K)
        )
        rows = (await db.execute(q)).all()
        examples = [(snap, dec) for snap, dec, d in rows if d is not None and d <= _MAX_DISTANCE]
        if not examples:
            return None  # 没有足够相似的历史样本，不强行预判

        # 组 few-shot prompt
        lines = ["历史处理示例："]
        for i, (snap, dec) in enumerate(examples, 1):
            snippet = _snapshot_text(snap)[:200]
            lines.append(f"{i}. 反馈：{snippet}\n   策划处理：{_DECISION_CN.get(dec, dec)}")
        lines.append("\n当前反馈：")
        lines.append(text[:500])
        lines.append("\n策划会如何处理？只回复：采纳 或 不采纳")
        user_prompt = "\n".join(lines)

        router = get_ai_router()
        result = (await router.chat(_SYSTEM, user_prompt, temperature=0.1, max_tokens=10)).strip()
        prediction = _CN_DECISION.get(result[:3], None) or _CN_DECISION.get(result, None)
        if prediction is None:
            # 兜底：从结果里找关键词
            if "不采纳" in result:
                prediction = "rejected"
            elif "采纳" in result:
                prediction = "adopted"
            else:
                return None

        # 写库（惰性建行 + 存 embedding/snapshot 供后续作为样本）
        row = await _get_or_create(db, source_type, source_id, game_id)
        row.ai_prediction = prediction
        row.ai_predicted_at = datetime.utcnow()
        if row.embedding is None:
            row.embedding = emb
        if not row.source_snapshot:
            row.source_snapshot = {"text": text[:500]}
        await db.commit()
        return prediction
    except Exception as e:
        logger.warning(f"[curation_predict] {source_type}/{source_id} 预判失败: {e}")
        try:
            await db.rollback()
        except Exception:
            pass
        return None


def _snapshot_text(snap: dict) -> str:
    """从快照里抽出可读文本。"""
    if not snap:
        return ""
    for key in ("text", "content", "title", "summary"):
        v = snap.get(key)
        if v:
            return str(v)
    return str(snap)
