# Comment Manager — 启动指南

## 环境要求

- Docker Desktop for Windows（[下载](https://www.docker.com/products/docker-desktop/)）
- Python 3.12+
- Node.js 20+

## 1. 启动 PostgreSQL（pgvector）

```bash
cd e:\Proj\comment-manager
docker-compose up -d db
```

等容器启动完毕（日志出现 `database system is ready to accept connections`）。

## 2. 初始化数据库

```bash
python backend/manage.py initdb
python backend/manage.py enable_vector
```

## 3. 创建登录账号

```bash
python backend/manage.py adduser admin <你的密码> 管理员
```

## 4. 安装依赖 + 启动后端

```bash
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000
```

后端跑在 `http://localhost:8000`，API 文档在 `http://localhost:8000/docs`。

## 5. 启动前端（新终端）

```bash
cd e:\Proj\comment-manager\frontend
npm install
npm run dev
```

前端跑在 `http://localhost:3000`。

## 6. 登录 + 添加游戏

打开 `http://localhost:3000`，用第 3 步创建的账号登录。

进入 **Games** 页面，添加：
- 名称：背包闯江湖
- Steam App ID：3972650

## 7. 触发爬虫抓评论

先登录获取 token：

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"<你的密码>\"}"
```

返回的 `access_token` 填入下面命令：

```bash
# 获取游戏 UUID
curl "http://localhost:8000/api/games" \
  -H "Authorization: Bearer <token>"

# 触发 Steam 商店评论爬虫
curl -X POST "http://localhost:8000/api/crawlers/steam_store/run?game_id=<游戏UUID>" \
  -H "Authorization: Bearer <token>"

# 触发 Steam 讨论区爬虫
curl -X POST "http://localhost:8000/api/crawlers/steam_hub/run?game_id=<游戏UUID>" \
  -H "Authorization: Bearer <token>"
```

## 8. 填 API Key

编辑 `.env` 文件，填入真实 key：

```
AI_CHAT_API_KEY=你的DeepSeek key（已填入则跳过）
AI_EMBEDDING_API_KEY=你的Qwen key（已填入则跳过）
DINGTALK_WEBHOOK_URL=你的钉钉机器人webhook（可选）
```

## 9. 设置告警（可选）

登录后在 **Alerts** 页面添加关键词规则，当新评论命中关键词时钉钉会推送通知。

## 一键启动（后续）

数据库只需初始化一次。之后日常使用只需：

```bash
docker-compose up -d db        # 启数据库
cd backend && uvicorn app.main:app --reload --port 8000  # 终端1
cd frontend && npm run dev     # 终端2
```

爬虫会每 120 分钟自动运行（`.env` 中 `CRAWLER_INTERVAL_MINUTES` 可调）。
