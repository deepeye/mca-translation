# CulturalBridge — MCA 文化适配翻译平台

## 项目概述

CulturalBridge（MCA Translation）是一个面向国际传播内容编辑的文化适配 AI 转译平台。用户输入中文文本，选择文体、目标语言和文化适配参数，获得 LLM 驱动的翻译结果及风险标注。

**核心能力：** 文化感知翻译（8 文化圈 × 6 受众类型）、风险标注与处理、术语管理（RAG 知识库）、审校服务（四维评分+内联标注）。

## Tech Stack

| 层 | 技术 |
|---|---|
| **前端** | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand |
| **后端** | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Celery |
| **LLM** | 百炼 DashScope (qwen-plus / qwen-max) |
| **数据库** | PostgreSQL 16 + pgvector, Redis 7 |
| **部署** | Docker Compose |

## 项目结构

```
mca-translation/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, jobs, upload, reviews, glossary)
│   │   ├── core/         # config, security, database
│   │   ├── llm/          # Bailian client, prompt templates
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Translation pipeline, cultural preprocess, RAG retrieval, reviews
│   │   ├── constants/    # Cultural spheres, audience types, term taxonomy
│   │   ├── main.py       # FastAPI app entry
│   │   └── celery_app.py # Celery app
│   ├── migrations/       # Alembic
│   └── tests/
├── frontend/
│   ├── app/              # Next.js App Router pages (login, workspace, review, glossary)
│   ├── components/       # React components (workspace, review, glossary)
│   ├── stores/           # Zustand stores (workspace, translation, review)
│   └── lib/              # API client, utilities
├── docs/superpowers/
│   ├── specs/            # Design documents
│   └── plans/            # Implementation plans (checklist-based)
└── docker-compose.yml    # Full stack
    docker-compose.dev.yml # Dev dependencies only (pg + redis)
```

## 关键命令

### 后端
```bash
cd backend
uvicorn app.main:app --reload          # Dev server (需搭配 docker-compose.dev.yml 启动 pg/redis)
pytest -v                               # 运行测试
alembic upgrade head                    # 数据库迁移
```

### 前端
```bash
cd frontend
pnpm dev                                # Dev server (port 3000)
pnpm build                              # Production build
pnpm test                               # 测试
```

### Docker (完整环境)
```bash
docker compose up -d                    # 启动全部服务
docker compose -f docker-compose.dev.yml up -d  # 仅启动 pg + redis
docker compose down                     # 停止
```

### 开发流程
```bash
# 在本地开发时，先启动基础设施
docker compose -f docker-compose.dev.yml up -d
# 然后分别启动后端和前端 dev server
```

## 当前状态

- ✅ **全部 8 个实施计划已完成**（361 个步骤中 360 个完成，1 项已放弃）
- ✅ **文件上传功能已完成**（拖拽/选择 → .txt/.docx/.pdf 文本提取 → 自动填入 TextEditor）
- ✅ **转译决策日志功能已完成**（决策链路记录与展示）
- 所有计划文档在 `docs/superpowers/plans/`，设计文档在 `docs/superpowers/specs/`

## 功能模块速览

### 文化感知翻译管线
```
Input → 文体选择 → 文化圈选择 → 受众类型 → LLM 预处理
       → LLM 翻译（含 <cultural_constraints> 注入）
       → 风险标注 → 替换建议 → 返回结果
```
详情: `backend/app/services/translation.py` + `backend/app/llm/`

### 风险标注系统
- 内联 `<mark>` 标签高亮风险词段，hover Popover 显示详情
- 3 种风险操作: 接受 (accept) / 忽略 (dismiss) / 回退 (revert)
- 一键全部接受
- 风险说明及建议均为中文输出
详情: `backend/app/services/risk_annotation.py` + `frontend/components/workspace/`

### 转译决策日志
- 记录翻译管线各节点（文化预处理 / 术语检索 / 翻译约束 / 风险标注 / 替换建议）的关键决策与推理依据
- 从现有管线输出中提取，无额外 LLM 调用，不影响翻译质量
- 工作台译文区可折叠面板，按阶段分组展示，与风险标注内联高亮联动
- 阶段：`preprocess` / `cultural_detect`（输入期文化识别） / `glossary` / `translate` / `risk` / `suggestion`
详情: `backend/app/services/decision_log.py` + `frontend/components/workspace/decision-log-panel.tsx`

### 高语境术语内联高亮
- 输入区 textarea 上内联高亮（overlay 镜像层），覆盖两类高语境术语：
  - 术语库命中（政治话语/文化隐喻字面匹配，实时 800ms debounce）
  - LLM 文化负载词识别（隐喻/政治话语语义识别，手动「分析高语境词」按钮触发）
- 悬停高亮片段显示 Popover：分类、风险备注、转译建议（`suggested_rendering`）、适配理由
- 复用 `cultural_preprocess`，服务端计算文本偏移；重叠区间 glossary 优先
- 不改 `CULTURAL_PREPROCESS_PROMPT`，不影响翻译质量；LLM 失败/未选文化圈降级返回空
详情: `backend/app/api/glossary.py`（`/detect-cultural`）+ `frontend/components/workspace/inline-highlighter.tsx`

### 审校服务 (独立页面)
- 双模式: 对照审校（原文+译文） / 独立审校（仅译文）
- 四维评分: 忠实度 (fidelity) / 流畅度 (fluency) / 术语 (terminology) / 风格 (style)
- 内联标注 + 问题卡片 (IssueCard) + 可导出 Markdown 报告
详情: `backend/app/services/review.py` + `frontend/app/review/`

### 导出功能
- .txt 导出：纯文本，前端生成
- .docx 导出：原文 + 译文双段，风险标注为 Word 批注（comment），后端生成
详情: `backend/app/services/export_docx.py` + `backend/app/api/export.py`

### 术语管理 (RAG 知识库)
- Phase 1: 硬编码政治术语词典（15 组高优先级词汇）
- Phase 2: 双路检索（关键词 + pgvector 向量语义）
- 前端输入区 TermHighlighter 高亮提示
- 术语库管理页面（系统级 + 用户自定义 CRUD）
详情: `backend/app/services/glossary_retrieval.py` + `frontend/app/glossary/`

## 重要约定

1. **所有计划使用 checklist 追踪** — `- [x]` 表示完成，`- [ ]` 表示待完成
2. **使用 main 分支开发** — 直接提交到 main（单开发者模式）
3. **代码注释中英双语** — 重要逻辑使用中文注释
4. **API 认证** — JWT (python-jose)，token 存 localStorage，前端 ApiClient 自动管理
5. **LLM 提供商** — 百炼 DashScope（qwen-plus / qwen-max），已硬编码在 config.py 中
6. **数据库迁移** — 模型变更后需运行 `alembic revision --autogenerate -m "desc"` + `alembic upgrade head`
7. **前端样式** — Tailwind CSS + shadcn/ui，品牌色系：青绿 + 赤陶
8. **Next.js 版本注意** — 当前版本可能有 breaking changes，在 node_modules/next/dist/docs/ 中有官方指南
