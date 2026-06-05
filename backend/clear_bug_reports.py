"""
临时脚本：清空 bug_reports 表
用法：在 backend 目录下执行
  .venv\Scripts\python.exe clear_bug_reports.py
"""
import asyncio
from app.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE bug_reports"))
        print("bug_reports 表已清空！")

asyncio.run(main())
