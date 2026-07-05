# CulturalBridge — MCA 文化适配翻译平台

面向国际传播内容编辑的 AI 文化适配转译平台。输入中文文本，选择文体、目标语言和文化适配参数，即可获得 LLM 驱动的翻译结果、风险标注、术语建议与审校报告。

## 核心能力

- **文化感知翻译**：支持 8 大文化圈 × 6 类受众类型，在翻译中注入文化约束与受众适配策略。
- **风险标注与处理**：自动识别译文中的文化负载词、政治隐喻等风险片段，以内联高亮 + Popover 形式展示说明，支持接受 / 忽略 / 回退操作。
- **转译决策日志**：记录翻译管线各阶段（文化预处理、术语检索、翻译约束、风险标注、替换建议）的关键决策与推理，帮助编辑理解 AI 选择。
- **高语境术语内联高亮**：输入区实时高亮术语库命中与 LLM 识别的文化负载词，悬停查看分类、风险备注与转译建议。
- **术语管理（RAG 知识库）**：政治话语、文化隐喻等术语的 CRUD 管理，支持关键词 + 向量语义双路检索。
- **审校服务**：对照审校 / 独立审校双模式，四维评分（忠实度、流畅度、术语、风格）+ 内联标注 + 可导出 Markdown 报告。
- **文件上传**：支持 .txt / .docx / .pdf 文本提取，自动填入编辑器。
- **导出功能**：.txt 纯文本前端导出；.docx 原文 + 译文双段，风险标注转为 Word 批注。
- **管理员后台**：用户管理、积分调整、登录状态查看。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Zustand |
| 后端 | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Celery |
| LLM | 百炼 DashScope (qwen-plus / qwen-max) |
| 数据库 | PostgreSQL 16 + pgvector, Redis 7 |
| 部署 | Docker Compose + nginx 反向代理 |

## 系统架构

```
┌─────────────────┐      HTTP/WebSocket       ┌─────────────────┐
│   Next.js 前端   │ ◄───────────────────────► │  FastAPI 后端    │
│   (port 3000)   │                           │  (port 8000)    │
└─────────────────┘                           └────────┬────────┘
                                                       │
                              ┌────────────────────────┼────────────────────────┐
                              │                        │                        │
                              ▼                        ▼                        ▼
                        ┌──────────┐          ┌─────────────┐          ┌──────────────┐
                        │ PostgreSQL│          │    Redis    │          │ Celery Worker │
                        │  + pgvector│          │   (broker)  │          │               │
                        └──────────┘          └─────────────┘          └──────────────┘
```

### 翻译管线

```
输入文本
  → 文体选择 → 文化圈选择 → 受众类型
  → 文化预处理（Cultural Preprocess）
  → 术语检索（RAG）
  → LLM 翻译（注入 cultural_constraints）
  → 风险标注
  → 替换建议
  → 返回结果 + 决策日志
```

## 项目结构

```
mca-translation/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI 路由（auth, jobs, upload, reviews, glossary, admin 等）
│   │   ├── core/           # 配置、安全、数据库
│   │   ├── llm/            # 百炼 Bailian 客户端与提示词模板
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 翻译管线、文化预处理、RAG 检索、审校、导出
│   │   ├── constants/      # 文化圈、受众类型、术语分类
│   │   ├── main.py         # FastAPI 入口
│   │   └── celery_app.py   # Celery 应用
│   ├── alembic/            # 数据库迁移
│   ├── migrations/         # 额外迁移脚本
│   ├── tests/              # 测试
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                # Next.js App Router
│   ├── components/         # React 组件（workspace, review, glossary）
│   ├── stores/             # Zustand 状态管理
│   ├── lib/                # API 客户端与工具
│   └── package.json
├── nginx/
│   └── nginx.conf          # 生产环境反向代理配置
├── docker-compose.yml      # 完整生产环境
├── docker-compose.dev.yml  # 仅开发依赖（pg + redis）
├── docs/                   # 设计文档与实施计划
└── README.md
```

## 快速开始（Docker Compose）

### 1. 克隆仓库

```bash
git clone https://github.com/deepeye/mca-translation.git
cd mca-translation
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，至少填入：

```bash
BAILIAN_API_KEY=your-bailian-api-key
SECRET_KEY=change-me-to-a-random-string
```

### 3. 启动完整服务

```bash
docker compose up -d
```

访问：

- 前端：http://localhost
- 后端 API：http://localhost/api
- API 文档：http://localhost:8000/docs（直接访问后端容器）

## 本地开发

### 1. 启动基础设施

```bash
docker compose -f docker-compose.dev.yml up -d
```

这会启动 PostgreSQL 与 Redis。

### 2. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

运行迁移并启动服务：

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

后端默认运行在 http://localhost:8000，API 文档见 http://localhost:8000/docs。

运行测试：

```bash
pytest -v
```

### 3. 前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端默认运行在 http://localhost:3000。

运行测试：

```bash
pnpm test
```

## 环境变量

后端 `.env` 关键配置：

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://culturalbridge:culturalbridge@localhost:5432/culturalbridge` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT 签名密钥 | 随机字符串 |
| `BAILIAN_API_KEY` | 百炼 API Key | `sk-...` |
| `BAILIAN_BASE_URL` | 百炼兼容端点 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MCA_FILE_STORE_DIR` | 上传文件存储目录 | `./uploads` |
| `FRONTEND_URL` | 前端地址（CORS） | `http://localhost:3000` |
| `RUN_MIGRATIONS` | 启动时是否自动执行 Alembic 迁移 | `true` |
| `NEXT_PUBLIC_API_URL` | 前端构建时 API 基础地址 | `http://localhost` |
| `NEXT_PUBLIC_WS_URL` | 前端构建时 WebSocket 基础地址 | `ws://localhost` |

生产环境部署时通过 `.env` 提供上述变量，`docker-compose.yml` 会将其注入对应服务。

## 部署说明

生产环境使用 Docker Compose 一键部署：

```bash
docker compose up -d
```

包含以下服务：

- **nginx**：80 端口入口，反向代理到前端与后端，`/api/ws/*` 支持 WebSocket 长连接，上传大小限制 10MB，自带 `/health` 健康检查。
- **frontend**：Next.js standalone 生产构建。
- **backend**：FastAPI 服务，带自动迁移入口（`RUN_MIGRATIONS=true`）。
- **celery-worker**：异步任务工作进程。
- **postgres**：PostgreSQL 16 + pgvector。
- **redis**：Redis 7 消息队列与缓存。

上传文件通过 Docker volume `uploads` 持久化。首次部署建议创建初始管理员：

```bash
docker compose exec backend python scripts/seed_admin.py
```

更多部署细节请参考 `docs/superpowers/specs/` 中的设计文档。

## 测试

- 后端：`cd backend && pytest -v`
- 前端：`cd frontend && pnpm test`

## 文档

- 项目说明与开发约定：`CLAUDE.md`
- 产品需求与设计：`docs/PRD_文化适配AI转译系统.md`
- 实施计划：`docs/superpowers/plans/`
- 部署设计：`docs/superpowers/specs/`

## 许可证

MIT
