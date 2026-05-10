"""Management script for Comment Manager."""
import asyncio
import sys
from app.auth import hash_password
from app.config import get_settings
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

settings = get_settings()
engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def add_user(username: str, password: str, display_name: str):
    from app.models import User
    async with session_factory() as db:
        user = User(username=username, password_hash=hash_password(password), display_name=display_name)
        db.add(user)
        await db.commit()
        print(f"User '{username}' created.")


async def list_users():
    from app.models import User
    async with session_factory() as db:
        result = await db.execute(select(User))
        for u in result.scalars():
            print(f"  {u.username} ({u.display_name}) - {u.id}")


async def init_db():
    from app.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")


async def add_pgvector():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    print("pgvector extension enabled.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command> [args...]")
        print("Commands:")
        print("  adduser <username> <password> <display_name>")
        print("  listusers")
        print("  initdb")
        print("  enable_vector")
        return

    cmd = sys.argv[1]
    if cmd == "adduser":
        asyncio.run(add_user(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == "listusers":
        asyncio.run(list_users())
    elif cmd == "initdb":
        asyncio.run(init_db())
    elif cmd == "enable_vector":
        asyncio.run(add_pgvector())
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
