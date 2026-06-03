"""
Dump BUG上报爬虫
目标：http://dump.om.dianhun.cn  前置 AMS SSO

认证流程：
  1. 优先使用 ZENTAO_COOKIE（格式：PHPSESSID=xxx; user_name=xxx; user_key=xxx; product_id=xxx）
  2. 若未配置 cookie，则用 Playwright 自动化浏览器登录 AMS SSO
  3. 登录后获取 PHPSESSID/user_name/user_key/product_id cookies
  4. 导航到 xkbb 产品页（设置 product_id cookie）
  5. API 格式：index.php?/dump2_mobile/dump_list?date1=YYYY-MM-DD&gid=ID250001&page=N
  6. 数据嵌入在 HTML 页面中：var data = [...]
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# 游戏 ID（侠客帮帮 = xkbb）
GID = "ID250001"

# dump 服务器基地址
DUMP_SERVER_BASE = "http://dumpserver.dhom.m3guo.com:9527/"


class ZenTaoCrawler:
    """Dump BUG上报爬虫（Playwright SSO 登录 + httpx 数据抓取）"""

    def __init__(self):
        self.settings = get_settings()
        self._cookies: dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._base = self.settings.zentao_url.rstrip("/")

    # ── 公共接口 ─────────────────────────────────────────────────────────────

    async def ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                cookies=self._cookies,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def login(self) -> bool:
        """获取有效 session。优先 cookie 配置，其次 Playwright 自动登录。"""
        # 1. 手动 cookie 优先
        if self.settings.zentao_cookie:
            self._cookies = _parse_cookie_string(self.settings.zentao_cookie)
            if self._cookies:
                logger.info("[dump] 使用手动 ZENTAO_COOKIE 认证")
                return True

        # 2. 用户名密码 → Playwright 自动化
        if self.settings.zentao_username and self.settings.zentao_password:
            return await self._login_with_playwright()

        logger.warning("[dump] 未配置认证信息，请设置 ZENTAO_COOKIE 或 ZENTAO_USERNAME/PASSWORD")
        return False

    async def _login_with_playwright(self) -> bool:
        """用 Playwright 完成 AMS SSO 登录，提取所有必要 cookies。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("[dump] playwright 未安装，无法自动登录")
            return False

        logger.info("[dump] 启动 Playwright 进行 AMS SSO 登录...")
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = await ctx.new_page()

                # 1. 访问主页 → 重定向到 AMS 登录
                logger.info(f"[dump] 访问 {self._base}")
                await page.goto(self._base, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                logger.info(f"[dump] 当前页面: {page.url}")

                # 2. 切换到账号密码登录 tab（默认是扫码登录）
                if "ams.om.dianhun.cn" in page.url or "login" in page.url.lower():
                    logger.info("[dump] 正在切换到账号密码登录...")
                    try:
                        await page.click("div.vui-login-modal-toggler.account", timeout=8000)
                        await page.wait_for_timeout(500)
                    except Exception as e:
                        logger.warning(f"[dump] 切换 tab 失败: {e}，尝试继续...")

                    # 3. 填入账号密码
                    logger.info("[dump] 填写账号密码...")
                    await page.fill("input.input-text[type='text']", self.settings.zentao_username)
                    await page.fill("input.input-text[type='password']", self.settings.zentao_password)

                    # 4. 点击登录
                    await page.click("button.submit", timeout=5000)
                    logger.info("[dump] 已点击登录")
                    await page.wait_for_timeout(3000)

                    # 5. 处理"密码长期未修改"弹窗
                    try:
                        ignore_btn = page.locator("text=忽略").first
                        if await ignore_btn.count() > 0:
                            await ignore_btn.click()
                            logger.info("[dump] 已关闭密码修改提示")
                            await page.wait_for_timeout(2000)
                    except Exception:
                        pass

                logger.info(f"[dump] 登录后页面: {page.url}")

                # 6. 导航到 xkbb 产品页（设置 product_id cookie）
                await page.goto(
                    f"{self._base}/index.php?/index/index?product=xkbb",
                    wait_until="networkidle",
                    timeout=15000,
                )
                await page.wait_for_timeout(1000)
                logger.info(f"[dump] xkbb 产品页: {page.url}")

                # 7. 提取所有 dump.om.dianhun.cn 的 cookies
                all_cookies = await ctx.cookies()
                dump_cookies = {
                    c["name"]: c["value"]
                    for c in all_cookies
                    if "dump.om.dianhun.cn" in c.get("domain", "")
                }

                if "PHPSESSID" in dump_cookies:
                    self._cookies = dump_cookies
                    logger.info(
                        f"[dump] 成功获取 cookies: {list(dump_cookies.keys())}, "
                        f"PHPSESSID={dump_cookies['PHPSESSID'][:10]}..."
                    )
                    await browser.close()
                    return True

                logger.warning(
                    f"[dump] 未找到 PHPSESSID，现有 cookies: "
                    f"{[c['name'] for c in all_cookies]}"
                )
                await browser.close()
                return False

        except Exception as e:
            logger.error(f"[dump] Playwright 登录失败: {e}")
            return False

    async def get_product_id(self) -> str:
        """返回 xkbb 的游戏 ID。"""
        return GID

    async def fetch_bugs(
        self,
        page: int = 1,
        per_page: int = 100,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """
        抓取 Dump 上报列表（按日期范围分页）。
        since 若指定则抓取 since 之后的数据，否则抓取最近 7 天。
        """
        client = await self.ensure_client()
        # 同步最新 cookies
        for name, val in self._cookies.items():
            client.cookies.set(name, val)

        # 确定日期范围
        today = datetime.now()
        if since:
            date1 = since
        else:
            date1 = today - timedelta(days=7)

        # 按天抓取（避免单次请求数据量过大）
        all_bugs: list[dict] = []
        current = date1.date()
        end_date = today.date()

        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            day_bugs = await self._fetch_day(client, date_str)
            all_bugs.extend(day_bugs)
            logger.info(f"[dump] {date_str}: {len(day_bugs)} 条记录")
            current += timedelta(days=1)

        return all_bugs

    async def _fetch_day(
        self, client: httpx.AsyncClient, date_str: str
    ) -> list[dict]:
        """抓取某一天的所有 dump 记录（自动翻页）。

        使用 date1=date_str&date2=date_str+23:59 来精确限定当天的记录，
        避免 date1 单独使用时返回该日之后所有记录的问题。
        """
        results: list[dict] = []
        page_num = 1
        # date2 设置为当天 23:59:59，确保只返回当天记录
        date2_str = f"{date_str} 23:59:59"

        while True:
            url = (
                f"{self._base}/index.php?/dump2_mobile/dump_list"
                f"?date1={date_str}&date2={date2_str}&gid={GID}&page={page_num}"
            )
            try:
                resp = await client.get(url)
            except Exception as e:
                logger.debug(f"[dump] GET {url[:60]} 失败: {e}")
                break

            # 被重定向到登录页 → session 过期
            if (
                resp.status_code != 200
                or "production_list" in str(resp.url)
                or "login" in str(resp.url).lower()
            ):
                logger.warning("[dump] Session 已过期，需要重新登录")
                break

            records = _extract_json_data(resp.text)
            if not records:
                break  # 无数据或最后一页

            results.extend([self._parse_bug(r) for r in records if isinstance(r, dict)])

            # 如果本页记录数 < 20，说明是最后一页
            if len(records) < 20:
                break

            page_num += 1
            if page_num > 50:  # 安全上限
                logger.warning(f"[dump] {date_str} 超过 50 页，停止")
                break

        return results

    def _parse_bug(self, raw: dict) -> dict:
        """将 dump 记录映射到 BugReport 字段。"""
        dump_id = str(raw.get("id", ""))
        game_state = str(raw.get("GameState", "") or "").strip()
        logtype = str(raw.get("logtype", "") or "").strip()
        model = str(raw.get("model", "") or "").strip()
        osversion = str(raw.get("osversion", "") or "").strip()
        gameversion = str(raw.get("gameversion", "") or "").strip()
        uuid = str(raw.get("uuid", "") or "").strip()
        time_str = str(raw.get("time", "") or "").strip()
        file_path = str(raw.get("file_path", "") or "").strip()
        file_size = str(raw.get("file_size", "") or "").strip()

        # 标题：优先用 GameState（玩家描述），否则生成默认标题
        if game_state:
            title = game_state[:500]
        else:
            title = f"[{logtype}] {model[:50] or 'Unknown'} / {osversion[:30] or 'Unknown OS'}"

        # 描述：汇总技术信息
        desc_parts = []
        if game_state:
            desc_parts.append(f"玩家反馈: {game_state}")
        desc_parts.append(f"操作系统: {osversion}")
        desc_parts.append(f"硬件型号: {model}")
        desc_parts.append(f"游戏版本: {gameversion}")
        desc_parts.append(f"文件类型: {logtype}")
        if file_size:
            # file_size 单位是字节
            try:
                size_kb = int(file_size) // 1024
                desc_parts.append(f"文件大小: {size_kb}KB")
            except (ValueError, TypeError):
                desc_parts.append(f"文件大小: {file_size}")
        description = "\n".join(desc_parts)

        # 解析时间
        submitted_at = None
        if time_str:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    submitted_at = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue

        # 原始文件下载链接
        source_url = None
        if file_path:
            source_url = f"{DUMP_SERVER_BASE}{file_path}"

        return {
            "external_id": dump_id,
            "title": title,
            "description": description or None,
            "status": "active",
            "priority": None,
            "severity": None,
            "module": logtype or None,
            "submitter": uuid or None,
            "assignee": None,
            "submitted_at": submitted_at,
            "resolved_at": None,
            "closed_at": None,
            "source_url": source_url,
            "product": "xkbb",
            "raw_json": raw,
        }


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
    """
    解析 cookie 字符串为字典。
    格式：PHPSESSID=xxx; user_name=xxx; user_key=xxx; product_id=xxx
    """
    cookies: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            cookies[name.strip()] = value.strip()
    return cookies


def _extract_json_data(html: str) -> list[dict]:
    """
    从 HTML 页面中提取嵌入的 JavaScript 数据数组。
    格式：var data = [...];
    """
    match = re.search(r"var\s+data\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logger.debug(f"[dump] JSON 解析失败: {e}")
        return []
