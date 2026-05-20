Ready for review
Select text to add comments on the plan
小黑盒：保存研究文档 + 暂停爬取
Context
经过多次尝试，小黑盒（xiaoheihe.cn）游戏评价爬取因反爬机制被阻塞，无法在合理时间内解决。 用户决定：将所有研究成果写成文档存档，然后将爬虫临时设为"不支持"状态，后续有需要时再继续。

涉及文件
文件	改动性质
docs/xiaoheihe-crawl-research.md	新建：爬取研究归档文档
backend/app/crawlers/xiaoheihe/__init__.py	简化：直接返回空列表 + 明确日志
backend/test_cookie.py	删除：临时调试脚本
backend/test_requests.py	删除：临时调试脚本
第一步：创建研究文档
新建 docs/xiaoheihe-crawl-research.md，记录以下内容：

文档结构
背景：小黑盒是 Nuxt.js SPA，游戏评价页需要登录才能访问
目标 API：/bbs/app/link/game/comments（在 Tencent CAPTCHA 保护名单中）
URL 格式（从 JS Bundle 分析得出）：
游戏评价页：https://www.xiaoheihe.cn/app/game/steam/{steam_app_id}
备选格式：/app/game/{appid}、/app/game/pc/{appid}
必需参数：hkey（7字符动态 token，页面 JS 生成）、_time（时间戳）、nonce
尝试过的方案：
直接 HTTP 请求（httpx）：服务端 302 重定向到 /app/bbs/home
Playwright + Cookie 注入（域名 .xiaoheihe.cn）：游戏页仍重定向，Cookie 未传入 api.xiaoheihe.cn 子域
同时注入 .xiaoheihe.cn / www.xiaoheihe.cn / api.xiaoheihe.cn 三个域：Cookie header 为空，api.xiaoheihe.cn 不接受
代理（http://127.0.0.1:7897）+ Cookie：超时（可能 session 绑定了 IP）
拦截 hkey 后直接调用 API：返回"非法请求"（设备指纹不匹配）
根本障碍：
x_xhh_tokenid 是 HttpOnly，document.cookie 获取不到，但也是 Playwright 注入失败的核心
疑似 session 绑定了特定 IP 或设备指纹
/bbs/app/link/game/comments 在 Tencent CAPTCHA 保护列表中
Cookie 格式参考（从 .env.example 记录，不含实际值）：
user_pkey：base64({timestamp}_{userId}{random_key})
x_xhh_tokenid：HttpOnly，需从 DevTools Application→Cookies 获取
可能的后续方向：
使用真实浏览器（非 headless）并保持持久 Profile
研究是否有移动端 API 绕过 Tencent CAPTCHA
申请小黑盒官方数据接口（如有）
第二步：简化爬虫
将 backend/app/crawlers/xiaoheihe/__init__.py 的 _fetch_sync 函数开头直接 return：

def _fetch_sync(self, game_app_id, since, limit):
    logger.warning(
        "[xiaoheihe] 小黑盒爬取暂停（anti-bot 机制阻塞，详见 docs/xiaoheihe-crawl-research.md）"
    )
    return []
保留其他代码结构（_parse_cookies、常量等）以备后续恢复使用。

第三步：删除临时测试脚本
删除：

backend/test_cookie.py
backend/test_requests.py
验证步骤
确认 docs/xiaoheihe-crawl-research.md 内容完整
重启后端，触发一次小黑盒爬取，确认日志中出现 warning 而非报错
确认两个测试脚本已删除