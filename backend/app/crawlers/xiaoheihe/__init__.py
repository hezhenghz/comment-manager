"""
小黑盒 (xiaoheihe.cn) 游戏评价爬虫

原理：
  使用 Playwright 持久化浏览器 Profile，保留真实登录态（含 HttpOnly Cookie）。
  首次使用需运行 backend/setup_xiaoheihe_browser.py 完成手动登录。

  抓取策略：
    1. 打开游戏评价页，等待页面自然发出第一个带签名的 comments 请求
    2. 拦截该请求，提取完整 URL（含 hkey/nonce/_time/limit 等参数）
    3. 复用这些参数，通过 page.evaluate(fetch) 分页拉取后续页
       - offset 从 0 开始，每次递增签名 URL 里的 limit 值（实测为 10）
       - 不依赖响应里的 total_page（该字段不可信，实测固定返回 100）
       - 终止条件：items 为空，或连续 2 次请求无新增条目

  分页注意事项（踩坑记录）：
    - total_page 不可信：API 无论实际条数多少，total_page 始终返回 100，
      用它来判断最后一页会导致提前退出。
    - 每页实际条数由签名 URL 里的 limit 参数决定（实测值为 10，非 30）。
      若用硬编码步长（如 30）递增 offset，会跳过中间的条目。
    - 正确做法：从签名 URL 中读取 limit → 作为 offset 步长；
      结束判断仅依赖 items 是否为空 + 连续空批次计数。

  Windows 兼容说明：
    uvicorn 在 Windows 使用 SelectorEventLoop，不支持 create_subprocess_exec。
    playwright 必须通过该接口启动浏览器进程。
    解决方案：在独立的 ThreadPoolExecutor 线程里创建 ProactorEventLoop，
    在该 loop 里运行 async_playwright，与 uvicorn 主 loop 完全隔离。

Profile 路径：
  默认：backend/.browser_profiles/xiaoheihe/
  可通过环境变量 XIAOHEIHE_PROFILE_DIR 覆盖。

游戏 ID 规则：
  小黑盒使用 Steam App ID 作为游戏 key。
"""

import asyncio
import functools
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from app.crawlers.base import BaseCrawler, FetchedComment

logger = logging.getLogger(__name__)

_BASE_URL      = "https://www.xiaoheihe.cn"
_API_HOST      = "api.xiaoheihe.cn"
_COMMENTS_PATH = "/bbs/app/link/game/comments"
_PER_PAGE      = 10   # 备用默认值；实际页大小以签名 URL 里的 limit 参数为准
_PAGE_DELAY    = 0.8
_MAX_PAGES     = 300
_INIT_WAIT     = 6.0

_DEFAULT_PROFILE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".browser_profiles", "xiaoheihe"
)

# 独立线程池：每次爬取在此线程内创建自己的 ProactorEventLoop
_playwright_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xiaoheihe")


def _get_profile_dir() -> str:
    return os.path.abspath(
        os.getenv("XIAOHEIHE_PROFILE_DIR", _DEFAULT_PROFILE_DIR)
    )


def _extract_items(data: dict) -> list:
    result = data.get("result") or {}
    return (
        result.get("links")
        or result.get("list")
        or result.get("items")
        or (data.get("data") or {}).get("list")
        or []
    )


def _crawl_in_thread(game_app_id: str, since: datetime | None, limit: int | None) -> list[FetchedComment]:
    """在独立线程里用 ProactorEventLoop 运行 playwright，避免与 uvicorn 的 SelectorEventLoop 冲突。

    背景：uvicorn 在 Windows 使用 SelectorEventLoop，该 loop 不支持 create_subprocess_exec，
    但 playwright 启动浏览器进程必须通过此接口。直接在 uvicorn 的 loop 里调用 async_playwright
    会抛出 NotImplementedError。
    解决方案：在 ThreadPoolExecutor 线程里显式创建 ProactorEventLoop 并在其中运行 playwright，
    两个 loop 互相隔离，不影响 uvicorn 的正常工作。
    """
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_fetch_async(game_app_id, since, limit))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _fetch_async(
    game_app_id: str,
    since: datetime | None,
    limit: int | None,
) -> list[FetchedComment]:
    profile_dir = _get_profile_dir()

    if not os.path.isdir(profile_dir):
        logger.error(
            "[xiaoheihe] 未找到浏览器 Profile，请先运行登录初始化脚本：\n"
            "    .venv/Scripts/python backend/setup_xiaoheihe_browser.py"
        )
        return []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[xiaoheihe] 未安装 playwright")
        return []

    if not game_app_id:
        logger.warning("[xiaoheihe] game_app_id 为空，跳过")
        return []

    captured_items: list[dict] = []
    seen_ids: set[str] = set()

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        # ── 拦截第一个带签名的 comments 请求 URL ────────────────────────
        first_signed_url: list[str] = []

        def on_request(req):
            if (_COMMENTS_PATH in req.url
                    and _API_HOST in req.url
                    and not first_signed_url):
                first_signed_url.append(req.url)
                logger.info(f"[xiaoheihe] 捕获签名 URL: {req.url[:120]}…")

        page.on("request", on_request)

        # ── 打开游戏评价页 ────────────────────────────────────────────────
        game_url = f"{_BASE_URL}/app/topic/game/pc/{game_app_id}"
        logger.info(f"[xiaoheihe] 打开: {game_url}")
        try:
            await page.goto(game_url, wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            pass

        await asyncio.sleep(2.0)
        final_url = page.url
        logger.info(f"[xiaoheihe] 落地 URL: {final_url}")

        if any(k in final_url for k in ["/login", "passport", "/bbs/home"]):
            logger.error("[xiaoheihe] 登录态已过期，请重新运行登录初始化脚本")
            await context.close()
            return []

        logger.info(f"[xiaoheihe] 等待 {_INIT_WAIT}s 让页面加载评论…")
        await asyncio.sleep(_INIT_WAIT)

        if not first_signed_url:
            logger.info("[xiaoheihe] 未捕获到首次请求，尝试点击评价 tab…")
            for selector in ["text=评价", "text=用户评价", "[class*='tab'][class*='comment']"]:
                try:
                    await page.click(selector, timeout=2_000)
                    await asyncio.sleep(3.0)
                    if first_signed_url:
                        break
                except Exception:
                    continue

        if not first_signed_url:
            logger.error("[xiaoheihe] 未能捕获到评论 API 请求，无法获取签名参数")
            await context.close()
            return []

        # ── 复用签名参数从 offset=0 开始分页拉取 ────────────────────────
        parsed = urlparse(first_signed_url[0])
        base_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        # API 实际每页条数由签名 URL 里的 limit 参数决定（可能为 10 而非 30）
        actual_page_size = int(base_params.get("limit", _PER_PAGE))
        logger.info(f"[xiaoheihe] 实际每页条数={actual_page_size}")

        max_pages = (
            min((limit // actual_page_size) + 2, _MAX_PAGES) if limit else _MAX_PAGES
        )

        next_offset = 0        # 当前页 offset；优先用 API 返回的 next_offset 游标更新
        consecutive_empty = 0  # 连续无新增次数，防止死循环

        for page_idx in range(max_pages):
            if limit and len(captured_items) >= limit:
                break

            base_params["offset"] = str(next_offset)
            api_url = urlunparse(parsed._replace(query=urlencode(base_params)))

            try:
                data = await page.evaluate(f"""
                    async () => {{
                        const r = await fetch("{api_url}", {{
                            credentials: "include",
                            headers: {{
                                "Accept": "application/json, text/plain, */*",
                                "Referer": "{game_url}"
                            }}
                        }});
                        return r.json();
                    }}
                """)
            except Exception as e:
                logger.warning(f"[xiaoheihe] fetch 失败 offset={next_offset}: {e}")
                break

            if not isinstance(data, dict):
                logger.warning(f"[xiaoheihe] 响应格式异常: {data}")
                break

            status = data.get("status") or data.get("code")
            if status and str(status) not in ("ok", "200", "0"):
                logger.warning(f"[xiaoheihe] API 错误 status={status} offset={next_offset}")
                break

            result_block = data.get("result") or {}
            total_page = result_block.get("total_page")
            api_next   = result_block.get("next_offset")
            items = _extract_items(data)

            if not items:
                logger.info(f"[xiaoheihe] offset={next_offset} 无更多数据，结束")
                break

            new_in_batch = 0
            hit_since = False
            for item in items:
                ext_id = str(item.get("linkid") or item.get("link_id") or item.get("id") or "")
                if not ext_id or ext_id in seen_ids:
                    continue
                if since:
                    ts = item.get("create_at") or item.get("create_time") or item.get("created_at") or 0
                    if ts and datetime.fromtimestamp(ts) < since:
                        hit_since = True
                        break
                seen_ids.add(ext_id)
                captured_items.append(item)
                new_in_batch += 1

            logger.info(
                f"[xiaoheihe] offset={next_offset} 返回 {len(items)} 条，"
                f"total_page={total_page}, new={new_in_batch}，累计 {len(captured_items)} 条"
            )

            if hit_since:
                logger.info("[xiaoheihe] 已到 since 截止点，停止")
                break

            # 连续 2 次无新增 → API 已无更多数据或在重复返回同一页
            if new_in_batch == 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info("[xiaoheihe] 连续 2 次无新增，停止翻页")
                    break
            else:
                consecutive_empty = 0

            # 优先使用 API 返回的游标 next_offset；否则按实际页大小递增
            next_offset = int(api_next) if api_next is not None else next_offset + actual_page_size

            await asyncio.sleep(_PAGE_DELAY)

        await context.close()

    # ── 转换为 FetchedComment ────────────────────────────────────────────
    results: list[FetchedComment] = []
    for item in captured_items:
        if limit and len(results) >= limit:
            break

        ts = item.get("create_at") or item.get("create_time") or item.get("created_at") or 0
        published_at = datetime.fromtimestamp(ts) if ts else None

        if since and published_at and published_at < since:
            continue

        rating = item.get("score") or item.get("rating") or item.get("star")
        user   = item.get("user") or item.get("account") or {}
        author = (
            user.get("nickname")
            or user.get("name")
            or str(user.get("heybox_id") or "")
            or "匿名"
        )

        content = (item.get("description") or item.get("content") or item.get("text") or "").strip()

        ext_id = str(item.get("linkid") or item.get("link_id") or item.get("id") or "")
        results.append(
            FetchedComment(
                platform="xiaoheihe",
                source_type="review",
                external_id=ext_id or None,
                source_url=f"{_BASE_URL}/app/topic/game/pc/{game_app_id}",
                author_name=author,
                content=content,
                published_at=published_at,
                thumbs_up=int(rating) if rating is not None else None,
                thumbs_down=None,
                raw_json=item,
            )
        )

    logger.info(f"[xiaoheihe] 抓取完成，共 {len(results)} 条")
    return results


class XiaoheiheCrawler(BaseCrawler):
    platform = "xiaoheihe"

    async def fetch(
        self,
        game_app_id: str,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[FetchedComment]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _playwright_pool,
            functools.partial(_crawl_in_thread, game_app_id, since, limit),
        )

    async def validate(self, game_app_id: str) -> bool:
        return bool(game_app_id and game_app_id.strip())
