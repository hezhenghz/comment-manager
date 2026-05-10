# 项目进度 — 2026-05-10

## 项目仓库

```
https://github.com/hezhenghz/comment-manager.git
```

## 已完成

- 代码已提交并推送到 GitHub（102 files）
- 全局 Stop hook 已配置 → 每次 Claude 回完话右下角 toast 通知「任务完成！」
- .env 文件已配置（DeepSeek/Qwen API Key、钉钉 Webhook 等）

## 新电脑从头搭建

### 1. 安装基础环境

按顺序装这三个：

- **Git for Windows**：https://git-scm.com/download/win（独立安装版）
- **Python 3.12+**：https://www.python.org/downloads/（安装时勾选 "Add Python to PATH"）
- **Node.js 20+**：https://nodejs.org/（选 LTS 版本）
- **Docker Desktop for Windows**：https://www.docker.com/products/docker-desktop/

装完 Docker Desktop 后**重启电脑**。

### 2. 克隆项目

```bash
git clone https://github.com/hezhenghz/comment-manager.git
cd comment-manager
```

### 3. 恢复 .env 文件

`.env` 没提交到 GitHub（含 API Key）。把这台电脑上的 `.env` 复制到新电脑的项目根目录：

```
comment-manager/.env    ← 把旧电脑这份文件复制过来
.env.example            → 参考模板，丢了就照这个改
```

如果 .env 丢了，按 `.env.example` 重建，填入以下 key：

| 变量 | 说明 | 值 |
|------|------|----|
| `AI_CHAT_API_KEY` | DeepSeek API Key | 从 DeepSeek 后台获取 |
| `AI_EMBEDDING_API_KEY` | Qwen/DashScope Key | 从阿里云灵积获取 |
| `DINGTALK_WEBHOOK_URL` | 钉钉机器人 | 可选 |

### 4. 让 Docker Desktop 跑起来

安装 Docker Desktop 后它依赖 WSL2 后端。打开终端运行：

```bash
wsl --install -d Ubuntu
```

装完重启电脑。如果微软商店下载失败（国内网络问题），去 Microsoft Store 搜 "Ubuntu" 直接安装。

看 [docs/SETUP.md](docs/SETUP.md) 的「环境要求」部分。

### 5. 设置 Git 代理

```bash
# 你用的 SakuraCat 梯子，代理端口 7897
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

### 6. 启动项目

```bash
# 1) 启数据库
docker-compose up -d db

# 2) 初始化数据库（建表 + 启用 pgvector 向量扩展）
python backend/manage.py initdb
python backend/manage.py enable_vector

# 3) 创建管理员账号
python backend/manage.py adduser admin <你的密码> 管理员

# 4) 启动后端（终端 1）
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000

# 5) 启动前端（终端 2）
cd frontend
npm install
npm run dev

# 6) 浏览器打开 http://localhost:3000 登录
```

### 7. 添加游戏 + 触发爬虫

详见 [docs/SETUP.md](docs/SETUP.md) 第 6、7 步。

---

## 参考文件

- [docs/SETUP.md](docs/SETUP.md) — 完整启动指南（python + curl 命令等）
- [.env.example](.env.example) — .env 模板
- [docker-compose.yml](docker-compose.yml) — 三个服务：db / backend / frontend
