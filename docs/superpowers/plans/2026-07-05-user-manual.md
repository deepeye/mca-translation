# CulturalBridge 使用手册实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CulturalBridge 创建一份中文使用手册，同时以 `docs/USER_MANUAL.md` 仓库文档和前端 `/help` 应用内页面两种形式交付。

**Architecture:** 手册源文件唯一保存在 `docs/USER_MANUAL.md`。通过 npm `predev`/`prebuild` 脚本以及 Docker 构建流程将其复制到 `frontend/public/USER_MANUAL.md`，使 Next.js 在构建时即可读取。`/help` 路由使用服务端组件加载 Markdown、转换图片路径、提取目录，并用 `react-markdown` + 手动 Tailwind 样式渲染内容。

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, react-markdown, remark-gfm

## Global Constraints

- 手册语言：仅中文。
- 单一事实来源：`docs/USER_MANUAL.md`。
- Markdown 中图片引用约定：`![说明](./help/xxx.png)`。
- 应用内图片路径：`/help/xxx.png`。
- 源图片目录：`docs/help/`，构建时同步到 `frontend/public/help/`。
- 帮助页面路由：`/help`。
- 使用现有前端技术栈与目录约定；新增组件放在 `frontend/components/help/`，工具放在 `frontend/lib/help.ts`。
- 不使用 `@tailwindcss/typography`，通过 `react-markdown` 的 `components` 属性手动映射样式。

---

## 文件结构总览

创建或修改以下文件：

```
mca-translation/
├── docs/
│   ├── USER_MANUAL.md                    # 新建：手册源文件
│   └── help/                             # 新建：截图源目录
│       ├── workspace-overview.svg
│       ├── risk-annotation.svg
│       ├── inline-highlight.svg
│       ├── decision-log.svg
│       ├── history-detail.svg
│       ├── review-scoring.svg
│       ├── glossary-page.svg
│       └── admin-users.svg
├── frontend/
│   ├── app/(main)/help/
│   │   ├── page.tsx                      # 新建：/help 路由
│   │   └── layout.tsx                    # 新建：帮助页布局
│   ├── components/help/
│   │   └── help-content.tsx              # 新建：Markdown 渲染组件
│   ├── lib/help.ts                       # 新建：加载/解析/目录提取工具
│   ├── public/help/                      # 新建：docs/help/ 的同步副本
│   ├── app/(main)/layout.tsx             # 修改：增加“使用手册”导航链接
│   ├── package.json                      # 修改：新增依赖与脚本
│   ├── .gitignore                        # 修改：忽略生成的手册资源
│   ├── Dockerfile                        # 修改：构建上下文改为根目录，复制 docs 文件
│   └── next.config.ts                    # 修改：忽略 public/USER_MANUAL.md 生成的构建产物（可选）
├── docker-compose.yml                    # 修改：frontend 构建上下文改为根目录
```

---

### Task 1: 安装 Markdown 渲染依赖

**Files:**
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `react-markdown` 与 `remark-gfm` 可用于后续组件。

- [ ] **Step 1: 添加依赖**

在 `frontend/package.json` 的 `dependencies` 中新增：

```json
"react-markdown": "^10.0.0",
"remark-gfm": "^4.0.0",
"rehype-slug": "^6.0.0",
"github-slugger": "^2.0.0"
```

说明：
- `react-markdown`：渲染 Markdown。
- `remark-gfm`：支持 GitHub Flavored Markdown（表格、删除线等）。
- `rehype-slug`：自动为标题添加 `id` 属性，使目录锚点跳转可用。
- `github-slugger`：与 `rehype-slug` 使用相同的 slug 算法，确保目录 `id` 与标题 `id` 一致。

- [ ] **Step 2: 安装依赖**

Run: `cd frontend && pnpm install`

Expected: `pnpm-lock.yaml` 更新，`node_modules` 中出现 `react-markdown` 与 `remark-gfm`。

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(deps): add react-markdown and remark-gfm for help page"
```

---

### Task 2: 配置手册文件同步脚本

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/Dockerfile`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `docs/USER_MANUAL.md`（将在 Task 6/7 创建）。
- Produces: 开发/生产环境下 `frontend/public/USER_MANUAL.md` 均存在且与源文件一致。

- [ ] **Step 1: 添加 npm 脚本**

在 `frontend/package.json` 的 `scripts` 中新增：

```json
"predev": "mkdir -p public/help && cp -r ../docs/help/* public/help/ 2>/dev/null || true && cp ../docs/USER_MANUAL.md public/USER_MANUAL.md || true",
"prebuild": "mkdir -p public/help && cp -r ../docs/help/* public/help/ 2>/dev/null || true && cp ../docs/USER_MANUAL.md public/USER_MANUAL.md || true"
```

说明：
- `predev` 在 `pnpm dev` 之前自动执行。
- `prebuild` 在 `pnpm build` 之前自动执行。
- 同时同步 `docs/help/` 中的图片到 `public/help/`。
- `|| true` 防止 docs 文件暂时不存在时构建失败（实施初期 Task 1-5 可能先于 Task 6 执行）。

- [ ] **Step 2: 更新 .gitignore**

在 `frontend/.gitignore` 末尾追加：

```gitignore
# generated user manual assets
public/USER_MANUAL.md
public/help/
```

说明：
- `public/USER_MANUAL.md` 与 `public/help/` 是从 `docs/` 同步的构建产物，不应提交到仓库。
- 源文件始终保留在 `docs/USER_MANUAL.md` 与 `docs/help/`。

- [ ] **Step 2: 更新 Dockerfile 构建上下文与复制逻辑**

将 `frontend/Dockerfile` 整体替换为：

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@10.24.0 --activate && pnpm install --frozen-lockfile
COPY frontend/. .
COPY docs/USER_MANUAL.md ./public/USER_MANUAL.md
COPY docs/help/. ./public/help/
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

说明：
- 构建上下文将改为项目根目录，因此 COPY 路径需显式加 `frontend/` 前缀。
- `docs/USER_MANUAL.md` 从根目录复制到 `public/USER_MANUAL.md`。
- `docs/help/` 从根目录复制到 `public/help/`。

- [ ] **Step 3: 更新 docker-compose.yml 前端构建上下文**

将 `docker-compose.yml` 中 `frontend` 服务改为：

```yaml
  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost}
        NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL:-ws://localhost}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/.gitignore frontend/Dockerfile docker-compose.yml
git commit -m "build: sync docs/USER_MANUAL.md and docs/help/ into frontend public folder"
```

---

### Task 3: 创建帮助页工具函数

**Files:**
- Create: `frontend/lib/help.ts`
- Test: `frontend/lib/help.test.ts`

**Interfaces:**
- Produces:
  - `loadUserManual(): Promise<string>`
  - `transformImagePaths(content: string): string`
  - `extractHeadings(content: string): Array<{ level: number; text: string; id: string }>`

- [ ] **Step 1: 编写失败的测试**

创建 `frontend/lib/help.test.ts`：

```typescript
import { describe, it, expect } from "vitest";
import { transformImagePaths, extractHeadings } from "./help";

describe("transformImagePaths", () => {
  it("replaces ./help/ with /help/", () => {
    const input = "![工作台](./help/workspace-overview.svg)";
    expect(transformImagePaths(input)).toBe("![工作台](/help/workspace-overview.svg)");
  });

  it("leaves other paths unchanged", () => {
    const input = "![其他](/other/image.png)";
    expect(transformImagePaths(input)).toBe("![其他](/other/image.png)");
  });
});

describe("extractHeadings", () => {
  it("extracts h2 and h3 with github-compatible ids", () => {
    const input = `## 快速开始\n### 登录\n## 术语库`;
    const headings = extractHeadings(input);
    expect(headings).toEqual([
      { level: 2, text: "快速开始", id: "快速开始" },
      { level: 3, text: "登录", id: "登录" },
      { level: 2, text: "术语库", id: "术语库" },
    ]);
  });

  it("generates unique ids for duplicate headings", () => {
    const input = `## 登录\n### 登录`;
    const headings = extractHeadings(input);
    expect(headings[0].id).toBe("登录");
    expect(headings[1].id).toBe("登录-1");
  });

  it("handles punctuation and spaces", () => {
    const input = `## 接受 / 忽略 / 回退操作`;
    const headings = extractHeadings(input);
    expect(headings[0].id).toBe("接受-忽略-回退操作");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && pnpm test lib/help.test.ts`

Expected: FAIL，提示 `Cannot find module './help'` 或函数未定义。

- [ ] **Step 3: 实现工具函数**

创建 `frontend/lib/help.ts`：

```typescript
import { readFile } from "fs/promises";
import path from "path";
import { slug } from "github-slugger";

const MANUAL_PATH = path.join(process.cwd(), "public", "USER_MANUAL.md");

export async function loadUserManual(): Promise<string> {
  return readFile(MANUAL_PATH, "utf-8");
}

export function transformImagePaths(content: string): string {
  return content.replace(/\.\/help\//g, "/help/");
}

export interface Heading {
  level: number;
  text: string;
  id: string;
}

export function extractHeadings(content: string): Heading[] {
  const headings: Heading[] = [];
  const lines = content.split("\n");

  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.+)$/);
    if (!match) continue;

    const level = match[1].length;
    const text = match[2].trim();
    const id = slug(text);

    headings.push({ level, text, id });
  }

  return headings;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && pnpm test lib/help.test.ts`

Expected: PASS，所有断言通过。

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/help.ts frontend/lib/help.test.ts
git commit -m "feat(help): add utilities to load manual, transform paths, extract TOC"
```

---

### Task 4: 创建 Markdown 渲染组件

**Files:**
- Create: `frontend/components/help/help-content.tsx`
- Test: `frontend/components/help/help-content.test.tsx`

**Interfaces:**
- Consumes: Markdown 字符串。
- Produces: `HelpContent` 组件，渲染带样式的 HTML。

- [ ] **Step 1: 编写失败的测试**

创建 `frontend/components/help/help-content.test.tsx`：

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HelpContent } from "./help-content";

describe("HelpContent", () => {
  it("renders markdown headings and paragraphs", () => {
    render(<HelpContent content="## 快速开始\n\n欢迎使用。" />);
    expect(screen.getByRole("heading", { name: "快速开始" })).toBeInTheDocument();
    expect(screen.getByText("欢迎使用。")).toBeInTheDocument();
  });

  it("renders a table", () => {
    render(<HelpContent content="| A | B |\n|---|---|\n| 1 | 2 |" />);
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && pnpm test components/help/help-content.test.tsx`

Expected: FAIL，组件不存在。

- [ ] **Step 3: 实现组件**

创建 `frontend/components/help/help-content.tsx`：

```typescript
"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";

interface HelpContentProps {
  content: string;
}

export function HelpContent({ content }: HelpContentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSlug]}
      components={{
        h1: ({ children }) => <h1 className="mb-6 text-3xl font-bold text-foreground">{children}</h1>,
        h2: ({ children }) => (
          <h2 className="mb-4 mt-8 border-b border-border pb-2 text-2xl font-semibold text-foreground">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="mb-3 mt-6 text-xl font-medium text-foreground">{children}</h3>
        ),
        p: ({ children }) => <p className="mb-4 leading-relaxed text-foreground">{children}</p>,
        ul: ({ children }) => <ul className="mb-4 list-disc pl-6 text-foreground">{children}</ul>,
        ol: ({ children }) => <ol className="mb-4 list-decimal pl-6 text-foreground">{children}</ol>,
        li: ({ children }) => <li className="mb-1">{children}</li>,
        a: ({ href, children }) => (
          <a href={href} className="text-teal hover:text-teal-dark hover:underline">
            {children}
          </a>
        ),
        code: ({ children }) => (
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm text-foreground">
            {children}
          </code>
        ),
        pre: ({ children }) => (
          <pre className="mb-4 overflow-x-auto rounded-lg bg-muted p-4 font-mono text-sm">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="mb-4 border-l-4 border-teal pl-4 italic text-muted-foreground">
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <table className="mb-4 w-full border-collapse border border-border text-sm">
            {children}
          </table>
        ),
        thead: ({ children }) => <thead className="bg-muted">{children}</thead>,
        th: ({ children }) => (
          <th className="border border-border px-3 py-2 text-left font-semibold">{children}</th>
        ),
        td: ({ children }) => <td className="border border-border px-3 py-2">{children}</td>,
        img: ({ src, alt }) => (
          <img
            src={src}
            alt={alt}
            className="mb-4 max-w-full rounded-lg border border-border"
          />
        ),
        hr: () => <hr className="my-8 border-border" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && pnpm test components/help/help-content.test.tsx`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/components/help/help-content.tsx frontend/components/help/help-content.test.tsx
git commit -m "feat(help): add HelpContent markdown renderer with Tailwind styles"
```

---

### Task 5: 创建 /help 页面与布局

**Files:**
- Create: `frontend/app/(main)/help/layout.tsx`
- Create: `frontend/app/(main)/help/page.tsx`
- Create: `frontend/components/help/scroll-to-top-button.tsx`

**Interfaces:**
- Consumes: `loadUserManual`, `transformImagePaths`, `extractHeadings`, `HelpContent`。
- Produces: 可访问的 `/help` 路由，带左侧目录导航。

- [ ] **Step 1: 创建帮助页布局**

创建 `frontend/app/(main)/help/layout.tsx`：

```typescript
export default function HelpLayout({ children }: { children: React.ReactNode }) {
  return children;
}
```

说明：
- 帮助页本身控制布局，无需额外包装。
- 页面整体可滚动，目录使用 `sticky` 定位保持在视口内。

- [ ] **Step 2: 创建回到顶部按钮组件**

创建 `frontend/components/help/scroll-to-top-button.tsx`：

```typescript
"use client";

import { ChevronUp } from "lucide-react";

export function ScrollToTopButton() {
  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className="fixed bottom-6 right-6 flex items-center gap-1 rounded-full bg-teal px-3 py-2 text-sm text-white shadow-lg hover:bg-teal-dark"
    >
      <ChevronUp className="h-4 w-4" />
      回到顶部
    </button>
  );
}
```

说明：
- 该组件需要客户端交互（`window.scrollTo`），因此标注 `"use client"`。

- [ ] **Step 3: 创建 /help 页面**

创建 `frontend/app/(main)/help/page.tsx`：

```typescript
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { HelpContent } from "@/components/help/help-content";
import { ScrollToTopButton } from "@/components/help/scroll-to-top-button";
import { loadUserManual, transformImagePaths, extractHeadings } from "@/lib/help";

export default async function HelpPage() {
  const rawContent = await loadUserManual();
  const content = transformImagePaths(rawContent);
  const headings = extractHeadings(rawContent);

  return (
    <div className="flex">
      <aside className="sticky top-0 h-fit max-h-screen w-64 shrink-0 overflow-y-auto border-r border-border bg-card p-4">
        <div className="mb-4 flex items-center gap-2">
          <Link
            href="/workspace"
            className="flex items-center gap-1 text-sm text-teal hover:text-teal-dark"
          >
            <ArrowLeft className="h-4 w-4" />
            返回工作台
          </Link>
        </div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">目录</h2>
        <nav className="space-y-1">
          {headings.map((h) => (
            <a
              key={h.id}
              href={`#${h.id}`}
              className={`block rounded px-2 py-1 text-sm hover:bg-muted ${
                h.level === 3 ? "pl-5 text-muted-foreground" : "font-medium text-foreground"
              }`}
            >
              {h.text}
            </a>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-8">
        <div className="mx-auto max-w-3xl">
          <HelpContent content={content} />
        </div>
        <ScrollToTopButton />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: 本地验证页面可访问**

Run: `cd frontend && pnpm dev`

Then open http://localhost:3000/help

Expected: 页面加载，左侧目录 sticky 显示，右侧显示手册内容（此时可能为占位或空，取决于 docs/USER_MANUAL.md 是否存在）。滚动后点击“回到顶部”可回到页面顶部。

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(main)/help/layout.tsx frontend/app/(main)/help/page.tsx frontend/components/help/scroll-to-top-button.tsx
git commit -m "feat(help): add /help route with TOC sidebar and back-to-top"
```

---

### Task 6: 在主布局中添加“使用手册”入口

**Files:**
- Modify: `frontend/app/(main)/layout.tsx`

**Interfaces:**
- Produces: 主导航中出现指向 `/help` 的链接。

- [ ] **Step 1: 添加导航链接**

在 `frontend/app/(main)/layout.tsx` 的 `<nav>` 中，在历史链接之后新增：

```tsx
<Link href="/help" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">使用手册</Link>
```

- [ ] **Step 2: 本地验证链接**

Run: `cd frontend && pnpm dev`

Open http://localhost:3000/workspace

Expected: 顶部导航出现“使用手册”，点击后跳转到 `/help`。

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(main)/layout.tsx
git commit -m "feat(ui): add user manual link to main navigation"
```

---

### Task 7: 编写使用手册第 1-2 章

**Files:**
- Create: `docs/USER_MANUAL.md`
- Create: `docs/help/workspace-overview.svg`
- Create: `docs/help/risk-annotation.svg`
- Create: `docs/help/inline-highlight.svg`
- Create: `docs/help/decision-log.svg`
- Create: `docs/help/history-detail.svg`
- Create: `docs/help/review-scoring.svg`
- Create: `docs/help/glossary-page.svg`
- Create: `docs/help/admin-users.svg`

**Interfaces:**
- Produces: `docs/USER_MANUAL.md` 包含第 1 章快速开始、第 2 章编辑/译者指南及占位图片引用。

- [ ] **Step 1: 创建占位 SVG 图片**

每个 SVG 文件内容类似，仅文字不同。以 `docs/help/workspace-overview.svg` 为例：

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">
  <rect width="800" height="450" fill="#F0FDFA"/>
  <text x="400" y="220" font-family="sans-serif" font-size="24" fill="#134E4A" text-anchor="middle">工作台截图占位图</text>
  <text x="400" y="260" font-family="sans-serif" font-size="16" fill="#0D9488" text-anchor="middle">请替换为真实界面截图</text>
</svg>
```

为其余 7 张图片创建相同结构但文字不同的 SVG：
- `risk-annotation.svg` → “风险标注截图占位图”
- `inline-highlight.svg` → “高语境术语高亮截图占位图”
- `decision-log.svg` → “转译决策日志截图占位图”
- `history-detail.svg` → “历史记录截图占位图”
- `review-scoring.svg` → “审校评分截图占位图”
- `glossary-page.svg` → “术语库截图占位图”
- `admin-users.svg` → “管理员用户管理截图占位图”

- [ ] **Step 2: 编写手册第 1-2 章**

创建 `docs/USER_MANUAL.md`，写入以下内容（后续 Task 8 继续追加）：

```markdown
# CulturalBridge 使用手册

## 第 1 章 快速开始

### 1.1 登录与注册

打开 CulturalBridge 后，使用管理员分配的账号登录。首次登录后可在“账户”页面查看积分余额与个人信息。

### 1.2 界面概览

登录后进入主界面，顶部导航依次为：

- **工作台**：进行文化适配翻译。
- **审校**：对译文进行四维审校。
- **术语库**：管理系统知识库与自定义术语。
- **历史**：查看过往翻译任务。
- **管理**（仅管理员可见）：用户与积分管理。
- **使用手册**：打开本页面。

![工作台概览](./help/workspace-overview.svg)

### 1.3 完成第一次翻译

1. 点击顶部 **工作台**。
2. 在左侧输入区粘贴中文原文，或点击上传按钮选择 `.txt` / `.docx` / `.pdf` 文件。
3. 选择文体、目标语言、文化圈与受众类型。
4. 点击 **开始翻译**。
5. 在右侧输出区查看译文、风险标注与决策日志。

## 第 2 章 内容编辑 / 译者指南

### 2.1 工作台翻译

#### 输入文本与文件上传

输入区支持直接粘贴文本或上传文件。上传后系统会自动提取文本并填入编辑器。目前支持的格式包括：

- `.txt`：纯文本文件
- `.docx`：Word 文档
- `.pdf`：PDF 文档

#### 选择文体、目标语言、文化圈、受众类型

翻译前需要配置以下参数：

| 参数 | 说明 | 示例 |
|---|---|---|
| 文体 | 原文所属文体类型 | 新闻稿、演讲稿、社论 |
| 目标语言 | 译文语言 | 英语（英国）、德语、法语 |
| 文化圈 | 目标受众所属文化圈 | 英美、西欧、东亚 |
| 受众类型 | 目标读者身份 | 普通公众、专业人士、政策研究者 |

#### 启动翻译与查看结果

参数配置完成后，点击 **开始翻译**。系统将依次执行文化预处理、术语检索、LLM 翻译、风险标注与替换建议，最终返回：

- 译文文本
- 内联风险标注
- 替换建议
- 转译决策日志

### 2.2 理解风险标注

风险标注以高亮形式出现在译文中，悬停可查看风险类型、说明与建议操作。

![风险标注](./help/risk-annotation.svg)

#### 风险类型与含义

常见风险类型包括：

- **文化负载词**：目标语读者可能缺乏文化背景理解的词汇。
- **政治隐喻**：涉及政治话语或意识形态的隐喻表达。
- **术语不一致**：与术语库推荐译法存在偏差。

#### 接受 / 忽略 / 回退操作

对于每个风险标注，你可以选择：

- **接受**：采纳系统建议的替换文本。
- **忽略**：保留当前译文，不再提示该风险。
- **回退**：撤销之前的接受/忽略操作，恢复原始译文。

也可以点击 **全部接受** 一键采纳所有建议。

### 2.3 高语境术语内联高亮

在输入区，系统会实时高亮两类高语境术语：

1. **术语库命中**：政治话语、文化隐喻等术语的字面匹配。
2. **LLM 文化负载词识别**：隐喻、政治话语等语义识别结果。

悬停高亮片段可查看分类、风险备注、推荐译法与适配理由。

![高语境术语高亮](./help/inline-highlight.svg)

> 注意：LLM 识别需要选择文化圈，未选择或识别失败时会降级返回空结果。

### 2.4 转译决策日志

决策日志记录翻译管线各阶段的关键决策，包括：

```
preprocess      → 文化预处理识别
 cultural_detect → 输入期文化识别
glossary        → 术语检索
translate       → 翻译约束注入
risk            → 风险标注
suggestion      → 替换建议
```

![决策日志](./help/decision-log.svg)

点击输出区下方的决策日志面板，可按阶段展开查看详细推理。

### 2.5 历史记录

所有翻译任务会自动保存到 **历史** 页面。你可以：

- 按文体、状态筛选任务。
- 点击任务查看详情。
- 点击 **加载到工作台** 将历史任务还原到工作台继续编辑。
- 删除不再需要的任务。

![历史记录](./help/history-detail.svg)

### 2.6 审校服务

#### 对照审校与独立审校

进入 **审校** 页面后，可选择两种模式：

- **对照审校**：同时查看原文与译文，逐句核对。
- **独立审校**：仅查看译文，专注于目标语流畅度。

#### 四维评分解读

审校完成后，系统给出四维评分：

| 维度 | 含义 |
|---|---|
| 忠实度 | 译文是否准确传达原文信息 |
| 流畅度 | 译文是否符合目标语表达习惯 |
| 术语 | 术语使用是否一致、准确 |
| 风格 | 文体、语气是否与原文匹配 |

![审校评分](./help/review-scoring.svg)

#### 内联标注与问题卡片

审校结果包含内联标注（问题位置高亮）与问题卡片（问题分类与修改建议）。点击问题卡片可定位到对应片段。

#### 导出 Markdown 审校报告

点击 **导出报告** 可下载 Markdown 格式的审校报告，便于离线归档或分享。

### 2.7 导出译文

#### .txt 纯文本导出

点击输出区的 **导出 .txt**，浏览器会下载纯文本文件，内容为当前译文。

#### .docx 导出

点击 **导出 .docx**，后端会生成包含原文、译文双段的 Word 文档，风险标注会自动转换为 Word 批注。

### 2.8 术语库管理

#### 查看系统知识库

进入 **术语库** 页面，系统知识库按术语分类展示，包含政治话语、文化隐喻等高优先级词汇。

![术语库](./help/glossary-page.svg)

#### 添加 / 编辑 / 删除自定义术语

在“添加自定义术语”区域输入中文术语，并至少填写一种目标语言的首选译法。保存后可随时编辑或删除。

#### 一键补齐其余译法

编辑自定义术语时，点击 **✨ 一键补齐其余译法 (LLM)**，系统会自动为未填写的语言生成推荐译法。
```

- [ ] **Step 3: 本地验证渲染**

Run: `cd frontend && pnpm dev`

Open http://localhost:3000/help

Expected:
- 左侧目录显示“第 1 章 快速开始”、“第 2 章 内容编辑 / 译者指南”等。
- 正文正确渲染标题、表格、列表、代码块、图片占位图。
- 图片路径 `/help/xxx.svg` 正常显示。

- [ ] **Step 4: Commit**

```bash
git add docs/USER_MANUAL.md docs/help/*.svg
# 注意：public/USER_MANUAL.md 与 public/help/ 是构建产物，已生成到 .gitignore 中；若未忽略，请确认不提交。
git commit -m "docs: add user manual chapters 1-2 with placeholder images"
```

---

### Task 8: 编写使用手册第 3-5 章

**Files:**
- Modify: `docs/USER_MANUAL.md`

**Interfaces:**
- Produces: 完整手册，包含管理员指南、FAQ 与场景教程。

- [ ] **Step 1: 追加管理员指南**

在 `docs/USER_MANUAL.md` 末尾追加：

```markdown
## 第 3 章 管理员指南

### 3.1 初始管理员创建

首次部署后，执行以下命令创建初始管理员：

```bash
docker compose exec backend python scripts/seed_admin.py
```

按提示输入邮箱与密码即可。

### 3.2 用户管理

进入 **管理 → 用户** 页面，管理员可以：

- 查看所有用户列表。
- 启用或禁用用户账号。
- 删除用户（需谨慎，删除后不可恢复）。

![管理员用户管理](./help/admin-users.svg)

### 3.3 积分调整

在用户列表中点击 **调整积分**，可为指定用户增加或减少积分。积分用于控制翻译、审校等操作的可用额度。

### 3.4 查看登录状态

用户详情中显示最近登录时间与状态，便于排查异常登录。
```

- [ ] **Step 2: 追加常见问题（FAQ）**

继续追加：

```markdown
## 第 4 章 常见问题（FAQ）

### 翻译结果不理想怎么办？

1. 检查文化圈与受众类型是否匹配目标读者。
2. 尝试更换目标语言变体（如 en-GB 与 en-US）。
3. 在术语库中添加相关术语，提升术语一致性。
4. 使用审校服务定位具体问题。

### 风险标注误报如何处理？

点击该风险标注，选择 **忽略**。忽略后该标注将不再高亮显示，但可随时通过 **回退** 恢复。

### 术语库未命中怎么办？

- 确认术语已存在于系统知识库或自定义术语中。
- 检查术语分类与文体适用范围是否匹配。
- 如仍无法命中，可手动添加自定义术语。

### 审校评分怎么看？

四维评分中，单项分数越低表示该维度问题越多。建议优先处理分数最低的维度，并结合内联标注逐项修改。

### 账号、积分、登录相关问题

- 忘记密码：联系管理员重置。
- 积分不足：联系管理员调整或等待配额刷新。
- 无法登录：检查账号是否被禁用，或联系管理员查看登录状态。
```

- [ ] **Step 3: 追加场景教程**

继续追加：

```markdown
## 第 5 章 场景教程

### 场景 1：政治话语对外传播翻译

**场景描述**：将一则中文政治新闻稿翻译为面向英美普通公众的英文新闻稿。

**操作步骤**：

1. 在工作台输入中文稿件。
2. 文体选择“新闻稿”，目标语言“英语（英国）”，文化圈“英美”，受众“普通公众”。
3. 点击 **开始翻译**。
4. 查看风险标注，重点检查政治隐喻与术语一致性。
5. 对合适的标注点击 **接受**，对误报点击 **忽略**。
6. 导出 .docx，留档审校。

**翻译管线流程**：

```
输入文本
  → 文体选择 → 文化圈选择 → 受众类型
  → 文化预处理（识别政治话语、文化隐喻）
  → 术语检索（RAG 知识库）
  → LLM 翻译（注入 cultural_constraints）
  → 风险标注
  → 替换建议
  → 返回结果 + 决策日志
```

### 场景 2：文化隐喻的目标语适配

**场景描述**：原文包含“摸着石头过河”等文化隐喻，需要让目标语读者理解其含义。

**操作步骤**：

1. 输入包含隐喻的中文文本。
2. 选择对应文化圈与受众类型。
3. 点击 **分析高语境词**，查看 LLM 识别的文化负载词。
4. 结合风险标注与决策日志，判断是否需要意译或加注。
5. 在历史记录中保存该任务，便于后续复用。

### 场景 3：多轮审校与导出工作流

**场景描述**：完成初译后，需要进行多轮审校并导出最终报告。

**操作步骤**：

1. 在工作台完成翻译并导出 .txt 备份。
2. 进入 **审校** 页面，选择“对照审校”模式。
3. 粘贴原文与译文，点击 **开始审校**。
4. 根据四维评分与问题卡片逐条修改译文。
5. 将修改后的译文重新粘贴到工作台，再次翻译或导出。
6. 最终导出 .docx 或 Markdown 审校报告。
```

- [ ] **Step 4: 本地验证完整手册**

Run: `cd frontend && pnpm dev`

Open http://localhost:3000/help

Expected:
- 左侧目录包含所有章节与三级标题。
- 点击目录项可平滑滚动到对应位置。
- FAQ 与场景教程内容正确渲染。
- 翻译管线流程图以代码块形式清晰显示。

- [ ] **Step 5: Commit**

```bash
git add docs/USER_MANUAL.md
git commit -m "docs: add user manual chapters 3-5 (admin, FAQ, scenarios)"
```

---

### Task 9: 替换占位图为真实截图

**Files:**
- Modify: `docs/help/*.svg` → `docs/help/*.png`
- Modify: `docs/USER_MANUAL.md` 中的图片引用

**Interfaces:**
- Produces: 手册中展示真实界面截图。

- [ ] **Step 1: 截取真实截图**

启动完整应用后，依次访问以下页面并截图，保存为 `docs/help/*.png`：

| 截图文件 | 来源页面 | 截取内容 |
|---|---|---|
| `workspace-overview.png` | `/workspace` | 输入区与输出区完整界面 |
| `risk-annotation.png` | `/workspace` | 鼠标悬停在风险高亮上，显示 Popover |
| `inline-highlight.png` | `/workspace` | 输入区高亮术语，显示 Popover |
| `decision-log.png` | `/workspace` | 决策日志面板展开 |
| `history-detail.png` | `/history` | 选中某条历史记录后的详情面板 |
| `review-scoring.png` | `/review` | 审校完成后的评分与问题卡片 |
| `glossary-page.png` | `/glossary` | 系统知识库与自定义术语区 |
| `admin-users.png` | `/admin/users` | 用户列表与管理按钮 |

建议截图宽度 1200px 左右，保存为 PNG 到 `docs/help/`。

- [ ] **Step 2: 更新 USER_MANUAL.md 中的图片引用**

将 `docs/USER_MANUAL.md` 中所有 `.svg` 引用替换为 `.png`，例如：

```markdown
![工作台概览](./help/workspace-overview.png)
```

- [ ] **Step 3: 删除占位 SVG 文件**

Run:

```bash
rm docs/help/*.svg
```

- [ ] **Step 4: 验证图片显示**

Run: `cd frontend && pnpm dev`

Open http://localhost:3000/help

Expected: 所有图片均显示真实界面截图，无 404。

- [ ] **Step 5: Commit**

```bash
git add docs/help/*.png docs/USER_MANUAL.md
git commit -m "docs: replace placeholder images with real screenshots"
```

---

### Task 10: 生产构建验证

**Files:**
- No file changes.

**Interfaces:**
- Produces: 确认 Docker 构建后 `/help` 页面正常可用。

- [ ] **Step 1: 本地生产构建**

Run:

```bash
cd frontend
pnpm prebuild
pnpm build
```

Expected: 构建成功，无 TypeScript 或构建错误。

- [ ] **Step 2: Docker 构建验证**

Run:

```bash
docker compose build frontend
```

Expected: 构建成功，`docs/USER_MANUAL.md` 被正确复制到 `public/USER_MANUAL.md`。

- [ ] **Step 3: 启动完整服务并访问 /help**

Run:

```bash
docker compose up -d
```

Open http://localhost/help

Expected: 页面正常显示，目录、内容、图片均无异常。

- [ ] **Step 4: Commit（如无需修改则跳过）**

---

## 验收标准

- [ ] `docs/USER_MANUAL.md` 包含完整的中文手册内容，结构清晰。
- [ ] `/help` 页面可正常访问并渲染 Markdown 内容。
- [ ] 目录导航可点击跳转，锚点链接正常工作。
- [ ] 图片在仓库预览和应用内均能正确显示。
- [ ] 应用内有明确的“使用手册”入口。
- [ ] FAQ 和场景教程覆盖用户常见痛点。
- [ ] Docker 构建成功，`/help` 在生产环境可用。
- [ ] 单元测试通过：`frontend/lib/help.test.ts`、`frontend/components/help/help-content.test.tsx`。

## 自我审查

### Spec 覆盖检查

| Spec 要求 | 对应任务 |
|---|---|
| 单一源文件 `docs/USER_MANUAL.md` | Task 2（同步脚本）、Task 7/8（内容编写） |
| 应用内 `/help` 页面 | Task 5 |
| 左侧目录导航 | Task 5 |
| 图片路径处理 | Task 3、Task 7/9 |
| 角色分章节 | Task 7/8 |
| FAQ 与场景教程 | Task 8 |
| 导航入口 | Task 6 |
| 生产 Docker 可用 | Task 2、Task 10 |

### Placeholder 扫描

- 无 “TBD”、“TODO”、“implement later”。
- 无 “添加适当错误处理” 等模糊描述。
- 每个任务均包含具体代码、命令与预期输出。
- 图片占位使用明确 SVG 文件并在 Task 9 替换为真实截图。

### 类型一致性检查

- `extractHeadings` 返回 `Heading[]`，在 `page.tsx` 中消费时直接使用 `level` / `text` / `id`。
- `loadUserManual` 返回 `Promise<string>`，与 `HelpContent` 的 `content: string` 匹配。
- `transformImagePaths` 输入输出均为 `string`。

## 执行交接

**计划已保存到 `docs/superpowers/plans/2026-07-05-user-manual.md`。**

两种执行方式可选：

1. **Subagent-Driven（推荐）**：为每个 Task 分配独立子代理，逐任务审查，快速迭代。
2. **Inline Execution**：在当前会话中使用 `superpowers:executing-plans` 批量执行任务，并在关键检查点暂停确认。

请选择一种方式开始实施。
