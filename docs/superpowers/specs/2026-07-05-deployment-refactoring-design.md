# Docker Compose 部署重构设计

**日期：** 2026-07-05  
**背景：** 当前 `docker-compose.yml` 缺少生产环境必备要素（统一入口、健康检查、重启策略、网络隔离），且前端 standalone 构建配置缺失，导致生产镜像无法正常运行。本设计在保留 Docker Compose 部署方式的前提下，对生产部署方案进行重构。

## 目标

- 提供统一入口（nginx 反向代理），内网测试环境通过 `http://<host>` 访问全套服务。
- 修复前端 Next.js standalone 构建，使生产镜像可运行。
- 增加健康检查、依赖顺序与重启策略，提升运行稳定性。
- 通过自定义网络隔离数据库与应用层。
- 使用 YAML 锚点减少 backend 与 celery-worker 的环境变量重复。
- 自动执行 Alembic 数据库迁移，降低内网测试环境运维成本。

## 非目标

- 不引入 Kubernetes、Docker Swarm 等编排系统。
- 不改造 `docker-compose.dev.yml`（仍仅启动 pg + redis 供本地开发）。
- 不实现 HTTPS、域名、负载均衡、CI/CD 流水线、监控告警、数据库备份。
- 不修改业务代码，只调整部署相关配置与入口脚本。

## 当前问题诊断

| 问题 | 现状 | 影响 |
|---|---|---|
| 前端 standalone 构建失效 | `next.config.ts` 未设置 `output: "standalone"`，但 `frontend/Dockerfile` 却复制 `.next/standalone` | 生产镜像实际跑不起来 |
| 无统一入口 | 前端 3000、后端 8000 分别暴露端口 | 访问体验差，CORS 配置脆弱 |
| 无健康检查 | 5 个服务均无 `healthcheck` | 依赖顺序只看 `started`，后端可能在 pg/redis 未就绪时启动并反复崩溃 |
| 无重启策略 | 未配置 `restart` | 进程崩溃后不自动恢复 |
| 环境变量重复 | backend 与 celery-worker 的 9 个环境变量逐字复制 | 配置漂移风险 |
| 数据库端口裸露 | postgres、redis 均映射到宿主机 | 扩大内网安全攻击面 |
| 无网络分层 | 使用默认 bridge 网络 | 数据库与应用服务无隔离 |

## 方案选择

**选定方案：方案 A（nginx 全代理）**

nginx 作为唯一入口，将 `/api/*` 与 `/ws/*` 转发到 backend，其余转发到 frontend。Next.js 仍跑 standalone SSR，nginx 不感知前端内部路由。

未选方案：
- **方案 B（nginx 直服静态资源 + SSR 代理）：** 静态资源性能略好，但 nginx 配置复杂，对当前内网测试环境收益不足。
- **方案 C（nginx + 多 compose profile）：** 可扩展性更好，但当前没有监控/备份需求，属于过度设计。

## 服务拓扑

```
┌─────────────────────────────────────────┐
│              宿主机 :80                  │
│                  │                      │
│                  ▼                      │
│              nginx (app)                │
│          ┌──────┴──────┐                │
│          ▼             ▼                │
│   frontend:3000   backend:8000          │
│                       │                 │
│                       ▼                 │
│   ┌───────────────────────────────┐     │
│   │  data network                 │     │
│   │  postgres:5432  redis:6379    │     │
│   │  celery-worker                │     │
│   └───────────────────────────────┘     │
└─────────────────────────────────────────┘
```

### 服务清单

| 服务 | 作用 | 暴露给宿主机 | 所属网络 |
|---|---|---|---|
| `nginx` | 统一入口 | 是（:80） | `app` |
| `frontend` | Next.js standalone | 否 | `app` |
| `backend` | FastAPI | 否（可选调试可临时开启 8000） | `app`、`data` |
| `celery-worker` | 后台任务 | 否 | `data` |
| `postgres` | 数据库 | 否 | `data` |
| `redis` | 缓存 / Celery broker | 否 | `data` |

### 依赖顺序

- `backend`、`celery-worker` 等待 `postgres`、`redis` 进入 `healthy` 后启动。
- `nginx` 等待 `backend`、`frontend` 进入 `healthy` 后启动。

## nginx 路由

backend 的 API Router 统一以 `/api/*` 为前缀（如 `/api/auth/login`、`/api/ws/jobs/{job_id}`），因此 nginx **不剥离** `/api`，直接透传。

```nginx
server {
    listen 80;
    server_name localhost;

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
    }

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 前端环境变量

由于 `NEXT_PUBLIC_*` 在构建时固化，需通过 Dockerfile `ARG` + docker-compose `build.args` 传入。

| 变量 | 原值 | 新值 | 说明 |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `''` | 前端请求变成相对路径 `/api/...`，经 nginx 转发 |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | `''` | `new WebSocket('/api/ws/jobs/...')` 自动使用当前 host 与 ws/wss |

开发环境继续由 `frontend/.env.local` 提供 `http://localhost:8000`，不受影响。

## 后端 CORS

backend 的 `FRONTEND_URL` 改为 nginx 的实际访问地址（例如内网通过本机访问时为 `http://localhost`，通过 IP 访问时为 `http://<内网IP>`），使浏览器实际 origin 与 CORS `allow_origins` 一致。

`docker-compose.yml` 中默认写入 `FRONTEND_URL=http://localhost`，若通过其他地址访问，需在 `.env` 中覆盖该值。

## 健康检查

| 服务 | 检查命令 | 参数 |
|---|---|---|
| postgres | `pg_isready -U culturalbridge -d culturalbridge` | interval: 5s, timeout: 3s, retries: 5 |
| redis | `redis-cli ping \| grep PONG` | interval: 5s, timeout: 3s, retries: 5 |
| backend | `curl -f http://localhost:8000/health` | interval: 10s, timeout: 5s, retries: 3 |
| frontend | `curl -f http://localhost:3000/` | interval: 10s, timeout: 5s, retries: 3 |
| nginx | `curl -f http://localhost/` | interval: 10s, timeout: 5s, retries: 3 |
| celery-worker | `celery -A app.celery_app inspect ping` | interval: 15s, timeout: 5s, retries: 3 |

## 重启策略

所有服务统一配置 `restart: unless-stopped`，容器崩溃或宿主机重启后自动恢复，但用户手动停止后不会自动重启。

## 环境变量复用

在 `docker-compose.yml` 顶层定义 `x-backend-env` YAML 锚点，backend 与 celery-worker 通过 `<<: *x-backend-env` 引入，避免重复书写 9 个变量。

## Dockerfile 调整

### frontend/Dockerfile

新增 `ARG` 接收构建时环境变量：

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### frontend/next.config.ts

修复 standalone 输出：

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

### backend/Dockerfile

保持最小改动，增加非 root 用户：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 自动数据库迁移

新增 `backend/docker-entrypoint.sh`：

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

backend Dockerfile 的 `CMD` 改为入口脚本：

```dockerfile
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
```

`RUN_MIGRATIONS` 默认 `true`，内网测试环境自动迁移；如需手动控制，可在 `.env` 中设为 `false`。

## 待改文件清单

| 文件 | 变更类型 |
|---|---|
| `docker-compose.yml` | 重写：加 nginx、网络、健康检查、重启策略、YAML 锚点 |
| `frontend/Dockerfile` | 新增 `ARG` 传递 `NEXT_PUBLIC_*` |
| `frontend/next.config.ts` | 新增 `output: "standalone"` |
| `backend/Dockerfile` | 增加非 root 用户、入口脚本 |
| `backend/docker-entrypoint.sh` | 新增：自动执行 `alembic upgrade head` |
| `nginx/nginx.conf` | 新增：反向代理配置 |

## 验证方式

1. `docker compose up -d --build` 成功，无服务反复重启。
2. 浏览器访问 `http://localhost` 进入登录页。
3. 登录、上传文件、提交翻译、WebSocket 状态更新均正常。
4. 停止后重新 `docker compose up -d`，数据持久化（pgdata/redisdata/uploads 卷）。
5. 故意 `docker kill` backend 容器，观察到自动重启。

## 风险与回退

| 风险 | 缓解措施 |
|---|---|
| nginx 路由配置错误导致 API 404 | 先在本地完整测试所有接口 |
| 自动迁移并发执行 | 单节点 compose 不存在并发；如未来多实例部署，应改为 init 容器或手动迁移 |
| 前端 `NEXT_PUBLIC_*` 在构建时未生效 | Dockerfile 通过 `ARG` 显式传入，构建日志中可验证 |
| 非 root 用户导致文件权限问题 | `uploads` 卷权限在首次运行时检查，必要时 `chown` |

## 后续可选扩展

- HTTPS：在 nginx 前增加反向代理（如公司统一网关）或 nginx 直接配置 TLS。
- 监控：增加 Prometheus + Grafana，或至少配置日志聚合。
- 备份：对 `pgdata` 卷配置定时备份。
- 多实例：如需水平扩展，再评估 Docker Swarm / Kubernetes。
