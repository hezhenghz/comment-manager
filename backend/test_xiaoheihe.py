"""快速验证小黑盒爬虫是否能正常抓取。
用法：
    .venv/Scripts/python backend/test_xiaoheihe.py <steam_app_id>
示例：
    .venv/Scripts/python backend/test_xiaoheihe.py 3972650

注意：本脚本作为独立进程运行，asyncio.run() 在 Windows 默认使用 ProactorEventLoop，
playwright 可以正常启动浏览器。这与通过 Web API 触发爬虫的情况不同——uvicorn 使用
SelectorEventLoop，需要在独立线程里创建 ProactorEventLoop 才能运行 playwright。
详见 app/crawlers/xiaoheihe/__init__.py 中 _crawl_in_thread 的说明。
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main():
    app_id = sys.argv[1] if len(sys.argv) > 1 else "1245620"
    print(f"测试小黑盒爬虫，Steam App ID: {app_id}\n")

    from app.crawlers.xiaoheihe import XiaoheiheCrawler
    crawler = XiaoheiheCrawler()

    print("开始抓取（最多 10 条）……")
    results = await crawler.fetch(app_id, since=None, limit=10)

    if not results:
        print("\n未抓到任何评价，请检查：")
        print("  1. 登录态是否有效（重跑 setup_xiaoheihe_browser.py）")
        print("  2. Steam App ID 是否正确（该游戏在小黑盒是否有评价页）")
        return

    print(f"\n成功抓取 {len(results)} 条：\n")
    for i, c in enumerate(results, 1):
        ts = c.published_at.strftime("%Y-%m-%d") if c.published_at else "未知"
        preview = c.content[:60].replace("\n", " ")
        print(f"  [{i}] {ts}  {c.author_name}  👍{c.thumbs_up}")
        print(f"      {preview}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
