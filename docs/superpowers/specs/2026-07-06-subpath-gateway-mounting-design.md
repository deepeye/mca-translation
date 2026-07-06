# 公网网关 `/mca` 子路径挂载设计

- 日期: 2026-07-06
- 范围: 部署 / nginx / 前端构建配置(后端基本不动)
- 关联: `production-deployment` 记忆、`nginx/nginx.conf`、`frontend/lib/api-client.ts`、`frontend/lib/ws-client.ts`、`frontend/next.config.ts`、`frontend/Dockerfile`、`docker-compose.yml`

## 背景与问题

生产环境目前通过 nginx(容器内 80→暴露 8082)作为唯一入口,`/api/`→backend:8000、`/`→frontend:3000,前端用**同源相对路径**(`API_BASE=""`、`fetch("/api/...")`、`ws://${host}/api/ws/...`)。该设计能适配任意 host/port,但**不能适配子路径**。

现在要在公网 APISIX 网关上以 `airoute.hubpd.com/mca/*` 路径分流到 `10.19.1.95:8082`。核心障碍:前端发的 `fetch("/api/jobs")` 是**绝对路径**,浏览器在 `airoute.hubpd.com/mca/workspace` 页面下会把它解析成 `airoute.hubpd.com/api/jobs`(无 `/mca`),绕过网关 `/mca` 路由 → 404。

**结论**:走 `/mca` 子路径时,光改 nginx 或网关都不够,前端必须"感知前缀"。APISIX 的路径改写能力在此场景**无法免除应用改动**——因为问题在浏览器到网关这一段,不在网关到 nginx。

## 设计目标

- 通过 `airoute.hubpd.com/mca/` 正常访问应用,功能与直连 `10.19.1.95:8082` 等价(含 WebSocket 翻译进度、文件上传、导出)。
- 最小化改动,保持 dev 环境行为不变。
- 单一环境变量作为前缀真相源,避免多处硬编码漂移。

## 总体契约

三层各司其职:**前端自己拼 `/mca`,网关原样转发,nginx 内部剥离**。

| 层 | 职责 |
|---|---|
| **APISIX** | `airoute.hubpd.com/mca/*` → `10.19.1.95:8082`,**保留 `/mca` 前缀**(不 strip),开 WS upgrade + TLS 终止 |
| **nginx(容器内)** | 收到 `/mca/*`:后端路由 strip `/mca`→backend:8000;前端路由保留 `/mca`→frontend:3000(配合 basePath) |
| **前端** | `basePath=/mca`,API/WS/login 跳转都自带 `/mca` 前缀 |
| **后端** | 路由不变(nginx 已剥离);CORS 同源无需改;`root_path` 可选 |

**为什么 APISIX 不能 strip `/mca`**:前端用 `basePath=/mca` 后,Next.js 期望页面请求落在 `/mca/workspace`;若 APISIX 把 `/mca` 剥掉,nginx 转给 frontend 的是 `/workspace`,Next.js 返回 404。因此网关必须**保留**前缀,剥离动作放到 nginx 内部——且只对后端剥离,前端保留。

## APISIX 网关配置契约

- 路由:`airoute.hubpd.com/mca` 与 `/mca/*` → upstream `10.19.1.95:8082`,**保留原路径**(proxy-pass 不带 rewrite / 不 strip)。注意两条都要覆盖,否则 `/mca`(无尾斜杠)进不来。
- 启用 WebSocket(识别 `Upgrade` 头)——翻译任务进度走 `wss://airoute.hubpd.com/mca/api/ws/...`。
- TLS 在 APISIX 终止,回源 HTTP。
- upstream 健康检查可打 `GET /mca/health`(或直接 `10.19.1.95:8082/health`)。

> APISIX 配置由用户在网关侧维护,不在本仓库代码内。本设计仅明确契约。

## nginx 改动(`nginx/nginx.conf`)

新增 `/mca/*` location,保留 `/health`(容器自检),根路径重定向到 `/mca/`:

```nginx
server {
    listen 80;
    server_name localhost;
    client_max_body_size 10m;

    # 容器内部健康检查(不带 /mca)
    location /health {
        proxy_pass http://backend:8000/health;
        proxy_set_header Host $host;
    }

    # WS:strip /mca
    location /mca/api/ws/ {
        proxy_pass http://backend:8000/api/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # 后端 API:strip /mca
    location /mca/api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 外部健康检查
    location = /mca/health {
        proxy_pass http://backend:8000/health;
        proxy_set_header Host $host;
    }

    # 前端:保留 /mca(Next.js basePath 需要完整路径)
    location /mca/ {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 无尾斜杠重定向:/mca → /mca/,/ → /mca/(LAN 直连也能用)
    location = /mca { return 301 /mca/; }
    location = /    { return 301 /mca/; }
}
```

要点:
- `proxy_pass http://frontend:3000;`(无 URI、无尾斜杠)保留原始路径 `/mca/workspace`,匹配 Next.js basePath。
- `proxy_pass http://backend:8000/api/;`(带尾斜杠)剥离 `/mca`,后端无需改动。
- 删除原 `/api/`、`/api/ws/`、`/` location(被 `/mca/*` 与根路径重定向取代);保留 `/health` 供容器自检。

## 前端改动

引入单一环境变量 `NEXT_PUBLIC_BASE_PATH`(prod=`/mca`,dev 留空),作为 basePath 与 API/WS/login 前缀的唯一真相源。

### `frontend/next.config.ts`

```ts
const nextConfig: NextConfig = {
  output: "standalone",
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
};
```

### `frontend/lib/api-client.ts`(顶部)

```ts
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || BASE_PATH;
```

dev 仍可由 `NEXT_PUBLIC_API_URL=http://localhost:8000` 直连后端;prod 留空走 `BASE_PATH=/mca` 同源相对。`fetch(`${API_BASE}${path}`)` 调用处不变。

### 4 处 `window.location.href = "/login"` 改为前缀感知

涉及文件:
- `frontend/lib/api-client.ts`(3 处:401 处理、upload、exportDocx)
- `frontend/app/(main)/layout.tsx`(1 处:Sign out 按钮)

改为:
```ts
window.location.href = `${BASE_PATH}/login`;
```
(`layout.tsx` 顶部加一行 `const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";`)

> 原因:`window.location.href` 是浏览器原生 API,Next.js basePath 不会自动加前缀;`<Link>`/`router.push`/`redirect` 会自动加,无需改。

### `frontend/lib/ws-client.ts`(顶部)

同时修掉 HTTPS 下 `ws://` 混合内容的历史隐患:

```ts
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${BASE_PATH}`
    : "");
```

- dev:`NEXT_PUBLIC_WS_URL=ws://localhost:8000` 直连后端。
- prod HTTPS:`wss://airoute.hubpd.com/mca`。
- prod HTTP(LAN 直连):`ws://10.19.1.95:8082/mca`。

### `frontend/Dockerfile`(在 `pnpm build` 前)

```dockerfile
ARG NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
```

### `docker-compose.yml`(frontend build args)

```yaml
NEXT_PUBLIC_BASE_PATH: ${NEXT_PUBLIC_BASE_PATH:-}
```

prod `.env` 设 `NEXT_PUBLIC_BASE_PATH=/mca`。`basePath` 与 `NEXT_PUBLIC_*` 均为构建期内联,改 env 必须重建前端(不能只 restart)。

### 无需改动

`<Link href="/x">`、`router.push("/x")`、`redirect("/workspace")` —— Next.js 自动加 basePath。

### 待审计(低风险)

`public/` 资源若有 `<img src="/x">`、CSS `url(/x)` 等绝对路径引用,basePath 不会自动加前缀。初步 grep 未发现明显引用,实施时再扫一遍。

## 后端改动(最小)

- **CORS**:浏览器→API 全程同源(`https://airoute.hubpd.com`),不发 CORS 预检,**无需改**。`FRONTEND_URL` 仅为 allowlist,可选地设为 `https://airoute.hubpd.com`(origin,不含路径)以求严谨,但功能上非必需。
- **`root_path`**:可选。设 `FastAPI(root_path="/mca")` 仅让 OpenAPI 文档地址正确,不影响路由。非必需,建议跳过以最小化改动。

## 部署与验证

### 部署步骤(prod `zbd`)

1. prod `.env` 加 `NEXT_PUBLIC_BASE_PATH=/mca`(可选 `FRONTEND_URL=https://airoute.hubpd.com`)。
2. 推送代码改动到 gitee → prod pull。
3. `docker compose build frontend && docker compose up -d frontend nginx`。
4. APISIX 配置 `/mca/*` 路由(保留前缀 + WS + TLS)。
5. 按 checklist 验证。

### 验证清单

- [ ] `https://airoute.hubpd.com/mca/` 加载首页,自动跳 `/mca/workspace`。
- [ ] 未登录 → 401 跳 `/mca/login`;登录成功跳 `/mca/workspace`。
- [ ] 导航(工作台/审校/术语库/历史)客户端路由正常。
- [ ] 浏览器 devtools:API 请求落在 `/mca/api/...`(200)。
- [ ] 翻译任务:WS 连 `wss://airoute.hubpd.com/mca/api/ws/...` 并收到进度。
- [ ] 文件上传、导出 docx 正常。
- [ ] `_next` 静态资源 200(非 404);favicon 加载。
- [ ] LAN 直连 `http://10.19.1.95:8082/` → 301 跳 `/mca/`。

## 风险与兼容性

- **LAN 直连地址变化**:`:8082` → `:8082/mca/`(根路径有重定向,不会裸 404)。
- **dev 不受影响**:`NEXT_PUBLIC_BASE_PATH` 留空,basePath/API_BASE/WS 行为与现状一致。
- **需前端重建**:`basePath` 与 `NEXT_PUBLIC_*` 均为构建期内联,改 env 必须重建。
- **WS 协议**:本设计顺带把 `ws://` 改为按 `window.location.protocol` 自适应,修复 HTTPS 下混合内容隐患(原有 latent bug)。
- **basePath 不覆盖的绝对路径**:仅 `window.location.href`(已处理)与可能的 `public/` 资源绝对引用(待审计)两类,影响面小。

## 不做(Out of Scope)

- 子域名方案(`mca.hubpd.com`)——作为零改动备选已被排除,本设计选定路径前缀方案。
- 后端 `root_path`、CORS allowlist 严格化——可选,非必需。
- APISIX 路由具体配置——由用户在网关侧维护。
