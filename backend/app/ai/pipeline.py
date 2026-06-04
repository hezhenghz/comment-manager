import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Comment
from app.ai.sentiment import analyze_sentiment
from app.ai.classifier import classify
from app.ai.lang_detect import detect_lang
from app.ai.translate import translate_to_chinese

logger = logging.getLogger(__name__)

_ZH = {"zh-cn", "zh-tw"}


async def run_pipeline(comment: Comment, db: AsyncSession) -> None:
    """单条评论的 AI 分析 pipeline。

    - Discord 平台：先调 filter_game_feedback 判定是否游戏反馈；False 则标 'skipped' 直接返回。
    - 其他平台或已判定为 True 的 Discord 评论：跑 lang/sentiment/classify/translate。
    - 若所有主要 AI 子任务（sentiment + category）都失败，抛 RuntimeError 让 worker 重试。
    - 注意：本函数只写 comment 字段，**不** commit；由调用方决定提交时机。
    """
    text = comment.content
    if not text or not text.strip():
        return

    # ── Discord 过滤器（仅对未判定过的 Discord 消息）─────────────────────
    # 过滤器内部已包 try/except 异常时全保留，所以这里不会抛错。
    if comment.platform == "discord" and comment.is_game_feedback is None:
        from app.ai.discord_filter import filter_game_feedback
        flags = await filter_game_feedback([text])
        keep = bool(flags and flags[0])
        comment.is_game_feedback = keep
        if not keep:
            comment.ai_status = "skipped"
            comment.last_ai_error = None
            comment.next_ai_attempt_at = None
            return

    # 第一阶段：语言检测（其他分析依赖结果）
    try:
        comment.content_lang = await detect_lang(text)
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")

    # 第二阶段：情感 / 分类 / 翻译（非中文时）并行
    async def _sentiment():
        try:
            sentiment, score = await analyze_sentiment(text)
            comment.sentiment = sentiment
            comment.sentiment_score = score
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")

    async def _classify():
        try:
            comment.category = await classify(text)
        except Exception as e:
            logger.warning(f"Classification failed: {e}")

    async def _translate():
        try:
            comment.translation = await translate_to_chinese(text)
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

    tasks = [_sentiment(), _classify()]
    if comment.content_lang and comment.content_lang not in _ZH:
        tasks.append(_translate())

    await asyncio.gather(*tasks)

    # 主要子任务全失败 → 抛错让 worker 走重试+退避（避免"AI 挂时跑过的消息永远缺分析"）
    if comment.sentiment is None and comment.category is None:
        raise RuntimeError("pipeline 主要 AI 子任务全部失败（sentiment + category 均为空）")
