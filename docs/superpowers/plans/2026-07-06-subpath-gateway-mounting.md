# 公网网关 `/mca` 子路径挂载 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 CulturalBridge 通过公网 APISIX 网关 `airoute.hubpd.com/mca/*` 子路径访问,前端感知 `/mca` 前缀、nginx 内部剥离、后端不动。

**Architecture:** 单一环境变量 `NEXT_PUBLIC_BASE_PATH`(prod=`/mca`,dev 留空)作为前缀真相源,驱动 Next.js `basePath` 与 API/WS/login 前缀。APISIX 保留 `/mca` 前缀转发到 8082;nginx 对后端请求 strip `/mca`、对前端请求保留 `/mca`(配合 basePath)。新增 `frontend/lib/base-path.ts` 集中前缀工具(纯函数,便于单测),避免前缀逻辑在多处漂移。

**Tech Stack:** Next.js (App Router, `basePath`), TypeScript, Vitest + jsdom + @testing-library/react, nginx, Docker Compose。

## Global Constraints

- 单一前缀真相源 `NEXT_PUBLIC_BASE_PATH`(prod=`/mca`,dev 未注入→空串)。设定后前端 `basePath`/`API_BASE`/`WS_BASE`/login 跳转自动加前缀;改 env 必须重建前端(构建期内联)。
- dev 环境行为不变:`NEXT_PUBLIC_BASE_PATH` 未注入时 `basePath=undefined`、`API_BASE=""`、`WS_BASE` 走 `ws://host`(同现状),`NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL` 仍可在 `frontend/.env.local` 注入绝对地址直连后端。
- APISIX 必须**保留** `/mca` 前缀(不 strip);nginx 对后端 strip、对前端保留。若 APISIX strip 会导致前端 basePath 404。
- 后端不改(无 `root_path`、无 CORS 变更)。prod 走 `/mca` 时 `.env` 的 `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL` 须留空,否则绝对地址覆盖 `BASE_PATH`。
- 代码注释中英双语,重要逻辑中文注释(项目约定)。
- 前端别名 `@/*` → `frontend/`。测试:Vitest + jsdom,`pnpm test` = `vitest run`。
- 单开发者模式:每个任务结束直接 `git commit` 到 main。

---

## File Structure

- **Create:** `frontend/lib/base-path.ts` — env 派生的 `BASE_PATH` 与 `loginPath()` 纯函数;前缀唯一真相源。
- **Create:** `frontend/lib/__tests__/base-path.test.ts` — `BASE_PATH` env 派生 + `loginPath` 单测。
- **Create:** `frontend/lib/__tests__/ws-client.test.ts` — `buildWsBase` 纯函数单测。
- **Create:** `frontend/lib/__tests__/api-client-base-path.test.ts` — API_BASE 前缀 + 401 登录跳转接线单测。
- **Modify:** `frontend/lib/ws-client.ts` — 新增导出纯函数 `buildWsBase()`;`WS_BASE` 改为协议自适应(`wss`/`ws`)+ `BASE_PATH` 前缀。
- **Modify:** `frontend/lib/api-client.ts` — `API_BASE` 用 `BASE_PATH`;3 处 `window.location.href="/login"` 改用 `loginPath()`。
- **Modify:** `frontend/app/(main)/layout.tsx` — Sign out 按钮的 `window.location.href="/login"` 改用 `loginPath()`。
- **Modify:** `frontend/next.config.ts` — 加 `basePath`。
- **Modify:** `frontend/Dockerfile` — `ARG`/`ENV NEXT_PUBLIC_BASE_PATH`。
- **Modify:** `docker-compose.yml` — frontend build args 加 `NEXT_PUBLIC_BASE_PATH`。
- **Modify:** `.env.example` — 文档化 `NEXT_PUBLIC_BASE_PATH`。
- **Modify:** `nginx/nginx.conf` — `/mca` 路由 + 无尾斜杠重定向。
- 不涉及后端文件。

> **对设计的微调(spec 已批准):** spec 写的是各文件内联 `const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || ""` 与 `window.location.href = ${BASE_PATH}/login`。本计划改为集中到 `lib/base-path.ts`(`BASE_PATH` + `loginPath()`),并在 ws-client 抽出纯函数 `buildWsBase()`。目的:DRY(`BASE_PATH`/`loginPath` 多处复用)+ 可单测(协议/前缀分支用表驱动测试,不依赖 jsdom location hack)。行为与 spec 等价。

---

## Task 1: `lib/base-path.ts` 前缀工具(TDD)

新增前缀真相源模块与单测。后续任务都依赖它。

**Files:**
- Create: `frontend/lib/base-path.ts`
- Create: `frontend/lib/__tests__/base-path.test.ts`

**Interfaces:**
- Produces: `BASE_PATH: string`(由 `process.env.NEXT_PUBLIC_BASE_PATH` 派生,未注入为 `""`);`loginPath(basePath?: string = BASE_PATH): string`(返回 `${basePath}/login`)。

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/__tests__/base-path.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

describe("base-path", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it("BASE_PATH reflects NEXT_PUBLIC_BASE_PATH when set", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const { BASE_PATH } = await import("@/lib/base-path");
    expect(BASE_PATH).toBe("/mca");
  });

  it("BASE_PATH is empty string when NEXT_PUBLIC_BASE_PATH unset", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "");
    const { BASE_PATH } = await import("@/lib/base-path");
    expect(BASE_PATH).toBe("");
  });

  it("loginPath prefixes basePath explicitly", async () => {
    const { loginPath } = await import("@/lib/base-path");
    expect(loginPath("/mca")).toBe("/mca/login");
    expect(loginPath("")).toBe("/login");
  });

  it("loginPath defaults to BASE_PATH", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const { loginPath } = await import("@/lib/base-path");
    expect(loginPath()).toBe("/mca/login");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test lib/__tests__/base-path.test.ts`
Expected: FAIL — `Failed to resolve import "@/lib/base-path"`(模块不存在)。

- [ ] **Step 3: Write minimal implementation**

Create `frontend/lib/base-path.ts`:

```ts
// 应用前缀:prod=/mca,dev 留空。由 NEXT_PUBLIC_BASE_PATH 构建期注入,
// 作为 basePath / API / WS / login 跳转前缀的唯一真相源。
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

// 登录跳转路径。window.location.href 是浏览器原生 API,不受 Next.js basePath 自动加前缀,需手动拼接。
export function loginPath(basePath: string = BASE_PATH): string {
  return `${basePath}/login`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test lib/__tests__/base-path.test.ts`
Expected: PASS(4 tests passed)。

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/base-path.ts frontend/lib/__tests__/base-path.test.ts
git commit -m "feat(frontend): add BASE_PATH/loginPath path utilities"
```

---

## Task 2: `lib/ws-client.ts` 协议自适应 WS 基址(TDD)

抽出纯函数 `buildWsBase`,让 WS 基址按页面协议选 `wss`/`ws` 并拼 `BASE_PATH`,顺带修复 HTTPS 下 `ws://` 混合内容的历史隐患。

**Files:**
- Create: `frontend/lib/__tests__/ws-client.test.ts`
- Modify: `frontend/lib/ws-client.ts`(整文件替换)

**Interfaces:**
- Consumes: `BASE_PATH` from `@/lib/base-path`。
- Produces: `buildWsBase(wsUrl: string | undefined, protocol: string, host: string, basePath?: string): string`(导出纯函数);`WS_BASE` 改用它。

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/__tests__/ws-client.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { buildWsBase } from "@/lib/ws-client";

describe("buildWsBase", () => {
  it("returns wsUrl override when provided (dev direct backend)", () => {
    expect(buildWsBase("ws://localhost:8000", "https:", "airoute.hubpd.com", "/mca"))
      .toBe("ws://localhost:8000");
  });

  it("derives wss:// + basePath on HTTPS page (prod)", () => {
    expect(buildWsBase(undefined, "https:", "airoute.hubpd.com", "/mca"))
      .toBe("wss://airoute.hubpd.com/mca");
  });

  it("derives ws:// + basePath on HTTP page (LAN direct)", () => {
    expect(buildWsBase(undefined, "http:", "10.19.1.95:8082", "/mca"))
      .toBe("ws://10.19.1.95:8082/mca");
  });

  it("works without prefix (basePath empty)", () => {
    expect(buildWsBase(undefined, "http:", "localhost", "")).toBe("ws://localhost");
  });

  it("returns empty string when protocol/host missing (SSR, no window)", () => {
    expect(buildWsBase(undefined, "", "", "/mca")).toBe("");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test lib/__tests__/ws-client.test.ts`
Expected: FAIL — `buildWsBase is not exported from @/lib/ws-client`(当前 ws-client 未导出该函数)。

- [ ] **Step 3: Write minimal implementation**

Replace `frontend/lib/ws-client.ts` with:

```ts
import { BASE_PATH } from "@/lib/base-path";

// 纯函数:推导 WebSocket 基址,便于单测协议/前缀逻辑。
// - wsUrl 注入时优先(dev 直连后端);否则按页面协议选 wss/ws,并拼 BASE_PATH。
export function buildWsBase(
  wsUrl: string | undefined,
  protocol: string,
  host: string,
  basePath: string = BASE_PATH,
): string {
  if (wsUrl) return wsUrl;
  if (!protocol || !host) return "";
  const scheme = protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${host}${basePath}`;
}

// 未注入时从当前页 host 推导,走 nginx 同源代理(生产);dev 由 .env.local 注入 ws://localhost:8000
const WS_BASE =
  typeof window !== "undefined"
    ? buildWsBase(process.env.NEXT_PUBLIC_WS_URL, window.location.protocol, window.location.host)
    : process.env.NEXT_PUBLIC_WS_URL || "";

export class WsClient {
  private ws: WebSocket | null = null;

  connect(jobId: string, onMessage: (data: unknown) => void) {
    this.disconnect();
    this.ws = new WebSocket(`${WS_BASE}/api/ws/jobs/${jobId}`);
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch { /* ignore non-JSON */ }
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WsClient();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test lib/__tests__/ws-client.test.ts`
Expected: PASS(5 tests passed)。

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/ws-client.ts frontend/lib/__tests__/ws-client.test.ts
git commit -m "feat(frontend): protocol-aware WS base with basePath support"
```

---

## Task 3: 接线 api-client + layout 使用前缀工具

把 `API_BASE` 与 4 处 `window.location.href="/login"` 接到 `BASE_PATH`/`loginPath`。

**Files:**
- Modify: `frontend/lib/api-client.ts:1-2,109,241,274`
- Modify: `frontend/app/(main)/layout.tsx:5,34`
- Create: `frontend/lib/__tests__/api-client-base-path.test.ts`

**Interfaces:**
- Consumes: `BASE_PATH`, `loginPath` from `@/lib/base-path`。

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/__tests__/api-client-base-path.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// jsdom 不支持真正导航,用 setter spy 捕获 window.location.href 赋值
function mockLocationHref() {
  const hrefSetter = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      set href(v: string) { hrefSetter(v); },
      get href(): string { return ""; },
      assign: hrefSetter,
      replace: hrefSetter,
    } as unknown as Location,
  });
  return hrefSetter;
}

describe("api-client base path wiring", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv("NEXT_PUBLIC_API_URL", ""); // 确保不被绝对地址覆盖
    localStorage.clear();
  });

  it("prefixes fetch URL with BASE_PATH", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const hrefSetter = mockLocationHref();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiClient } = await import("@/lib/api-client");
    await apiClient.listJobs();

    expect(fetchMock).toHaveBeenCalledWith(
      "/mca/api/jobs",
      expect.objectContaining({ method: "GET" }),
    );
    expect(hrefSetter).not.toHaveBeenCalled();
  });

  it("redirects to /mca/login on 401", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const hrefSetter = mockLocationHref();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "unauth" }), { status: 401 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiClient } = await import("@/lib/api-client");
    await expect(apiClient.listJobs()).rejects.toThrow("Unauthorized");

    expect(hrefSetter).toHaveBeenCalledWith("/mca/login");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test lib/__tests__/api-client-base-path.test.ts`
Expected: FAIL — fetch 被调用为 `/api/jobs`(无 `/mca` 前缀);401 跳转 `/login`(非 `/mca/login`)。

- [ ] **Step 3: Wire api-client**

In `frontend/lib/api-client.ts`:

Replace the top two lines:

```ts
// 空串 = 相对路径,走 nginx 同源代理(生产);dev 由 .env.local 注入 NEXT_PUBLIC_API_URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
```

with:

```ts
import { BASE_PATH, loginPath } from "@/lib/base-path";

// API 基址:dev 优先 NEXT_PUBLIC_API_URL 直连后端;否则走 BASE_PATH 同源相对(生产 /mca)。
const API_BASE = process.env.NEXT_PUBLIC_API_URL || BASE_PATH;
```

Then replace all 3 occurrences of:

```ts
        window.location.href = "/login";
```

with:

```ts
        window.location.href = loginPath();
```

(位于 `request()` 的 401 分支、`uploadFile()` 的 401 分支、`exportDocx()` 的 401 分支。)

- [ ] **Step 4: Wire layout sign-out**

In `frontend/app/(main)/layout.tsx`:

After the existing imports (line 6, after `import { useCreditsStore } from "@/stores/credits-store";`), add:

```ts
import { loginPath } from "@/lib/base-path";
```

Replace the sign-out onClick (line 34):

```tsx
            onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }}
```

with:

```tsx
            onClick={() => { localStorage.removeItem("token"); window.location.href = loginPath(); }}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && pnpm test lib/__tests__/api-client-base-path.test.ts`
Expected: PASS(2 tests passed)。

- [ ] **Step 6: Run full frontend test suite**

Run: `cd frontend && pnpm test`
Expected: 全部 PASS(含新增 3 个测试文件 + 既有测试)。

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/api-client.ts frontend/app/(main)/layout.tsx frontend/lib/__tests__/api-client-base-path.test.ts
git commit -m "feat(frontend): prefix API calls and login redirects with BASE_PATH"
```

---

## Task 4: Next.js basePath + Docker 构建接线

配置构建期 `basePath` 与 Docker 传参。无单测(纯配置),用构建冒烟 + `docker compose config` 验证。

**Files:**
- Modify: `frontend/next.config.ts`
- Modify: `frontend/Dockerfile:8-12`
- Modify: `docker-compose.yml:39-42`
- Modify: `.env.example`

**Interfaces:**
- Produces: 构建期 `basePath`(`process.env.NEXT_PUBLIC_BASE_PATH || undefined`);Docker `ARG`/`ENV NEXT_PUBLIC_BASE_PATH`;compose build arg。

- [ ] **Step 1: Add basePath to next.config**

Replace `frontend/next.config.ts` with:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // prod 经公网网关 /mca 子路径挂载;dev 留空(NEXT_PUBLIC_BASE_PATH 未注入)。
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
};

export default nextConfig;
```

- [ ] **Step 2: Add ARG/ENV to Dockerfile**

In `frontend/Dockerfile`, replace the block:

```dockerfile
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
RUN pnpm build
```

with:

```dockerfile
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ARG NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
RUN pnpm build
```

- [ ] **Step 3: Add build arg to docker-compose**

In `docker-compose.yml`, replace the frontend `args:` block:

```yaml
      args:
        # 空默认 = 前端用相对路径走 nginx 同源代理;dev 在 frontend/.env.local 注入绝对地址
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-}
        NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL:-}
```

with:

```yaml
      args:
        # 空默认 = 前端用相对路径走 nginx 同源代理;dev 在 frontend/.env.local 注入绝对地址
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-}
        NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL:-}
        NEXT_PUBLIC_BASE_PATH: ${NEXT_PUBLIC_BASE_PATH:-}
```

- [ ] **Step 4: Document in .env.example**

In `.env.example`, replace:

```
# Frontend public origin (used at Docker build time)
NEXT_PUBLIC_API_URL=http://localhost
NEXT_PUBLIC_WS_URL=ws://localhost
```

with:

```
# Frontend public origin (used at Docker build time)
NEXT_PUBLIC_API_URL=http://localhost
NEXT_PUBLIC_WS_URL=ws://localhost
# 公网子路径前缀:prod=/mca,dev 留空。走 /mca 时须把上面两项留空(否则绝对地址覆盖前缀)。需重建前端。
NEXT_PUBLIC_BASE_PATH=/mca
```

- [ ] **Step 5: Audit public/ absolute-path references**

Run:

```bash
cd frontend
grep -rn --include="*.tsx" --include="*.ts" --include="*.css" 'src="/\|url(/' . | grep -v node_modules
```

Expected: 无命中,或命中的均为 basePath 安全引用(`<Link href="/x">` 不会匹配 `src="/`)。若命中 `<img src="/x">` 或 CSS `url(/x)` 引用 `public/` 资源,需改为 `next/image` 或显式 `${BASE_PATH}` 拼接——若出现,停下来在此任务补改。

- [ ] **Step 6: Verify build + compose config**

Run:

```bash
cd frontend && pnpm test && NEXT_PUBLIC_BASE_PATH=/mca pnpm build
```

Expected: 全部测试 PASS;`next build` 成功(exit 0,无类型错误)。

Run (from repo root):

```bash
docker compose config | grep NEXT_PUBLIC_BASE_PATH
```

Expected: 输出含 `NEXT_PUBLIC_BASE_PATH` 的 build arg 行(证明 compose 透传)。

- [ ] **Step 7: Commit**

```bash
git add frontend/next.config.ts frontend/Dockerfile docker-compose.yml .env.example
git commit -m "feat(build): wire NEXT_PUBLIC_BASE_PATH into basePath + Docker build"
```

---

## Task 5: nginx `/mca` 路由

重写 nginx 配置:`/mca/*` 路由,后端 strip、前端保留,无尾斜杠重定向。

**Files:**
- Modify: `nginx/nginx.conf`(整文件替换)

**Interfaces:**
- Produces: `/mca/api/ws/`、`/mca/api/`、`/mca/health`、`/mca/`、`/health`、`/mca`→`/mca/`、`/`→`/mca/` 路由。

- [ ] **Step 1: Replace nginx.conf**

Replace `nginx/nginx.conf` with:

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

    # 无尾斜杠重定向:/mca → /mca/,/ → /mca/
    location = /mca { return 301 /mca/; }
    location = /    { return 301 /mca/; }
}
```

- [ ] **Step 2: Verify nginx syntax**

Run (from repo root):

```bash
docker run --rm -v "$(pwd)/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:alpine nginx -t
```

Expected: `nginx: configuration file /etc/nginx/nginx.conf test is successful`。

> `nginx -t` 只校验语法,不解析 `backend`/`frontend` 主机名(运行时 DNS),故无需启动全栈。

- [ ] **Step 3: Commit**

```bash
git add nginx/nginx.conf
git commit -m "feat(nginx): route /mca prefix, strip for backend, preserve for frontend"
```

---

## Task 6: 本地端到端验证 + 生产部署

本地全栈验证 `/mca` 路径(无需 APISIX,直连 :8082/mca/),再执行生产部署并按 HTTPS/wss 清单验证。

**Files:**
- 无代码改动(仅验证与部署)。

- [ ] **Step 1: 本地全栈构建并启动**

Run (from repo root):

```bash
# 本地 .env 设 NEXT_PUBLIC_BASE_PATH(本地全栈验证用 /mca)
grep -q '^NEXT_PUBLIC_BASE_PATH=' .env 2>/dev/null || echo 'NEXT_PUBLIC_BASE_PATH=/mca' >> .env
docker compose build frontend nginx
docker compose up -d
docker compose ps   # 等待 nginx/frontend/backend healthy
```

Expected: 三个服务 `healthy`。

- [ ] **Step 2: 本地路由冒烟(HTTP :8082)**

Run:

```bash
curl -sI http://localhost:8082/            | head -1   # 期望 301
curl -sI http://localhost:8082/mca         | head -1   # 期望 301
curl -sI http://localhost:8082/mca/health  | head -1   # 期望 200
curl -sI http://localhost:8082/mca/api/jobs | head -1  # 期望 401(后端可达,非 404)
```

Expected: 依次 `301`、`301`、`200`、`401`。

- [ ] **Step 3: 浏览器功能清单(本地 HTTP)**

打开 `http://localhost:8082/mca/`,逐项确认:

- [ ] 首页加载并跳 `/mca/workspace`(或未登录跳 `/mca/login`)。
- [ ] 登录成功跳 `/mca/workspace`。
- [ ] devtools Network:API 请求落 `/mca/api/...`(200)。
- [ ] 提交翻译任务,devtools WS:`ws://localhost:8082/mca/api/ws/...` 连上并收到进度。
- [ ] 文件上传(.txt/.docx/.pdf)、导出 docx 正常。
- [ ] devtools:`_next` 静态资源 200(非 404);favicon 加载。
- [ ] 导航(工作台/审校/术语库/历史/使用手册)客户端路由正常。

- [ ] **Step 4: 生产部署(prod `zbd`)**

按 `production-deployment` 与 `gitee-sync-manual` 记忆执行:

1. 本地 push 到 GitHub(origin);用户手动同步 GitHub → gitee。
2. prod `ssh zbd` → `cd /root/mca-translation && git pull`。
3. 确认 prod `.env`:设 `NEXT_PUBLIC_BASE_PATH=/mca`;`NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL` 留空。
4. 构建 + 重启:`docker compose build frontend && docker compose up -d frontend nginx`。
5. APISIX 配置:`airoute.hubpd.com/mca` 与 `/mca/*` → upstream `10.19.1.95:8082`,**保留前缀**(不 strip),启用 WebSocket(Upgrade),TLS 终止。

- [ ] **Step 5: 生产验证清单(HTTPS/wss)**

打开 `https://airoute.hubpd.com/mca/`,逐项确认:

- [ ] 加载首页,跳 `/mca/workspace`(或 `/mca/login`)。
- [ ] 未登录 → 401 跳 `/mca/login`;登录成功跳 `/mca/workspace`。
- [ ] devtools Network:API 落 `/mca/api/...`(200)。
- [ ] devtools WS:`wss://airoute.hubpd.com/mca/api/ws/...` 连上并收到进度(非混合内容报错)。
- [ ] 文件上传、导出 docx 正常。
- [ ] `_next` 静态资源 200;favicon 加载。
- [ ] LAN 直连 `http://10.19.1.95:8082/` → 301 跳 `/mca/`。

- [ ] **Step 6: 更新生产部署记忆**

生产验证通过后,更新 `production-deployment` 记忆:公网入口为 `https://airoute.hubpd.com/mca/`(APISIX 保留前缀),LAN 直连改为 `http://10.19.1.95:8082/mca/`(根路径重定向),`NEXT_PUBLIC_BASE_PATH=/mca` 需在重建前端时注入。

---

## Self-Review

**Spec coverage:**
- APISIX 契约 → Task 6 Step 4-5(部署指令,APISIX 不在仓库)。
- nginx 改动 → Task 5。
- `next.config.ts` basePath → Task 4 Step 1。
- `api-client.ts` API_BASE + 3× login href → Task 3 Step 3。
- 4 处 login href(含 layout ×1)→ Task 3 Step 3-4。
- `ws-client.ts` 协议自适应 + 前缀 → Task 2。
- Dockerfile ARG/ENV → Task 4 Step 2。
- docker-compose build arg → Task 4 Step 3。
- `.env.example` 文档化 → Task 4 Step 4。
- public/ 资源审计 → Task 4 Step 5。
- 后端不改 → Global Constraints 声明,无任务(符合 Out of Scope)。
- 部署与验证清单 → Task 6。

**Placeholder scan:** 无 TBD/TODO;所有代码步骤含完整代码,所有验证步骤含具体命令与期望输出。

**Type consistency:** `BASE_PATH`、`loginPath`、`buildWsBase` 在定义(Task 1/2)与使用(Task 2/3)处签名一致;`API_BASE` 派生公式(`NEXT_PUBLIC_API_URL || BASE_PATH`)与 spec 一致。
