# 小黑盒爬取研究归档

> 状态：**暂停**（2026-05-15）
> 原因：反爬机制阻塞，短期内无合理解法，记录所有尝试供后续参考。

---

## 目标

抓取 [小黑盒](https://www.xiaoheihe.cn) 上指定游戏的玩家评价，存入 comment-manager 数据库做分析。

---

## 目标 API

```
GET https://api.xiaoheihe.cn/bbs/app/link/game/comments
    ?game_id=<heybox_game_id>
    &hkey=<7字符动态token>
    &_time=<unix时间戳>
    &nonce=<随机串>
    &limit=20
    &offset=0
```

- **已确认**：该路径在小黑盒 JS Bundle 的 Tencent CAPTCHA 保护名单中（`tcaptchaActionList`）
- 返回格式：`{ result: { list: [...] } }`，每条评价含 `link_id`、`content`、`rating`、`create_time`、`user.nickname`、`like_count`

---

## URL 格式（从 JS Bundle 路由分析）

| 用途 | URL |
|------|-----|
| 游戏评价页（首选） | `https://www.xiaoheihe.cn/app/game/steam/{steam_app_id}` |
| 游戏评价页（备选1） | `https://www.xiaoheihe.cn/app/game/{appid}` |
| 游戏评价页（备选2） | `https://www.xiaoheihe.cn/app/game/pc/{appid}` |
| 单条评价 | `https://www.xiaoheihe.cn/app/game/comment/{link_id}` |

**注意**：steam_app_id 直接用作小黑盒的 game key（例如 `2358720` → 黑神话悟空）

---

## 认证机制

### 关键 Cookie

| Cookie 名 | 说明 | 获取方式 |
|-----------|------|---------|
| `user_pkey` | 用户身份标识，格式 base64(`{timestamp}_{userId}{random_key}`) | `document.cookie` 可获取 |
| `x_xhh_tokenid` | 核心 Auth Token | **HttpOnly**，只能从 DevTools Application→Cookies 获取 |
| `heybox_id` | 用户 ID | `document.cookie` 可获取 |

### hkey 动态 Token

- 7 字符随机串（如 `VZI1W74`）
- 由页面 JS（Nuxt.js 应用）在加载时动态生成
- 每个页面会话不同，无法预测或复用
- 匿名用户也会生成 hkey，但只对部分公开 API 有效

---

## 尝试过的方案

### 方案 1：直接 HTTP 请求（httpx）

```python
import httpx
headers = {"Cookie": cookie_str, "User-Agent": "..."}
r = httpx.get("https://www.xiaoheihe.cn/app/game/steam/2358720", headers=headers)
```

**结果**：服务端返回 302，重定向到 `/app/bbs/home`（未登录首页）  
**结论**：游戏评价页有服务端 SSR 校验，纯 HTTP 请求无法绕过

---

### 方案 2：Playwright + Cookie 注入（单域名）

```python
context.add_cookies([{"name": k, "value": v, "domain": ".xiaoheihe.cn", "path": "/"}])
page.goto("https://www.xiaoheihe.cn/app/game/steam/2358720")
```

**结果**：页面最终 URL 仍是 `/app/bbs/home`，重定向未消失  
**结论**：Cookie 注入到 `.xiaoheihe.cn` 后，浏览器访问 `www.xiaoheihe.cn` 时 Cookie 传递正常，但 SSR 仍然拒绝

---

### 方案 3：Playwright + 三域名 Cookie 注入

同时向以下三个域注入相同 Cookie：
- `.xiaoheihe.cn`
- `www.xiaoheihe.cn`  
- `api.xiaoheihe.cn`

拦截 `api.xiaoheihe.cn` 的请求，发现 **Cookie 请求头为空**——Playwright `add_cookies()` 对跨源 fetch 的子域无效。

**结论**：Playwright context 的 Cookie 只对顶层页面 origin 有效，内嵌 fetch 到 `api.xiaoheihe.cn` 不继承

---

### 方案 4：拦截 hkey 后直接调用 API

```python
# 拦截到 hkey = "VZI1W74"
r = context.request.get(
    "https://api.xiaoheihe.cn/bbs/app/link/game/comments",
    params={"game_id": "2358720", "hkey": hkey, "_time": int(time.time()), ...},
    headers={"Cookie": cookie_str}
)
```

**结果**：HTTP 200，但响应体为 `{"message": "非法请求"}`  
**推断**：服务器验证了设备指纹（UA、TLS 指纹、IP 等），直接构造请求与真实浏览器行为不一致

---

### 方案 5：代理 + Cookie（127.0.0.1:7897）

假设 session 绑定了特定代理 IP，尝试通过相同代理访问。

**结果**：`page.goto()` 超时（30s）  
**推断**：代理本身对 xiaoheihe.cn 访问异常，或者 session 绑定的是登录时的真实 IP 而非代理 IP

---

## 根本障碍

1. **HttpOnly Token**：`x_xhh_tokenid` 无法从 `document.cookie` 获取，Playwright 注入后也未传递到 API 请求中
2. **Tencent CAPTCHA**：目标 API 在 CAPTCHA 保护名单中，触发验证时直接返回"非法请求"
3. **IP/设备绑定**：session token 疑似与登录时的 IP 或设备指纹绑定，换环境后失效
4. **SPA 反爬**：Nuxt.js SPA 的 SSR 校验在服务端完成，本地浏览器无法复现完整请求签名

---

## 可能的后续方向

1. **持久化真实浏览器 Profile**：使用 `playwright launch --user-data-dir` 保持真实登录态，避免重新注入
2. **移动端 API**：研究小黑盒 App 的 API（可能不在 Tencent CAPTCHA 保护范围内）
3. **官方数据接口**：联系小黑盒官方申请数据合作
4. **半自动化**：提供工具让用户手动导出评价 CSV，系统负责导入和分析

---

## 相关文件

- `backend/app/crawlers/xiaoheihe/__init__.py` — 爬虫代码（当前状态：暂停，直接返回空列表）
- `.env.example` — Cookie 配置说明
- `docs/SETUP.md` — Cookie 获取步骤说明（#小黑盒配置 章节）
