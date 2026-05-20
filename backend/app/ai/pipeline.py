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
    text = comment.content
    if not text or not text.strip():
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
