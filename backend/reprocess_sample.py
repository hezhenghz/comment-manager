"""随机抽取 10 条评论重新跑 AI 分析，用于验证效果。
用法：在项目根目录执行
    .venv/Scripts/python backend/reprocess_sample.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from sqlalchemy import select, func
from app.database import async_session
from app.models import Comment
from app.ai.pipeline import run_pipeline
from app.ai.router import get_ai_router


async def main():
    async with async_session() as db:
        result = await db.execute(
            select(Comment).order_by(func.random()).limit(10)
        )
        comments = result.scalars().all()
        print(f"抽到 {len(comments)} 条，开始分析…\n")

        for i, c in enumerate(comments, 1):
            print(f"[{i}/10] 原文({c.content_lang})：{c.content[:80]}")
            await run_pipeline(c, db)
            print(f"       → 语言={c.content_lang}  情感={c.sentiment}  分类={c.category}")
            if c.translation:
                print(f"       → 翻译：{c.translation[:80]}")
            print()

        await db.commit()
        print("完成，已写入 DB。")


if __name__ == "__main__":
    asyncio.run(main())
