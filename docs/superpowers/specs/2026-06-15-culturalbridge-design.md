# CulturalBridge 系统设计文档

**日期**: 2026-06-15
**状态**: 已确认
**基于**: PRD_文化适配AI转译系统.md v1.0

---

## 1. 设计决策摘要

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 目标用户 | 画像A：国际传播内容编辑 | MVP 聚焦，UI 重心在工作台和批量处理 |
| 技术起点 | 从零开始 | 当前仓库只有 PRD，不复用之前实现 |
| 部署模式 | 私有化部署 | 政府/官媒数据安全要求 |
| LLM 提供商 | 百炼优先 | 国内访问稳定，已验证可行 |
| 架构方案 | 全栈 Monorepo | Next.js BFF + FastAPI，职责清晰 |
| 配色 | 青绿 + 赤陶 | 汝窑天青×赤陶，文化辨识度，避开行业同质化 |
| 前端框架 | Next.js App Router + shadcn/ui | SSR + 组件可定制 |
| 状态管理 | Zustand（每语言独立 slice） | 避免多语言并发竞态 |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│  前端（Next.js App Router）                         │
│  - 工作台、术语库、历史记录、批量处理页面            │
│  - Zustand 状态管理（每语言独立 slice）              │
│  - WebSocket 接收转译进度                           │
├─────────────────────────────────────────────────────┤
│  BFF 层（Next.js API Routes / Server Actions）      │
│  - JWT 认证、请求代理                               │
│  - WebSocket 中转（转译进度推送）                    │
│  - 文件上传预处理                                   │
├─────────────────────────────────────────────────────┤
│  后端 API（FastAPI）                                │
│  - 转译任务 CRUD                                    │
│  - 术语库 CRUD + pgvector 语义检索                  │
│  - LLM 编排（5 步 prompt chain）                    │
│  - Celery 异步任务调度                              │
│  - 风险标注 + 接受度评分                            │
├─────────────────────────────────────────────────────┤
│  数据层                                             │
│  - PostgreSQL（业务数据 + pgvector 向量）            │
│  - Redis（Celery broker + 结果缓存）                │
│  - 本地文件存储（私有化部署不用 S3）                 │
├─────────────────────────────────────────────────────┤
│  外部服务                                           │
│  - 百炼 LLM API（主转译引擎）                       │
│  - [后续] Anthropic Claude API（备选）              │
└─────────────────────────────────────────────────────┘
```

### 关键决策

1. **文件存储**：本地文件系统（`MCA_FILE_STORE_DIR`），私有化部署不需要 S3。如需 S3 兼容，加一层抽象。
2. **LLM 编排**：分步调用，5 步流水线。每步独立，错误定位更清晰。
3. **前端状态**：每语言独立 Zustand slice，避免竞态，支持单语言重试。
4. **WebSocket**：Next.js BFF 维护与 FastAPI 的 SSE/WebSocket 连接，统一推送给浏览器。

---

## 3. 配色与视觉设计

### 配色方案：青绿 + 赤陶

灵感：汝窑天青（celadon）× 赤陶 — 宋代青瓷的温润配上大地色的厚重。

| 角色 | 色值 | 用途 |
|------|------|------|
| 主色 | `#0D9488` (Teal) | 导航栏、按钮、标签、交互元素 |
| 强调色 | `#C2410C` (Terracotta) | 品牌标识、CTA、风险标注高优先级 |
| 次级色 | `#14B8A6` (Teal light) | 悬停态、次要交互 |
| 次级强调 | `#EA580C` (Orange) | 风险标注中等级、进度指示 |
| 文字色 | `#134E4A` (Teal dark) | 正文、标题 |
| 背景色 | `#F0FDFA` (Teal lightest) | 页面背景、面板背景 |
| 导航栏背景 | `#134E4A` | 顶部导航、侧边栏 |
| 高风险 | `#EF4444` (Red) | 高风险标注 |
| 成功 | `#10B981` (Emerald) | 完成状态、通过 |

### 视觉风格

Swiss Modernism 2.0：严格网格、清晰层级、最小装饰、数学化间距。

### 字体

Plus Jakarta Sans（标题+正文统一）：现代、专业、友好，适合 SaaS 仪表盘。

### 布局

- 工作台：左右分栏（左 42% 输入 / 右 58% 输出）
- 导航栏：高度 56px，全宽
- 决策日志：底部可折叠（默认折叠，展开 ~200px）
- 设计逻辑：左右对应用户心理模型「我写，系统返」

---

## 4. 数据模型

严格遵循 PRD 第五章字段名和结构（约束项）。补充 PRD 未覆盖的部分。

### 核心实体

```
User
  id: UUID
  username: str
  hashed_password: str
  created_at: datetime

TranslationJob
  id: UUID
  user_id: FK → User
  status: pending | processing | completed | failed | partial
  source_text: str (max 10000)
  genre: political | news | policy | brand
  genre_confidence: float (0-1)
  detected_terms: JSON[]
  strategy: semantic_equivalence | audience_first | literal_reference
  target_languages: str[] (BCP-47, max 10)
  glossary_ids: UUID[]
  created_at: datetime

TranslationResult（每语言独立，从 PRD results 拆出）
  id: UUID
  job_id: FK → TranslationJob
  language: str (BCP-47)
  status: idle | streaming | completed | failed | partial
  translated_text: text
  acceptance_score: int (0-100, -1 = 未计算)
  audience_baseline: str
  risk_annotations: JSON[]
  quality_confidence: float (0-1)
  decision_log_ids: UUID[]
  created_at: datetime

DecisionLog
  id: UUID
  job_id: FK → TranslationJob
  target_language: str
  decision_type: term_handling | metaphor_replacement | narrative_reordering | omission_suggestion
  source_span: int[2]
  target_span: int[2]
  chosen_approach: str
  alternatives_considered: JSON[]
  knowledge_source: system_kb | user_glossary | llm_generation
  created_at: datetime

GlossaryEntry
  id: UUID
  owner_id: UUID
  source_term: str
  translations: JSON{ lang: { preferred, alternatives, notes, applicable_genres } }
  risk_notes: str
  freshness_date: datetime
  version: str
  created_at: datetime
  updated_at: datetime
```

**与 PRD 的差异**：`TranslationResult` 从 `TranslationJob.results` 嵌套结构拆为独立表。理由：每语言有独立状态机（streaming/completed/failed），需要独立查询和并发更新，嵌套结构会导致整行锁定。

---

## 5. API 设计

```
认证
  POST   /api/auth/login          → { access_token, token_type }
  POST   /api/auth/refresh        → { access_token, token_type }

转译任务
  POST   /api/jobs                → 创建任务（触发 Celery）
  GET    /api/jobs                → 任务列表（分页）
  GET    /api/jobs/:id            → 任务详情（含所有语言结果）
  POST   /api/jobs/:id/retry/:lang → 重试某语言转译
  DELETE /api/jobs/:id            → 删除任务

转译进度（WebSocket）
  WS     /api/ws/jobs/:id         → 实时推送步骤进度
  事件格式: { type: "chunk"|"step_complete"|"step_start"|"error",
              lang, step, totalSteps, stepLabel, delta }

术语库
  GET    /api/glossaries          → 术语列表（搜索+分页）
  POST   /api/glossaries          → 添加术语
  PUT    /api/glossaries/:id      → 编辑术语
  DELETE /api/glossaries/:id      → 删除术语
  POST   /api/glossaries/search   → 语义检索（pgvector）

历史记录
  GET    /api/history             → 转译历史（分页+筛选）

文件上传
  POST   /api/upload              → 上传文件（返回 file_id）
```

---

## 6. LLM 转译管线

### 5 步流水线

| 步骤 | 模型 | 职责 | 延迟目标 |
|------|------|------|---------|
| Step 1: 文体识别 & 术语标注 | qwen-plus | 分类+术语检测 | < 800ms |
| Step 2: 术语处理 | 无 LLM（RAG + 规则） | 术语库/知识库匹配 | < 200ms |
| Step 3: 主转译 | qwen-max | 流式生成译文 | p50 < 12s |
| Step 4: 文化隐喻替换 | qwen-plus | 隐喻等效替换 | < 3s |
| Step 5: 风险标注 & 评分 | qwen-plus | 风险识别+评分 | < 2s |

### 术语约束注入格式

Step 3 的 prompt 中以结构化约束注入术语决策：

```
[TERMINOLOGY_CONSTRAINTS]
"五位一体" → MUST_USE "Five-sphere Overall Plan" (source: user_glossary, priority: HIGH)
"以人民为中心" → SUGGEST "people-centered" with note "may trigger populist association" (source: system_kb, priority: MEDIUM)
"新型举国体制" → NEEDS_CONFIRMATION, candidates: [...] (source: system_kb, priority: LOW)
[/TERMINOLOGY_CONSTRAINTS]
```

优先级：用户术语 > 系统知识库 > LLM 自由生成。

### 流式输出

Step 3 使用 streaming，WebSocket 消息格式：

```json
{"type": "chunk", "lang": "en-GB", "delta": "Over the past "}
{"type": "step_complete", "lang": "en-GB", "step": 3}
```

前端用 `requestAnimationFrame` 批量更新 DOM。

### P0 简化

P0 阶段：Step 1 仅手动选择文体，Step 2 用硬编码 10-20 条术语测试，Step 4 跳过，Step 5 仅基础风险标注。实质上 P0 = Step 3 核心转译 + 简化版 Step 5。

---

## 7. 前端架构

### 页面路由

```
/                    → 重定向到 /workspace
/workspace           → 工作台（核心页面）
/glossary            → 术语库管理
/history             → 转译历史记录
/batch               → 批量处理
/settings            → 设置
/login               → 登录页
```

### 组件树（工作台）

```
<WorkspacePage>
  <AppShell>
    <TopNav>
    <WorkspaceLayout>
      <InputPanel>                     ← 左侧 42%
        <GenreSelector>
        <TextEditor>
          <TermHighlight>
          <CharCounter>
        <StrategySelector>
        <GlossaryOverride>
        <TranslateButton>
      <OutputPanel>                    ← 右侧 58%
        <LanguageTabs>
        <TranslationResult>
          <InlineAnnotation>
          <RiskHighlight>
        <RiskSummary>
        <ScoreDisplay>
        <ResultActions>
      <DecisionLogPanel>              ← 底部可折叠
        <DecisionEntry>
    </WorkspaceLayout>
  </AppShell>
</WorkspacePage>
```

### 状态管理

```
useWorkspaceStore
  ├─ input: { text, genre, strategy, detectedTerms }
  ├─ languages: string[]
  └─ isTranslating: boolean

useTranslationStore                  ← 每语言独立 slice
  [lang: string]: {
    status, currentStep, totalSteps, stepLabel,
    translatedText, riskAnnotations, acceptanceScore, decisionLogs
  }

useGlossaryStore
  ├─ entries: GlossaryEntry[]
  └─ searchQuery: string
```

### 内联标注实现

转译结果中的注释标记和风险高亮用后端返回的 `span` 偏移量定位，前端渲染为绝对定位的 `<span>` 覆盖层。悬停弹出 Popover（shadcn/ui Popover 组件）。

### UI 组件库

shadcn/ui（Tailwind + Radix UI）：无运行时依赖、完全可定制、与 Next.js 兼容。

---

## 8. 部署架构

### Docker Compose 服务

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| frontend | 自建 | 3000 | Next.js + BFF |
| backend | 自建 | 8000 | FastAPI |
| celery-worker | 自建（同 backend） | - | Celery worker (-c 4) |
| celery-beat | 自建（同 backend） | - | 定时任务 |
| postgres | pgvector/pgvector:pg16 | 5432 | 业务数据 + 向量 |
| redis | redis:7-alpine | 6379 | 队列 + 缓存 |

### 本地开发

```bash
docker compose -f docker-compose.dev.yml up -d   # 仅 PostgreSQL + Redis
cd backend && uvicorn app.main:app --reload       # 后端热重载
cd backend && celery -A app.celery worker -l info  # Celery
cd frontend && npm run dev                         # 前端热重载
```

### 生产部署

```bash
docker compose up -d --build
```

---

## 9. MVP（P0）范围

严格按 PRD 第九章 P0 功能集：

- [ ] 文本输入界面（粘贴 + 文件上传）
- [ ] 文体手动选择（4 种）
- [ ] 目标语言选择（英/德/日/西/法 5 种）
- [ ] 调用百炼 LLM 基础转译（无 RAG，直接 prompt）
- [ ] 结果展示与复制
- [ ] 单语言 .txt 导出
- [ ] JWT 认证（登录/刷新）
- [ ] Docker Compose 部署

P0 不包含：自动文体检测、RAG 知识库、风险标注、接受度评分、决策日志、批量处理、术语库管理、.docx 导出。

---

*文档结束*
*CulturalBridge 设计文档 | 2026-06-15*
