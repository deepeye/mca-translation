# 转译决策日志 — 翻译过程决策链路记录与展示

**日期**: 2026-07-01
**状态**: 设计已确认

## 1. 概述

### 1.1 背景

当前翻译平台已完成文化感知翻译管线（文化预处理 → RAG 术语检索 → 主翻译 → 风险标注 → 替换建议），各步骤已产出丰富的决策数据（文化负载词适配策略、术语命中、风险识别、替换建议等），但这些数据散落在管线中间结果中，用户只能看到最终译文和内联风险标注，无法追溯「为什么这样翻译」「哪些词做了文化适配」「为什么标记为高风险」。

数据库层面，`TranslationResult.decision_log_ids`（ARRAY UUID）字段早已预留，但尚无对应的 `decision_logs` 表和实现。

### 1.2 目标

- 记录每次翻译过程中 LLM 在各管线节点做出的关键决策及其推理依据
- 提供独立 API 查询某个任务/某个语言译文的所有决策日志
- 在工作台译文区提供「决策日志」折叠面板，按阶段分组展示
- 与现有风险标注内联高亮联动（点击 `<mark>` 跳转到对应决策条目）

### 1.3 非目标

- 不新增额外 LLM 调用（仅提取现有管线产出的数据）
- 不修改主翻译 Prompt（不影响翻译质量）
- 不做决策日志的导出功能（后续按需添加）
- 不做跨任务决策对比分析（后续按需添加）

## 2. 设计决策

### 2.1 方案选择：管线数据提取（方案 A）

| 方案 | 决策 |
|---|---|
| 方案 A：管线数据提取 — 从现有各步骤输出中结构化提取决策 | 💡 选定 — 零额外 LLM 成本、零延迟增加、不影响翻译质量 |
| 方案 B：翻译后追加推理分析 — 额外 LLM 调用生成深度推理 | ❌ 舍弃 — 成本/延迟高，Phase 2 视需求再叠加 |
| 方案 C：增强主翻译 Prompt 一次性输出 — 译文+决策同返回 | ❌ 舍弃 — 结构化输出影响翻译质量，Prompt 调优成本高 |

### 2.2 存储方案：独立 `decision_logs` 表

| 方案 | 决策 |
|---|---|
| 独立 `decision_logs` 表 + `decision_log_ids` 关联 | 💡 选定 — 复用已预留字段，支持按 stage 查询/索引，schema 可独立演进 |
| JSONB 数组内嵌在 `translation_results` | ❌ 舍弃 — 查询/过滤不便，schema 变更需迁移全量数据 |

## 3. 数据库与模型设计

### 3.1 新增 `decision_logs` 表

```python
# backend/app/models/decision_log.py

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_jobs.id"), index=True
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_results.id"), index=True
    )
    # 决策阶段：preprocess / glossary / translate / risk / suggestion
    stage: Mapped[str] = mapped_column(String(16), index=True)
    # 决策类型标签，如 culture_term_adaptation / risk_identified
    decision_type: Mapped[str] = mapped_column(String(48))
    source_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)  # 触发决策的原文片段
    target_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)  # 译文对应片段
    decision: Mapped[str] = mapped_column(Text)  # 决策内容摘要（一句话）
    reasoning: Mapped[str] = mapped_column(Text)  # 推理依据
    confidence: Mapped[str | None] = mapped_column(String(8), nullable=True)  # high/medium/low/None
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)  # 阶段特有扩展数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

### 3.2 各阶段提取的决策类型

| stage | decision_type | 数据来源 | reasoning 来自 | confidence 来自 |
|---|---|---|---|---|
| `preprocess` | `culture_term_adaptation` | `cultural_preprocess()` 返回的每个 `culture_loaded_terms` 条目 | 条目 `reason` 字段 | `culture_gap` (high/medium/low) |
| `glossary` | `term_retrieved` | `retrieve_glossary_terms()` 命中的每个术语 | 术语 `reason` 或 "知识库匹配" | None |
| `translate` | `cultural_constraint_applied` | 注入 prompt 的 must_lines / suggest_lines（culture_gap 为 high/medium 的条目） | 对应约束 `reason` | `culture_gap` |
| `risk` | `risk_identified` | `RISK_ANNOTATION_PROMPT` 返回的每条风险 | 风险 `explanation` 字段 | `risk_level` (high/medium/low) |
| `suggestion` | `alternative_suggested` | `SUGGESTION_PROMPT` 返回的每条建议 | 建议 `reason` 字段 | None |

### 3.3 `TranslationResult` 关联

`decision_log_ids`（ARRAY UUID）字段已存在，无需 schema 变更。翻译完成后将决策条目 ID 列表写入此字段，建立反向关联。

### 3.4 迁移

```bash
alembic revision --autogenerate -m "add decision_logs table"
alembic upgrade head
```

## 4. 翻译管线变更

### 4.1 核心思路

`TranslationPipeline.translate()` 各步骤完成后，提取决策数据收集为 `decision_entries` 列表，**通过返回值传出**（不在此方法内持久化，因为 `translate()` 签名不含 `job_id`/`result_id`）。调用方 `tasks.py` 在拿到 `output` 和 `tr.id`（TranslationResult 已先创建）后，调用 `save_decision_logs()` 批量写入，并将返回的 ID 列表填入 `tr.decision_log_ids`。

这样保持 `translate()` 签名不变，持久化职责留在编排层（tasks.py 拥有 job_id/result_id 上下文）。

### 4.2 管线伪代码

```python
# backend/app/services/translation.py — translate() 内部收集决策
async def translate(...) -> dict:
    decision_entries: list[dict] = []  # 新增：收集决策条目

    # Step 1: 文化预处理
    if cultural_sphere:
        cultural_result = await cultural_preprocess(...)
        if cultural_result:
            for term in cultural_result.culture_loaded_terms:
                decision_entries.append({
                    "stage": "preprocess",
                    "decision_type": "culture_term_adaptation",
                    "source_phrase": term.term,
                    "target_phrase": term.suggested_rendering,
                    "decision": f"采用 {term.adaptation_strategy} 策略翻译「{term.term}」",
                    "reasoning": term.reason,
                    "confidence": term.culture_gap,
                    "metadata": {"adaptation_strategy": term.adaptation_strategy},
                })

    # Step 2: RAG 术语检索
    if db and user_id:
        rag_terms = await retrieve_glossary_terms(...)
        for t in rag_terms:
            decision_entries.append({
                "stage": "glossary",
                "decision_type": "term_retrieved",
                "source_phrase": t.source_term,
                "target_phrase": t.target_term,
                "decision": f"从知识库检索到术语「{t.source_term}」",
                "reasoning": t.reason or "知识库匹配",
                "metadata": {"glossary_id": str(t.glossary_id)},
            })

    # Step 3: 主翻译（注入约束时记录，与 cultural_constraints 对应）
    # 仅记录 culture_gap 为 high/medium 的条目（low 不生成约束）
    if cultural_constraints:
        for term in cultural_constraints.culture_loaded_terms:
            if term.culture_gap in ("high", "medium"):
                decision_entries.append({
                    "stage": "translate",
                    "decision_type": "cultural_constraint_applied",
                    "source_phrase": term.term,
                    "target_phrase": term.suggested_rendering,
                    "decision": f"翻译时必须遵守：「{term.term}」→ {term.suggested_rendering}",
                    "reasoning": term.reason,
                    "confidence": term.culture_gap,
                })

    # Step 4: 风险标注
    risk_annotations = await risk_annotation(...)
    for risk in risk_annotations:
        decision_entries.append({
            "stage": "risk",
            "decision_type": "risk_identified",
            "target_phrase": risk["phrase"],
            "decision": f"标记为 {risk['risk_level']} 风险：{risk['risk_type']}",
            "reasoning": risk["explanation"],
            "confidence": risk["risk_level"],
            "metadata": {"risk_level": risk["risk_level"], "risk_type": risk["risk_type"]},
        })

    # Step 5: 替换建议（通过 suggestion API 单独触发，异步写入 decision_logs）

    # 不在此处持久化，通过返回值传出
    return {
        "translated_text": translated_text,
        "risk_annotations": risk_annotations,
        "cultural_adaptation": cultural_adaptation,
        "acceptance_score": acceptance_score,
        "decision_entries": decision_entries,  # 新增返回字段
    }
```

```python
# backend/app/tasks.py — 调用方保存决策日志
output = await pipeline.translate(
    source_text=job.source_text,
    genre=job.genre,
    strategy=job.strategy,
    target_language=lang,
    cultural_sphere=job.cultural_sphere,
    audience_type=job.audience_type,
    cultural_constraints=cultural_constraints,
    db=db,
    user_id=job.user_id,
)
tr.translated_text = output["translated_text"]
tr.risk_annotations = output["risk_annotations"]
tr.cultural_adaptation = output["cultural_adaptation"]
tr.acceptance_score = output["acceptance_score"]
tr.status = "completed"

# 新增：保存决策日志
if output.get("decision_entries"):
    log_ids = await save_decision_logs(db, job_id=job.id, result_id=tr.id, entries=output["decision_entries"])
    tr.decision_log_ids = log_ids

await db.commit()
```

### 4.3 服务层新增

```python
# backend/app/services/decision_log.py

async def save_decision_logs(
    db: AsyncSession,
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    entries: list[dict],
) -> list[uuid.UUID]:
    """批量创建 DecisionLog 记录，返回 ID 列表。"""
    ...

async def get_decision_logs_by_result(
    db: AsyncSession,
    result_id: uuid.UUID,
) -> list[DecisionLog]:
    """按 result_id 查询所有决策日志，按 stage 和 created_at 排序。"""
    ...

async def get_decision_logs_by_job(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> list[DecisionLog]:
    """按 job_id 查询所有语言的决策日志。"""
    ...
```

### 4.4 替换建议的特殊处理

替换建议（`suggestion` 阶段）由用户在审阅译文时主动触发（点击风险标注的"查看建议"），不在主翻译流程同步执行。建议生成后通过 `save_decision_logs()` 异步写入，追加到对应 `TranslationResult.decision_log_ids`。

## 5. API 设计

### 5.1 新增端点

```python
# backend/app/api/decisions.py

@router.get("/jobs/{job_id}/decisions", response_model=list[DecisionLogResponse])
async def list_job_decisions(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某个翻译任务的所有决策日志（全部语言），按 stage 分组、created_at 排序。"""
    ...

@router.get("/results/{result_id}/decisions", response_model=list[DecisionLogResponse])
async def list_result_decisions(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某个语言译文结果的所有决策日志（按语言查看）。"""
    ...
```

### 5.2 响应 Schema

```python
# backend/app/schemas/decision_log.py

import uuid
from datetime import datetime
from pydantic import BaseModel


class DecisionLogResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    result_id: uuid.UUID
    stage: str  # preprocess / glossary / translate / risk / suggestion
    decision_type: str
    source_phrase: str | None
    target_phrase: str | None
    decision: str
    reasoning: str
    confidence: str | None  # high / medium / low / None
    metadata: dict | None
    created_at: datetime
```

### 5.3 路由注册

```python
# backend/app/main.py
from app.api import decisions
app.include_router(decisions.router, prefix="/api", tags=["decisions"])
```

## 6. 前端 UI 设计

### 6.1 展示位置

在工作台译文区右侧增加「决策日志」折叠面板，与现有风险标注 Popover 互补：
- 风险标注 = 译文中内联高亮（局部视角）
- 决策日志 = 侧边完整决策链路（全局视角）

### 6.2 组件结构

```
frontend/components/workspace/
├── DecisionLogPanel.tsx          # 主面板（可折叠）
├── DecisionLogEntry.tsx          # 单条决策条目
├── DecisionStageGroup.tsx        # 按阶段分组容器
└── DecisionLogSkeleton.tsx       # 加载骨架
```

### 6.3 面板布局

```
┌─ 译文区 ─────────────────┐ ┌─ 决策日志 ───────────┐
│                          │ │ [收起 ▶]              │
│  译文内容 + <mark> 高亮   │ │                      │
│                          │ │ ▸ 文化预处理 (3)      │
│                          │ │   • 「一带一路」采用   │
│                          │ │     类比策略 → BRI    │
│                          │ │     原因: 目标文化有   │
│                          │ │     相近概念...        │
│                          │ │                      │
│                          │ │ ▸ 术语检索 (2)        │
│                          │ │ ▸ 翻译约束 (2)        │
│                          │ │ ▸ 风险标注 (1)        │
│                          │ │   ⚠ high 风险          │
│                          │ │     cognitive_bias    │
│                          │ │ ▸ 替换建议 (2)        │
└──────────────────────────┘ └──────────────────────┘
```

### 6.4 视觉规范（遵循现有品牌色系：青绿 + 赤陶）

| 元素 | 样式 |
|---|---|
| 阶段标题 | 加粗 + 折叠箭头 + 计数徽章 |
| confidence=high | 赤陶色（#C8553D）左边框 |
| confidence=medium | 琥珀色左边框 |
| confidence=low | 灰色左边框 |
| reasoning 文本 | 次要色（text-muted-foreground）+ 小字号 |
| source_phrase / target_phrase | 青绿色（品牌色）inline code 样式 |

### 6.5 数据流

```
translationStore.currentResultId 变化
  → useEffect 触发 apiClient.getResultDecisions(resultId)
  → 存入 translationStore.decisionLogs
  → DecisionLogPanel 渲染
```

### 6.6 Zustand Store 扩展

```typescript
// frontend/stores/translation-store.ts
interface TranslationState {
  // ...现有字段
  decisionLogs: DecisionLogEntry[]  // 新增
  isLoadingDecisions: boolean       // 新增
  loadDecisionLogs: (resultId: string) => Promise<void>  // 新增
}
```

### 6.7 API Client 扩展

```typescript
// frontend/lib/api-client.ts
async getResultDecisions(resultId: string): Promise<DecisionLogEntry[]>
async getJobDecisions(jobId: string): Promise<DecisionLogEntry[]>
```

### 6.8 交互细节

1. **默认折叠**：面板默认收起，点击展开
2. **阶段折叠**：每个阶段可独立折叠/展开
3. **与风险标注联动**：点击风险标注 `<mark>` 时，自动展开决策日志并滚动到对应风险条目（通过 `decision_type=risk_identified` + `target_phrase` 匹配）
4. **空状态**：无决策日志时显示"本次翻译无关键决策记录"

## 7. 测试与错误处理

### 7.1 后端测试

```python
# backend/tests/test_decision_log.py

class TestDecisionLogExtraction:
    """测试各阶段决策提取逻辑"""

    def test_extract_preprocess_decisions()
        # 文化预处理返回 3 个文化负载词 → 生成 3 条 preprocess 决策

    def test_extract_glossary_decisions()
        # RAG 检索命中 2 个术语 → 生成 2 条 glossary 决策

    def test_extract_risk_decisions()
        # 风险标注返回 2 条风险 → 生成 2 条 risk 决策

    def test_no_cultural_sphere_skips_preprocess_stage()
        # 未选文化圈 → preprocess/glossary/translate 阶段无条目

    def test_empty_pipeline_produces_no_decisions()
        # 空原文 + 无风险 → decision_log_ids 为空列表
```

```python
# backend/tests/test_api_decisions.py

class TestDecisionsAPI:
    def test_list_job_decisions_returns_all_stages()
    def test_list_result_decisions_filtered_by_result()
    def test_decisions_ordered_by_stage_then_created_at()
    def test_unauthorized_returns_401()
    def test_other_users_job_returns_404()  # 权限隔离
```

### 7.2 前端测试

```typescript
// frontend/components/workspace/__tests__/DecisionLogPanel.test.tsx
- 渲染空状态
- 按阶段分组渲染
- 折叠/展开交互
- loading 骨架
- 与风险标注联动滚动
```

### 7.3 错误处理

| 场景 | 处理 |
|---|---|
| 某阶段 LLM 调用失败 | 该阶段不生成决策条目，不影响其他阶段和主翻译流程 |
| `save_decision_logs` 写入失败 | 记录 warning 日志，不中断翻译流程（决策日志是附属数据） |
| `GET /decisions` 查询无数据 | 返回空数组 `[]`，不报错 |
| `result_id` 不存在 | 返回 404 |
| 跨用户访问 | 返回 404（权限隔离，与现有 jobs API 一致） |

### 7.4 关键原则

**决策日志是"尽力而为"的附属数据**：任何环节失败都不应阻断主翻译流程。翻译结果优先保证完整，决策日志作为增强信息，缺失时 UI 显示空状态即可。

## 8. 实施顺序概览

1. 后端：`DecisionLog` 模型 + Alembic 迁移
2. 后端：`decision_log` service（save/get）
3. 后端：`TranslationPipeline.translate()` 注入决策提取逻辑
4. 后端：`decisions` API router + schema
5. 后端：测试
6. 前端：API Client 方法 + TypeScript 类型
7. 前端：Zustand store 扩展
8. 前端：`DecisionLogPanel` 及子组件
9. 前端：集成到工作台 + 风险标注联动
10. 前端：测试
