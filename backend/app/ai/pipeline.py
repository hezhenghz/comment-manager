import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Comment
from app.utils.lang import detect_lang
from app.ai.sentiment import analyze_sentiment
from app.ai.classifier import classify
from app.ai.summarizer import summarize
from app.ai.embedding import generate_embedding
from app.ai.dedup import find_similar

logger = logging.getLogger(__name__)


async def run_pipeline(comment: Comment, db: AsyncSession) -> None:
    """Run the full AI analysis pipeline on a new comment."""
    text = comment.content
    if not text or not text.strip():
        return

    try:
        comment.content_lang = detect_lang(text)
    except Exception:
        comment.content_lang = "unknown"

    try:
        sentiment, score = await analyze_sentiment(text)
        comment.sentiment = sentiment
        comment.sentiment_score = score
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")

    try:
        comment.category = await classify(text)
    except Exception as e:
        logger.warning(f"Classification failed: {e}")

    try:
        comment.summary = await summarize(text)
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")

    try:
        embedding = await generate_embedding(text)
        if embedding:
            comment.embedding = embedding
            similar_id = await find_similar(comment, db)
            if similar_id:
                comment.is_duplicate = True
                comment.duplicate_of = similar_id
    except Exception as e:
        logger.warning(f"Embedding/dedup failed: {e}")
