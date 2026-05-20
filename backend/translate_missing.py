"""
批量补翻译脚本

找出所有 content_lang 非中文且 translation 为空的评论，逐条翻译并写回 DB。

用法（在 backend/ 目录下运行）：
    python translate_missing.py
    python translate_missing.py --concurrency 3
    python translate_missing.py --dry-run
"""

import asyncio
import argparse
import sys
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, ".")
from app.config import get_settings
from app.models import Comment
from app.ai.translate import translate_to_chinese

CHINESE_LANGS = {"zh-cn", "zh-tw", "zh"}


async def fetch_pending(session: AsyncSession) -> list:
    q = (
        select(Comment.id, Comment.content, Comment.content_lang)
        .where(
            Comment.translation.is_(None),
            Comment.content.isnot(None),
            Comment.content_lang.notin_(CHINESE_LANGS),
            Comment.content_lang.isnot(None),
            Comment.content_lang != "unknown",
        )
        .order_by(Comment.fetched_at.desc())
    )
    result = await session.execute(q)
    return result.all()


async def translate_one(
    semaphore: asyncio.Semaphore,
    Session: async_sessionmaker,
    row,
    idx: int,
    total: int,
) -> bool:
    comment_id, content, lang = row
    async with semaphore:
        try:
            translation = await translate_to_chinese(content)
            if not translation.strip():
                logger.warning(f"[{idx}/{total}] id={comment_id} 结果为空，跳过")
                return False
            async with Session() as session:
                await session.execute(
                    update(Comment)
                    .where(Comment.id == comment_id)
                    .values(translation=translation)
                )
                await session.commit()
            logger.info(f"[{idx}/{total}] ✓ {lang} id={comment_id}")
            return True
        except Exception as e:
            logger.error(f"[{idx}/{total}] ✗ id={comment_id}: {e}")
            return False


async def main(concurrency: int, dry_run: bool):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        pending = await fetch_pending(session)

    total = len(pending)
    if total == 0:
        logger.info("没有待翻译的评论，退出。")
        await engine.dispose()
        return

    logger.info(f"共找到 {total} 条待翻译评论（并发={concurrency}）")
    if dry_run:
        logger.info("--dry-run 模式，不实际翻译。")
        await engine.dispose()
        return

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        translate_one(semaphore, Session, row, idx, total)
        for idx, row in enumerate(pending, 1)
    ]
    results = await asyncio.gather(*tasks)
    success = sum(1 for r in results if r)
    logger.info(f"完成：成功 {success}/{total}，失败 {total - success}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.concurrency, args.dry_run))
