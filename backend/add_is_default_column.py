"""
临时脚本：给 games 表新增 is_default 字段（默认游戏标记）
在项目根目录执行：
  .venv\\Scripts\\python.exe backend\\add_is_default_column.py
"""
import asyncio
from app.database import engine
from sqlalchemy import text


async def main():
    async with engine.begin() as conn:
        try:
            await conn.execute(text(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS "
                "is_default BOOLEAN NOT NULL DEFAULT false"
            ))
            print("OK: is_default")
        except Exception as e:
            print(f"SKIP is_default: {e}")
    print("完成！")


asyncio.run(main())
