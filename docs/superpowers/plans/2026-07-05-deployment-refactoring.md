# Docker Compose 部署重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal：** 将当前生产 Docker Compose 部署重构为具备 nginx 统一入口、健康检查、重启策略、网络隔离、前端 standalone 修复及自动数据库迁移的内网测试环境方案。

**架构：** 新增 nginx 作为唯一入口；`/api/*` 与 `/ws/*` 透传至 FastAPI backend，其余流量转发至 Next.js standalone frontend；postgres/redis 仅挂 data 网络且不暴露宿主机端口；backend 与 celery-worker 共享 YAML 锚点环境变量；backend 启动时自动执行 Alembic 迁移。

**Tech Stack：** Docker Compose、nginx、Next.js 16 standalone、FastAPI、Celery、PostgreSQL 16 + pgvector、Redis 7。

## Global Constraints

- 保留 Docker Compose 部署方式，不引入 Kubernetes/Swarm。
- 不修改 `docker-compose.dev.yml`。
- 不实现 HTTPS、域名、负载均衡、CI/CD、监控、备份。
- 不修改业务代码，只调整部署相关配置与入口脚本。
- 所有服务配置 `restart: unless-stopped`。
- postgres/redis 不映射端口到宿主机。
- `NEXT_PUBLIC_*` 变量通过 Dockerfile `ARG` + docker-compose `build.args` 在构建时传入。
- backend 以非 root 用户运行。

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `nginx/nginx.conf`（新建） | nginx 反向代理：/api/* 与 /ws/* → backend，其余 → frontend |
| `frontend/next.config.ts`（修改） | 启用 `output: "standalone"` |
| `frontend/Dockerfile`（修改） | 通过 `ARG` 接收 `NEXT_PUBLIC_API_URL`、`NEXT_PUBLIC_WS_URL` |
| `backend/docker-entrypoint.sh`（新建） | 根据 `RUN_MIGRATIONS` 自动执行 `alembic upgrade head`，然后启动 uvicorn |
| `backend/Dockerfile`（修改） | 增加非 root 用户，使用入口脚本 |
| `docker-compose.yml`（重写） | 6 服务编排、双网络、健康检查、YAML 锚点复用 env |

---

### Task 1：创建 nginx 反向代理配置

**Files：**
- Create: `nginx/nginx.conf`
- Test: 使用 `nginx -t` 验证配置语法

**Interfaces：**
- Consumes: 无
- Produces: `nginx/nginx.conf`，定义 `backend:8000` 与 `frontend:3000` 两个 upstream 路由

- [x] **Step 1：创建 nginx 配置目录与文件**

```bash
mkdir -p /Users/felixwang/devspace/cc-project/mca-translation/nginx
```

- [x] **Step 2：写入 nginx.conf**

```nginx
server {
    listen 80;
    server_name localhost;
    client_max_body_size 10m;

    location /health {
        proxy_pass http://backend:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ws/ {
        proxy_pass http://backend:8000/api/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

- [x] **Step 3：验证 nginx 配置语法**

Run:

```bash
docker run --rm -v /Users/felixwang/devspace/cc-project/mca-translation/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t
```

Expected:

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

- [x] **Step 4：提交**

```bash
git -C /Users/felixwang/devspace/cc-project/mca-translation add nginx/nginx.conf
git -C /Users/felixwang/devspace/cc-project/mca-translation commit -m "feat(deploy): add nginx reverse proxy config"
```

---

### Task 2：修复前端 standalone 构建并支持构建时 env

**Files：**
- Modify: `frontend/next.config.ts`
- Modify: `frontend/Dockerfile`
- Test: `docker build -t mca-frontend-test ./frontend`

**Interfaces：**
- Consumes: 无
- Produces: 生产可用的 frontend 镜像，内部 API 调用使用相对路径 `/api/*`，WebSocket 使用相对路径 `/api/ws/*`

- [x] **Step 1：启用 Next.js standalone 输出**

修改 `frontend/next.config.ts`：

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [x] **Step 2：修改 frontend Dockerfile 接收构建参数**

修改 `frontend/Dockerfile`：

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@10.24.0 --activate && pnpm install --frozen-lockfile
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [x] **Step 3：本地构建验证**

Run:

```bash
cd /Users/felixwang/devspace/cc-project/mca-translation/frontend
docker build --build-arg NEXT_PUBLIC_API_URL="" --build-arg NEXT_PUBLIC_WS_URL="" -t mca-frontend-test .
```

Expected: 构建成功，无 `standalone` 相关文件缺失错误。

- [x] **Step 4：提交**

```bash
git -C /Users/felixwang/devspace/cc-project/mca-translation add frontend/next.config.ts frontend/Dockerfile
git -C /Users/felixwang/devspace/cc-project/mca-translation commit -m "fix(deploy): enable Next.js standalone and pass public env at build time"
```

---

### Task 3：backend 入口脚本与 Dockerfile 加固

**Files：**
- Create: `backend/docker-entrypoint.sh`
- Modify: `backend/Dockerfile`
- Test: `docker build -t mca-backend-test ./backend` 并检查入口脚本行为

**Interfaces：**
- Consumes: `DATABASE_URL`、`REDIS_URL` 等环境变量由 docker-compose 注入
- Produces: backend 容器启动时执行 `alembic upgrade head`（默认启用），然后启动 uvicorn

- [x] **Step 1：创建入口脚本**

写入 `backend/docker-entrypoint.sh`：

```bash
#!/bin/sh
set -e

# 仅当以默认 backend 方式启动（无额外命令参数）时才执行迁移
if [ "$#" -eq 0 ] && [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
else
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
```

- [x] **Step 2：添加执行权限**

```bash
chmod +x /Users/felixwang/devspace/cc-project/mca-translation/backend/docker-entrypoint.sh
```

- [x] **Step 3：修改 backend Dockerfile**

修改 `backend/Dockerfile`：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/uploads
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
```

- [x] **Step 4：本地构建验证**

Run:

```bash
cd /Users/felixwang/devspace/cc-project/mca-translation/backend
docker build -t mca-backend-test .
```

Expected: 构建成功。

- [x] **Step 5：提交**

```bash
git -C /Users/felixwang/devspace/cc-project/mca-translation add backend/docker-entrypoint.sh backend/Dockerfile
git -C /Users/felixwang/devspace/cc-project/mca-translation commit -m "feat(deploy): add backend entrypoint with auto migrations and non-root user"
```

---

### Task 4：重写 docker-compose.yml

**Files：**
- Modify: `docker-compose.yml`
- Test: `docker compose config` 语法检查 + `docker compose up -d --build` + curl  smoke test

**Interfaces：**
- Consumes: `nginx/nginx.conf`、`frontend/Dockerfile`、`backend/Dockerfile`
- Produces: 完整的生产编排，对外仅暴露 nginx :80

- [x] **Step 1：重写 docker-compose.yml**

```yaml
x-backend-env: &backend-env
  DATABASE_URL: postgresql+asyncpg://culturalbridge:culturalbridge@postgres:5432/culturalbridge
  REDIS_URL: redis://redis:6379/0
  SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
  BAILIAN_API_KEY: ${BAILIAN_API_KEY}
  BAILIAN_BASE_URL: https://dashscope.aliyuncs.com/compatible-mode/v1
  BAILIAN_MODEL_PLUS: qwen-plus
  BAILIAN_MODEL_MAX: qwen-max
  MCA_FILE_STORE_DIR: /app/uploads
  FRONTEND_URL: ${FRONTEND_URL:-http://localhost}
  RUN_MIGRATIONS: ${RUN_MIGRATIONS:-true}

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - app
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost}
        NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL:-ws://localhost}
    networks:
      - app
    environment:
      - NODE_ENV=production
      - HOSTNAME=0.0.0.0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 15s

  backend:
    build: ./backend
    networks:
      - app
      - data
    environment:
      <<: *backend-env
    volumes:
      - uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s

  celery-worker:
    build: ./backend
    command: celery -A app.celery_app worker -l info -c 4
    networks:
      - data
    environment:
      <<: *backend-env
    volumes:
      - uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "celery", "-A", "app.celery_app", "inspect", "ping"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s

  postgres:
    image: pgvector/pgvector:pg16
    networks:
      - data
    environment:
      POSTGRES_DB: culturalbridge
      POSTGRES_USER: culturalbridge
      POSTGRES_PASSWORD: ${DB_PASSWORD:-culturalbridge}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U culturalbridge -d culturalbridge"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    networks:
      - data
    volumes:
      - redisdata:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep PONG"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 5s

networks:
  app:
  data:

volumes:
  pgdata:
  redisdata:
  uploads:
```

- [x] **Step 2：compose 语法检查**

Run:

```bash
cd /Users/felixwang/devspace/cc-project/mca-translation
docker compose config > /dev/null
```

Expected: 无错误输出，退出码 0。

- [x] **Step 3：完整启动并 smoke test**

Run:

```bash
cd /Users/felixwang/devspace/cc-project/mca-translation
docker compose down
docker compose up -d --build
sleep 45
curl -f http://localhost/health
curl -f http://localhost/
```

Expected:

- `docker compose ps` 显示 6 个服务均 `healthy`（或至少 `Up`）。
- `curl http://localhost/health` 返回 `{"status":"ok"}`。
- `curl http://localhost/` 返回前端 HTML（HTTP 200）。

- [x] **Step 4：WebSocket 与登录流程验证（可选但推荐）**

在浏览器访问 `http://localhost`，使用已有账号登录，提交一次翻译任务，确认 WebSocket 状态更新正常。

- [x] **Step 5：崩溃恢复验证**

Run:

```bash
docker compose kill backend
sleep 5
docker compose ps backend
```

Expected: backend 容器状态重新变为 `Up (healthy)`，证明 `restart: unless-stopped` 生效。

- [x] **Step 6：提交**

```bash
git -C /Users/felixwang/devspace/cc-project/mca-translation add docker-compose.yml
git -C /Users/felixwang/devspace/cc-project/mca-translation commit -m "feat(deploy): refactor production docker-compose with nginx, healthchecks, networks"
```

---

### Task 5：更新环境变量示例文档

**Files：**
- Modify: `.env.example`
- Test: 无（文档同步）

**Interfaces：**
- Consumes: 新 docker-compose 中使用的变量
- Produces: 与部署方案一致的 `.env.example`

- [x] **Step 1：更新 `.env.example`**

```bash
# Required
BAILIAN_API_KEY=your-bailian-api-key
SECRET_KEY=change-me-to-a-random-string

# Optional
DB_PASSWORD=culturalbridge

# Frontend public origin (used at Docker build time)
NEXT_PUBLIC_API_URL=http://localhost
NEXT_PUBLIC_WS_URL=ws://localhost

# Backend CORS origin and migration behavior
FRONTEND_URL=http://localhost
RUN_MIGRATIONS=true
```

- [x] **Step 2：提交**

```bash
git -C /Users/felixwang/devspace/cc-project/mca-translation add .env.example
git -C /Users/felixwang/devspace/cc-project/mca-translation commit -m "docs(env): sync .env.example with new deployment variables"
```

---

## 自我审查

### Spec 覆盖检查

| Spec 要求 | 对应任务 |
|---|---|
| nginx 统一入口 | Task 1、Task 4 |
| `/api/*`、`/ws/*` 透传 backend | Task 1 |
| 其余流量到 frontend | Task 1 |
| 修复 `output: "standalone"` | Task 2 |
| Dockerfile `ARG` 传 `NEXT_PUBLIC_*` | Task 2 |
| backend 非 root 用户 | Task 3 |
| 自动 `alembic upgrade head` | Task 3 |
| 双网络隔离 | Task 4 |
| 健康检查 + 依赖顺序 | Task 4 |
| 重启策略 | Task 4 |
| YAML 锚点复用 env | Task 4 |
| postgres/redis 不暴露宿主机端口 | Task 4 |
| FRONTEND_URL 可配置 | Task 4 |
| .env.example 同步 | Task 5 |

### Placeholder 检查

- 无 TBD/TODO。
- 无 "适当错误处理"、"类似 Task N" 等模糊描述。
- 每个修改步骤均给出完整代码或命令。

### 一致性检查

- `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` 在 Task 2 Dockerfile、Task 4 build.args、设计文档中保持一致（通过 `.env` 提供，默认分别为 `http://localhost` 与 `ws://localhost`）。
- `backend-env` 锚点包含的变量与现有 backend/celery 所需变量一致。
- `FRONTEND_URL` 默认 `http://localhost`，可通过 `.env` 覆盖。
- `RUN_MIGRATIONS` 默认 `true`，与 Task 3 入口脚本逻辑一致。

---

## 执行方式选择

Plan complete and saved to `docs/superpowers/plans/2026-07-05-deployment-refactoring.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
