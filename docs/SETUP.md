# Comment Manager — 启动指南

## 环境要求

- Docker Desktop for Windows
- Python 3.11+
- Node.js 20+

## 项目路径

本机：`F:\xiake2\Docs\工具目录\comment-manager`

---

## 首次搭建（新电脑）

### 1. 安装基础工具

按顺序安装：
- **Git**：https://git-scm.com/download/win
- **Python 3.11+**：https://www.python.org/downloads/（安装时勾选 "Add Python to PATH"）
- **Node.js 20+**：https://nodejs.org/（选 LTS）
- **Docker Desktop**：https://www.docker.com/products/docker-desktop/

装完 Docker Desktop 后**重启电脑**。

### 2. 启用 WSL2

```bash
wsl --install -d Ubuntu
```

装完重启。

### 3. 克隆项目

```bash
git clone https://github.com/hezhenghz/comment-manager.git
cd comment-manager
```

### 4. 恢复 .env 文件

`.env` 未提交到 Git（含 API Key），参考 `.env.example` 手动创建：

| 变量 | 说明 |
|------|------|
| `AI_CHAT_API_KEY` | DeepSeek API Key（platform.deepseek.com） |
| `AI_CHAT_MODEL` | 默认 `deepseek-chat` |
| `AI_EMBEDDING_API_KEY` | Qwen/DashScope Key（暂未启用，可留空） |
| `DATABASE_URL` | PostgreSQL 连接串（Docker 环境默认已配置） |
| `CRAWLER_INTERVAL_MINUTES` | 定时爬取间隔，默认 120 |

### 5. 创建 Python 虚拟环境

**在项目根目录**执行（`.venv` 放根目录，供 backend 使用）：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

---

## 日常启动

### 1. 启动数据库

```bash
docker-compose up -d db
```

等 Docker 日志出现 `database system is ready to accept connections`。

### 2. 初始化数据库（仅首次）

```bash
.venv\Scripts\python backend/manage.py initdb
.venv\Scripts\python backend/manage.py enable_vector
```

### 3. 创建登录账号（仅首次）

```bash
.venv\Scripts\python backend/manage.py adduser admin <你的密码> 管理员
```

### 4. 启动后端（终端 1）

```powershell
cd backend
..\.venv\Scripts\uvicorn app.main:app --reload --port 8001 --host 0.0.0.0
```

> `--host 0.0.0.0` 使后端监听所有网卡，局域网内可访问。仅本机使用时去掉该参数也可正常运行。

后端地址：`http://localhost:8001`  
API 文档：`http://localhost:8001/docs`

### 5. 启动前端（终端 2）

```bash
cd frontend
npm install   # 首次或依赖变更时
npm run dev
```

前端地址：`http://localhost:5173`

### 6. 登录

打开 `http://localhost:5173`，用第 3 步创建的账号登录。

---

## 代理配置（国内网络）

### Git 代理

```bash
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

### Steam 爬虫代理

如爬虫请求超时，在 `.env` 中添加：

```
STEAM_PROXY=http://127.0.0.1:7897
```

---

## 小黑盒登录初始化（首次 / 登录态过期时）

小黑盒爬虫使用 Playwright 持久化浏览器 Profile 保留登录态（含 HttpOnly Cookie），
不依赖手动导出 Cookie。首次使用或登录态过期时，运行一次初始化脚本即可。

### 运行初始化脚本

```powershell
.venv\Scripts\python backend\setup_xiaoheihe_browser.py
```

脚本会打开一个独立的 Chromium 窗口（与系统 Chrome 无关），在窗口里登录小黑盒后，
回到终端按回车，登录状态自动保存到 `backend/.browser_profiles/xiaoheihe/`。

**注意事项：**
- Profile 目录未提交 Git，换电脑或重建环境需重新运行此脚本
- 登录态通常可维持数周；如爬取日志提示"登录态已过期"，重新运行脚本即可
- 运行脚本前确保已安装 playwright 及浏览器：
  ```powershell
  .venv\Scripts\pip install playwright
  .venv\Scripts\playwright install chromium
  ```

### 验证爬虫是否正常

```powershell
.venv\Scripts\python backend\test_xiaoheihe.py <Steam_App_ID>
```

成功时输出若干条评论；若返回空列表，按上面步骤重新初始化登录态。

### Windows 兼容说明

uvicorn 在 Windows 默认使用 `SelectorEventLoop`，不支持 `create_subprocess_exec`，
而 playwright 启动浏览器进程必须依赖该接口。

**解决方案（已固化在代码里，无需手动操作）：**
爬虫在独立的 `ThreadPoolExecutor` 线程里创建 `asyncio.ProactorEventLoop()`，
playwright 在该 loop 内运行，与 uvicorn 主 loop 完全隔离，互不干扰。
详见 `backend/app/crawlers/xiaoheihe/__init__.py` 中的 `_crawl_in_thread`。

### 分页机制说明

小黑盒评论 API 有两个不可信的字段，调试时需注意：

| 字段 | 问题 | 正确处理方式 |
|------|------|-------------|
| `total_page` | 固定返回 100，与实际页数无关 | 不用于判断终止，只记日志 |
| 签名 URL 里的 `limit` | 实测值为 10（非默认的 30），直接影响 offset 步长 | 从捕获的 URL 参数中读取，作为每次 offset 递增量 |

**正确的翻页终止条件：**
1. 当次 fetch 返回 `items` 为空列表
2. 连续 2 次请求新增条数为 0（API 无更多数据或重复返回同一页）

若出现抓取数量远少于网页显示数量的情况，首先检查日志里的 `实际每页条数=` 和每页 `返回N条` 是否与预期一致。

---

---

## 局域网共享（让同事访问）

### 1. 查询本机 IP

```powershell
ipconfig
```

找 `以太网适配器` 或 `WLAN` 下的 IPv4 地址，例如 `192.168.1.100`。

### 2. 开放防火墙（管理员 PowerShell，仅首次）

```powershell
New-NetFirewallRule -DisplayName "Comment Manager Frontend" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow
New-NetFirewallRule -DisplayName "Comment Manager Backend"  -Direction Inbound -Protocol TCP -LocalPort 8001 -Action Allow
```

### 3. 按正常步骤启动前后端

前端无需额外配置（`vite.config.ts` 已设置 `host: true`）；  
后端启动命令带上 `--host 0.0.0.0`（见"启动后端"章节）。

### 4. 把地址发给同事

```
http://192.168.1.100:5173
```

同事在浏览器打开即可，用你创建的账号登录。

---

## 账号管理

系统没有注册页，由管理员在命令行管理账号（密码以哈希值存库）：

```powershell
# 创建账号（在项目根目录执行）
.venv\Scripts\python backend\manage.py adduser <用户名> <密码> <显示名>

# 示例
.venv\Scripts\python backend\manage.py adduser zhangsan Pass123 张三

# 设置管理员权限（管理员可访问"游戏管理"功能）
.venv\Scripts\python backend\manage.py setadmin <用户名>

# 示例
.venv\Scripts\python backend\manage.py setadmin admin

# 查看所有账号
.venv\Scripts\python backend\manage.py listusers
```

> **权限说明**：普通用户可查看仪表盘、评论、BUG、建议；管理员额外拥有"游戏管理"入口（添加游戏、触发爬虫、配置停用词等）。

---

## 快速参考

```powershell
# 启动数据库
docker-compose up -d db

# 启动后端（在 backend 目录）
..\.venv\Scripts\uvicorn app.main:app --reload --port 8001 --host 0.0.0.0

# 启动前端（在 frontend 目录）
npm run dev
```
