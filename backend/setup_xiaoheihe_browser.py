"""
小黑盒浏览器登录初始化脚本（只需运行一次）。

用法：在项目根目录执行
    .venv/Scripts/python backend/setup_xiaoheihe_browser.py

注意：会打开一个全新的 Chromium 窗口（与你平时用的 Chrome 无关），
需要在这个窗口里重新登录小黑盒，登录完成后回到终端按回车。
"""
import os
import sys
import sqlite3

PROFILE_DIR = os.path.join(os.path.dirname(__file__), ".browser_profiles", "xiaoheihe")
COOKIE_DB = os.path.join(PROFILE_DIR, "Default", "Network", "Cookies")


def check_cookies() -> int:
    if not os.path.exists(COOKIE_DB):
        return 0
    try:
        conn = sqlite3.connect(COOKIE_DB)
        count = conn.execute(
            "SELECT count(*) FROM cookies WHERE host_key LIKE '%xiaoheihe%'"
        ).fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("未安装 playwright，请先执行：")
        print("   .venv/Scripts/pip install playwright")
        print("   .venv/Scripts/playwright install chromium")
        sys.exit(1)

    os.makedirs(PROFILE_DIR, exist_ok=True)
    print("=" * 60)
    print("小黑盒登录初始化")
    print("=" * 60)
    print(f"Profile 目录：{PROFILE_DIR}\n")
    print("即将打开一个独立的 Chromium 浏览器窗口。")
    print("注意：这不是你平时用的 Chrome，需要在这里重新登录！\n")

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()
        try:
            page.goto("https://www.xiaoheihe.cn", wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            pass

        print("浏览器已打开，请完成以下步骤：")
        print("  1. 在浏览器窗口中登录小黑盒（账号密码或扫码）")
        print("  2. 确认右上角显示你的头像/昵称（已登录状态）")
        print("  3. 回到此终端按回车\n")

        input(">>> 登录完成后按回车……")

        # 关闭 context 触发 Cookie 写入磁盘
        context.close()

    # 验证 Cookie 是否保存
    cookie_count = check_cookies()
    if cookie_count == 0:
        print("\n未检测到小黑盒 Cookie，可能原因：")
        print("  - 未在浏览器窗口中完成登录")
        print("  - 登录后未等待页面完全加载就按了回车")
        print("\n请重新运行本脚本，确保在浏览器里完整登录后再按回车。")
        sys.exit(1)
    else:
        print(f"\n✅ 检测到 {cookie_count} 个小黑盒 Cookie，登录状态已保存。")
        print(f"   Profile 目录：{PROFILE_DIR}")
        print("   现在可以正常使用小黑盒爬虫了。")


if __name__ == "__main__":
    main()
