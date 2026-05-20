"""重新对所有评论运行 AI 分析（语言检测 / 情感 / 分类）。
只处理 sentiment IS NULL 的评论，可多次重跑续跑。
用法：在项目根目录执行
    .venv/Scripts/python backend/reprocess_ai.py
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from sqlalchemy import select, func
from app.database import async_session
from app.models import Comment
from app.ai.pipeline import run_pipeline
from app.ai.router import get_ai_router


BATCH_SIZE = 20


async def main():
    # Pre-trip primary circuit breaker — primary returns 500, skip it for 2h
    router = get_ai_router()
    router._primary_disabled_until = time.monotonic() + 7200
    router._primary_failures = 99
    print("已预开主路由熔断器，直接使用备用 AI。\n")

    async with async_session() as db:
        total = (await db.execute(
            select(func.count(Comment.id)).where(Comment.sentiment == None)
        )).scalar() or 0
        print(f"待分析（sentiment 为空）：{total} 条\n")

        done = 0
        errors = 0

        while True:
            result = await db.execute(
                select(Comment)
                .where(Comment.sentiment == None)
                .order_by(Comment.published_at.desc())
                .limit(BATCH_SIZE)
            )
            comments = result.scalars().all()
            if not comments:
                break

            for c in comments:
                try:
                    await run_pipeline(c, db)
                    done += 1
                    print(f"[{done}/{total}] {c.id}  情感={c.sentiment}  分类={c.category}  语言={c.content_lang}")
                except Exception as e:
                    errors += 1
                    print(f"[err {errors}] {c.id}  ✗ {e}")

            await db.commit()
            await asyncio.sleep(0.5)

    print(f"\n完成：成功 {done} 条，失败 {errors} 条。")


if __name__ == "__main__":
    asyncio.run(main())
