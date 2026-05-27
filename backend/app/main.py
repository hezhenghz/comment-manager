import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if not exists (dev convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 清理上次进程残留的幽灵 running job，再启动调度器
    from app.crawlers.scheduler import start_scheduler, cleanup_orphan_jobs
    await cleanup_orphan_jobs()
    start_scheduler()
    yield
    await engine.dispose()


app = FastAPI(title="Comment Manager", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Bearer token via Authorization header，无需 Cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
from app.api.auth import router as auth_router
from app.api.games import router as games_router
from app.api.comments import router as comments_router
from app.api.search import router as search_router
from app.api.dashboard import router as dashboard_router
from app.api.crawlers import router as crawlers_router
from app.api.topics import router as topics_router
from app.api.requirements import router as requirements_router
from app.api.chat import router as chat_router

app.include_router(auth_router)
app.include_router(games_router)
app.include_router(comments_router)
app.include_router(search_router)
app.include_router(dashboard_router)
app.include_router(crawlers_router)
app.include_router(topics_router)
app.include_router(requirements_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
