"""游戏更新公告同步调度。

- sync_announcements(game_id=None) : 同步单个或所有游戏的官方更新公告
- start_announcement_sync_scheduler(): 注册 APScheduler 定时任务
- get_sync_status()                 : 返回上次同步元信息

中文优先：抓取时已用 l=schinese，若正文检测为中文则直接入库；
否则调用翻译，把标题与正文译为中文（翻译保留 BBCode 标签只译文字），
入库前统一用 bbcode_to_html 转成 HTML 片段。
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from app.crawlers.steam.announcements import fetch_announcements
from app.crawlers.steam.bbcode import bbcode_to_html

logger = logging.getLogger(__name__)

# 上次同步元信息（内存缓存，重启后归零）
_last_sync_at: datetime | None = None
_last_sync_count: int = 0
_is_syncing: bool = False

# 翻译长正文用的 token 上限（公告正文可能较长）
_TRANSLATE_MAX_TOKENS = 4000


def get_sync_status() -> dict:
    return {
        "last_sync_at":    _last_sync_at.isoformat() if _last_sync_at else None,
        "last_sync_count": _last_sync_count,
        "is_syncing":      _is_syncing,
    }


def _looks_chinese(text: str) -> bool:
    """粗判是否中文为主：中文字符占比 > 20% 即认为是中文，省去无谓的 AI 调用。"""
    if not text:
        return False
    sample = text[:500]
    han = sum(1 for ch in sample if "一" <= ch <= "鿿")
    return han / max(len(sample), 1) > 0.20


async def _translate_keep_bbcode(text: str) -> str:
    """翻译为简体中文，保留 BBCode 标签只译文字。"""
    from app.ai.router import get_ai_router
    system = (
        "You are a translator. Translate the following game update announcement "
        "into Simplified Chinese (简体中文). The text contains BBCode tags like "
        "[h1][p][b][olist][*][url][img]. KEEP all BBCode tags and URLs/image links "
        "EXACTLY as-is, only translate the human-readable text between them. "
        "Output ONLY the translated text with tags preserved, no explanation."
    )
    router = get_ai_router()
    result = await router.chat(system, text, temperature=0.3,
                               max_tokens=_TRANSLATE_MAX_TOKENS)
    return result.strip()


async def _translate_title(text: str) -> str:
    from app.ai.router import get_ai_router
    system = (
        "Translate the following game announcement title into Simplified Chinese. "
        "Output ONLY the translated title, no explanation."
    )
    router = get_ai_router()
    result = await router.chat(system, text, temperature=0.3, max_tokens=200)
    return result.strip()


async def _process_one(game_id: uuid.UUID, item: dict) -> "GameAnnouncement":
    """把一条抓取结果转成 GameAnnouncement（含中文优先/翻译 + BBCode→HTML）。"""
    from app.models import GameAnnouncement

    title = item["title"]
    body = item["body"]
    is_chinese = _looks_chinese(title + " " + body)

    if is_chinese:
        title_zh = title
        body_zh = bbcode_to_html(body)
        is_translated = False
        lang = "zh"
    else:
        # 非中文：翻译标题 + 正文（保留 BBCode），再转 HTML
        try:
            title_zh = await _translate_title(title)
            translated_body = await _translate_keep_bbcode(body) if body else ""
            body_zh = bbcode_to_html(translated_body)
            is_translated = True
        except Exception as e:
            logger.warning(f"[announcement-sync] 翻译失败，回退原文: {e}")
            title_zh = title
            body_zh = bbcode_to_html(body)
            is_translated = False
        lang = "en"

    return GameAnnouncement(
        game_id=game_id,
        external_id=item["external_id"],
        title=title,
        title_zh=title_zh,
        body=body,
        body_zh=body_zh,
        is_translated=is_translated,
        lang=lang,
        published_at=item["published_at"],
        source_url=item["source_url"],
        fetched_at=datetime.utcnow(),
        raw_json={"language": item.get("language")},
    )


async def sync_announcements(game_id: str | None = None, limit: int | None = None) -> dict:
    """同步公告。game_id 为空时同步所有配置了 steam_app_id 的游戏。
    limit 不为空时为试爬：每个游戏只取最近 limit 条入库。
    返回 {"new": N, "error": None|str}。"""
    global _last_sync_at, _last_sync_count, _is_syncing

    if _is_syncing:
        return {"new": 0, "error": "同步进行中，请稍后"}

    _is_syncing = True
    new_count = 0
    error_msg = None

    try:
        from app.database import async_session
        from app.models import Game, GameAnnouncement

        async with async_session() as db:
            # 取目标游戏
            q = select(Game).where(Game.steam_app_id.isnot(None))
            if game_id:
                q = q.where(Game.id == game_id)
            games = (await db.execute(q)).scalars().all()

            for game in games:
                appid = (game.steam_app_id or "").strip()
                if not appid:
                    continue

                items = await fetch_announcements(appid)
                if not items:
                    continue

                # 试爬：只取最近 limit 条（接口已按时间倒序）
                if limit:
                    items = items[:limit]

                # 去重：已存在的 external_id 跳过
                ext_ids = [it["external_id"] for it in items]
                existing = set((await db.execute(
                    select(GameAnnouncement.external_id).where(
                        GameAnnouncement.game_id == game.id,
                        GameAnnouncement.external_id.in_(ext_ids),
                    )
                )).scalars())

                for it in items:
                    if it["external_id"] in existing:
                        continue
                    ann = await _process_one(game.id, it)
                    db.add(ann)
                    new_count += 1

            await db.commit()

        _last_sync_at = datetime.utcnow()
        _last_sync_count = new_count
        logger.info(f"[announcement-sync] 同步完成，新增 {new_count} 条")
    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"[announcement-sync] 同步失败: {e}\n{traceback.format_exc()}")
    finally:
        _is_syncing = False

    return {"new": new_count, "error": error_msg}


async def _sync_wrapper():
    """APScheduler 调用包装，捕获所有异常。"""
    try:
        await sync_announcements()
    except Exception as e:
        logger.error(f"[announcement-sync] 定时同步异常: {e}")


def start_announcement_sync_scheduler(interval_minutes: int = 60) -> None:
    """注册公告定时同步到主 APScheduler 实例。"""
    from app.crawlers.scheduler import scheduler

    if interval_minutes <= 0:
        logger.info("[announcement-sync] interval<=0，不启动定时同步")
        return

    scheduler.add_job(
        _sync_wrapper,
        trigger="interval",
        minutes=interval_minutes,
        id="announcement_sync",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"[announcement-sync] 已注册定时同步，间隔={interval_minutes}分钟")
