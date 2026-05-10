# 项目进度 — 2026-05-10

## 已完成

- Docker Desktop + WSL2 引擎已安装
- 全局 Stop hook 已配置：每次 Claude 回复完，右下角弹出 toast 通知「任务完成！」
- .env 文件已存在（含 DeepSeek/Qwen API Key、钉钉 Webhook）
- 项目代码完整（backend + frontend + docker-compose.yml）

## 下一步

### 1. 让 Docker Desktop 正常运行

当前 WSL 装了引擎，但没装 Ubuntu 发行版。两个方案：

**方案 A：微软应用商店装 Ubuntu**
- 打开 Microsoft Store，搜 "Ubuntu"（不带版本号）安装
- 装完点"打开"，设用户名密码

**方案 B：换 Hyper-V 后端**
- Docker Desktop → Settings → General → 取消勾选 "Use WSL 2 based engine"
- 改用 Hyper-V，不依赖 WSL

### 2. 启动项目（按 SETUP.md 走）

```bash
# 1) 启数据库
cd e:\Proj\comment-manager
docker-compose up -d db

# 2) 初始化数据库
python backend/manage.py initdb
python backend/manage.py enable_vector

# 3) 创建管理员账号
python backend/manage.py adduser admin <你的密码> 管理员

# 4) 启动后端
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000

# 5) 新终端，启动前端
cd e:\Proj\comment-manager\frontend
npm install
npm run dev

# 6) 浏览器打开 http://localhost:3000 登录
```

### 3. 添加游戏 + 触发爬虫

详见 [docs/SETUP.md](docs/SETUP.md) 第 6、7 步。

## 重要文件

- [docs/SETUP.md](docs/SETUP.md) — 完整启动指南
- [.env](.env) — API Key 配置文件
- [docker-compose.yml](docker-compose.yml) — 三个服务：db / backend / frontend
