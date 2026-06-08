"""
临时脚本：给 bug_reports 表新增 4 个文件下载链接字段
在项目根目录执行：
  .venv\Scripts\python.exe backend\add_bug_columns.py
"""
import asyncio
from app.database import engine
from sqlalchemy import text

async def main():
    cols = ["screenshot_url", "save_url", "log_url", "prev_log_url"]
    async with engine.begin() as conn:
        for col in cols:
            try:
                await conn.execute(text(
                    f"ALTER TABLE bug_reports ADD COLUMN IF NOT EXISTS {col} VARCHAR(1024)"
                ))
                print(f"OK: {col}")
            except Exception as e:
                print(f"SKIP {col}: {e}")
    print("完成！")

asyncio.run(main())
