import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Comment


async def find_similar(comment: Comment, db: AsyncSession, threshold: float = 0.85) -> uuid.UUID | None:
    """Find an existing comment that is semantically similar to the new one."""
    if comment.embedding is None:
        return None
    vector_str = "[" + ",".join(str(v) for v in comment.embedding) + "]"
    q = (
        select(Comment.id)
        .where(
            Comment.game_id == comment.game_id,
            Comment.id != comment.id,
            Comment.embedding.isnot(None),
        )
        .order_by(Comment.embedding.cosine_distance(vector_str))
        .limit(1)
    )
    result = await db.execute(q)
    similar_id = result.scalar_one_or_none()
    return similar_id
