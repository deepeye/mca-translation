# 文化语境适配 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有翻译流程中引入"文化语境"维度（8 个文化圈 + 6 个受众类型），新增 LLM 预处理步骤识别文化负载词并注入主翻译 prompt，同时保持向后兼容。

**Architecture:** 后端新增 `cultural_sphere` / `audience_type` 字段；新增 `app/services/cultural.py` 预处理服务和 `CULTURAL_SPHERE_PROFILES`/`AUDIENCE_TYPE_GUIDELINES` 常量表；翻译流程从 2 步扩展为 3 步（预处理 → 主翻译（带文化约束）→ 风险标注）；前端新增 `culture-sphere-selector` 和 `audience-type-selector` 组件，结果面板新增"文化适配"折叠区域。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · Celery · Next.js · React · Zustand · Tailwind · pytest（新引入）

**参考 Spec：** `docs/superpowers/specs/2026-06-16-cultural-context-design.md`

---

## 文件结构

### 新建文件

| 路径 | 职责 |
|------|------|
| `backend/app/services/cultural.py` | 文化预处理服务：构建 prompt、调用 LLM、解析 JSON、降级处理 |
| `backend/app/llm/cultural_profiles.py` | 文化圈特征字典（CULTURAL_SPHERE_PROFILES）和受众类型指引（AUDIENCE_TYPE_GUIDELINES） |
| `backend/alembic/versions/<rev>_add_cultural_context_fields.py` | DB 迁移：新增 `cultural_sphere` 和 `audience_type` 列 |
| `backend/tests/__init__.py` | pytest 包目录 |
| `backend/tests/conftest.py` | pytest 配置（设置 sys.path） |
| `backend/tests/test_cultural_service.py` | 文化预处理服务单元测试 |
| `backend/tests/test_cultural_prompt_injection.py` | 主翻译 prompt 文化约束注入单元测试 |
| `backend/pyproject.toml` | 引入 pytest + pytest-asyncio 配置 |
| `frontend/components/workspace/culture-sphere-selector.tsx` | 文化圈选择器组件 |
| `frontend/components/workspace/audience-type-selector.tsx` | 受众类型选择器组件 |
| `frontend/components/workspace/cultural-adaptation-panel.tsx` | 翻译结果中"文化适配"折叠区域组件 |

### 修改文件

| 路径 | 改动 |
|------|------|
| `backend/app/models/job.py` | TranslationJob 新增 `cultural_sphere` / `audience_type` 列 |
| `backend/app/schemas/job.py` | CreateJobRequest 与 TranslationResultResponse 扩展，新增 CulturalLoadedTerm / CulturalPreprocessResult schema |
| `backend/app/llm/prompts.py` | 新增 `CULTURAL_PREPROCESS_PROMPT`；扩展 `TRANSLATION_SYSTEM_PROMPT` 支持可选 `<cultural_constraints>` 段 |
| `backend/app/services/translation.py` | `pipeline.translate` 接入预处理步骤；prompt 构建拆为独立函数 |
| `backend/app/api/jobs.py` | `create_job` 写入新字段；`_build_job_response` 透出 `cultural_adaptation` |
| `backend/app/tasks.py` | Celery worker 调用 pipeline 时传入新参数；落库 `cultural_adaptation` |
| `frontend/stores/workspace-store.ts` | 类型与 store action 扩展 |
| `frontend/stores/translation-store.ts` | LangResult 新增 `culturalAdaptation` 字段 |
| `frontend/components/workspace/input-panel.tsx` | 嵌入两个新选择器；调用 `/api/jobs` 时传入新字段；轮询时把 `cultural_adaptation` 写回 store |
| `frontend/components/workspace/translation-result.tsx` | 顶部插入 `CulturalAdaptationPanel` |

### 不需要修改的文件

- `frontend/components/workspace/genre-selector.tsx`、`strategy-selector.tsx`：保持原样
- `backend/app/services/suggestion.py`：风险标注/建议链路不变

---

## Task 1：新增 pytest 测试脚手架

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Modify: `backend/requirements.txt`

后端目前没有测试基础设施。后续多个任务采用 TDD，必须先准备好 pytest 环境。

- [ ] **Step 1: 在 requirements.txt 末尾追加 pytest 依赖**

修改 `backend/requirements.txt`，在文件末尾追加两行：

```
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: 写 backend/pyproject.toml**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: 写 backend/tests/__init__.py（空文件即可）**

```python
```

- [ ] **Step 4: 写 backend/tests/conftest.py**

```python
"""pytest 共享配置。

把 backend/ 加入 sys.path，让 tests/ 可以 import app.*。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

- [ ] **Step 5: 安装新依赖**

```bash
cd backend && source .venv/bin/activate && pip install -r requirements.txt
```

- [ ] **Step 6: 运行 pytest 确认环境就绪（应输出 "no tests ran"）**

```bash
cd backend && source .venv/bin/activate && pytest
```

预期：退出码 5（no tests collected），不是 import 错误。

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/pyproject.toml backend/tests/__init__.py backend/tests/conftest.py
git commit -m "test: add pytest scaffolding for backend"
```

---

## Task 2：新增文化圈特征 / 受众类型指引常量表

**Files:**
- Create: `backend/app/llm/cultural_profiles.py`
- Test: `backend/tests/test_cultural_profiles.py`

定义 8 个文化圈和 6 个受众类型的硬编码描述。后续预处理 prompt 和主翻译 prompt 都会引用这个表。

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_cultural_profiles.py`：

```python
"""验证文化圈和受众类型常量表的完整性。"""
from app.llm.cultural_profiles import (
    AUDIENCE_TYPE_GUIDELINES,
    CULTURAL_SPHERE_PROFILES,
    SUPPORTED_AUDIENCE_TYPES,
    SUPPORTED_CULTURAL_SPHERES,
)


def test_cultural_sphere_profiles_cover_all_keys():
    expected = {
        "western_english",
        "european_continental",
        "islamic_middle_east",
        "east_asian_confucian",
        "latin_american",
        "russian_sphere",
        "south_asian",
        "african",
    }
    assert set(CULTURAL_SPHERE_PROFILES.keys()) == expected
    assert set(SUPPORTED_CULTURAL_SPHERES) == expected
    for key, value in CULTURAL_SPHERE_PROFILES.items():
        assert isinstance(value, str) and len(value.strip()) >= 30, key


def test_audience_type_guidelines_cover_all_keys():
    expected = {
        "general_public",
        "media",
        "government",
        "academic",
        "business",
        "diaspora_chinese",
    }
    assert set(AUDIENCE_TYPE_GUIDELINES.keys()) == expected
    assert set(SUPPORTED_AUDIENCE_TYPES) == expected
    for key, value in AUDIENCE_TYPE_GUIDELINES.items():
        assert isinstance(value, str) and len(value.strip()) >= 20, key
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && pytest tests/test_cultural_profiles.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.llm.cultural_profiles'`。

- [ ] **Step 3: 实现 cultural_profiles.py**

`backend/app/llm/cultural_profiles.py`：

```python
"""文化圈特征 / 受众类型指引常量表。

由 cultural.py 预处理服务和 prompts.py 主翻译模板共同引用。
更新这里时请同步检查 docs/superpowers/specs/2026-06-16-cultural-context-design.md。
"""

CULTURAL_SPHERE_PROFILES: dict[str, str] = {
    "western_english": (
        "欧美英语圈（美国、英国、加拿大、澳大利亚）：受众秉持个人主义价值观与自由市场语境，"
        "对'国家主导/政府主导'类叙事天然警惕；偏好以数据、案例、个人故事为载体的论证；"
        "倾向直接、简洁、可质疑的表达。"
    ),
    "european_continental": (
        "欧洲大陆（德国、法国、意大利、北欧）：社会民主传统深厚，重视制度对比与公共政策讨论；"
        "对环保、社会公平、人权议题敏感；偏好严谨论证与深度分析；倾向多角度对照式叙事。"
    ),
    "islamic_middle_east": (
        "伊斯兰中东（沙特、阿联酋、伊朗、埃及）：宗教与传统价值观敏感，受众尊重权威与家庭、"
        "集体的关系优先于个人；避免任何与宗教对立、世俗主义冲突的隐喻或比喻；"
        "倾向尊重、和谐、稳定取向的叙事。"
    ),
    "east_asian_confucian": (
        "东亚儒家（日本、韩国）：高语境文化，等级与礼节意识较强；重视集体和谐与含蓄表达；"
        "对'发展、合作、共赢'类叙事接受度高；避免过于直接的冲突表述。"
    ),
    "latin_american": (
        "拉美（巴西、墨西哥、阿根廷）：关系驱动、情感表达活跃；关心发展议题、南南合作、"
        "去殖民化叙事；偏好故事化、情感化的表达；接受较高的语言张力。"
    ),
    "russian_sphere": (
        "俄语圈（俄罗斯、中亚）：国家叙事传统深厚，地缘政治意识强；对历史议题、安全议题敏感；"
        "偏好厚重、宏大叙事；对西方话语体系常持审视态度。"
    ),
    "south_asian": (
        "南亚（印度、巴基斯坦、孟加拉）：多元宗教并存，发展中大国身份认同强；英语普及率高，"
        "关注发展合作、基础设施、数字经济议题；偏好正式但故事化的表达。"
    ),
    "african": (
        "非洲（南非、尼日利亚、肯尼亚）：发展合作叙事接受度高，年轻人口比重大，"
        "关心基础设施、教育、卫生、农业议题；偏好务实、案例驱动的表达；南南合作语境亲切。"
    ),
}

AUDIENCE_TYPE_GUIDELINES: dict[str, str] = {
    "general_public": "公众读者：使用简明语言，避免专业术语，多用日常类比和具体故事。",
    "media": "媒体记者/编辑：采用客观可引用的 Reuters 风格，5W1H 结构清晰，措辞中立。",
    "government": "政府/外交人员：使用正式精准的政策语言，避免歧义，措辞规范。",
    "academic": "学者/智库：保留概念完整性，论证严密，引用规范，可使用专业术语。",
    "business": "商界人士：以数据、ROI、商业影响为框架，表达务实、聚焦商业价值。",
    "diaspora_chinese": "海外华人：可保留部分中文概念（用拼音或音译），结合所在地语境与文化共鸣。",
}

SUPPORTED_CULTURAL_SPHERES: tuple[str, ...] = tuple(CULTURAL_SPHERE_PROFILES.keys())
SUPPORTED_AUDIENCE_TYPES: tuple[str, ...] = tuple(AUDIENCE_TYPE_GUIDELINES.keys())
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && pytest tests/test_cultural_profiles.py -v
```

预期：2 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/cultural_profiles.py backend/tests/test_cultural_profiles.py
git commit -m "feat(backend): add cultural sphere and audience type profile tables"
```

---

## Task 3：扩展 Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/job.py`
- Test: `backend/tests/test_cultural_schemas.py`

新增 `CulturalLoadedTerm` 和 `CulturalPreprocessResult`，扩展 `CreateJobRequest` 和 `TranslationResultResponse`。

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_cultural_schemas.py`：

```python
"""验证 cultural 相关 schema 的字段和默认值。"""
import pytest
from pydantic import ValidationError

from app.schemas.job import (
    CreateJobRequest,
    CulturalLoadedTerm,
    CulturalPreprocessResult,
    TranslationResultResponse,
)


def test_cultural_loaded_term_accepts_valid_payload():
    term = CulturalLoadedTerm(
        term="共同富裕",
        culture_gap="high",
        adaptation_strategy="explanatory",
        suggested_rendering="a policy initiative aimed at balanced wealth distribution",
        reason="lacks context for Western audiences",
    )
    assert term.adaptation_strategy == "explanatory"


def test_cultural_loaded_term_rejects_unknown_strategy():
    with pytest.raises(ValidationError):
        CulturalLoadedTerm(
            term="x",
            culture_gap="low",
            adaptation_strategy="invented",
            suggested_rendering="x",
            reason="x",
        )


def test_cultural_preprocess_result_defaults_to_empty_lists():
    result = CulturalPreprocessResult()
    assert result.culture_loaded_terms == []
    assert result.cultural_notes == []
    assert result.taboo_warnings == []


def test_create_job_request_cultural_fields_optional():
    req = CreateJobRequest(
        source_text="hello",
        genre="political",
        target_languages=["en-GB"],
    )
    assert req.cultural_sphere is None
    assert req.audience_type is None


def test_create_job_request_accepts_cultural_fields():
    req = CreateJobRequest(
        source_text="hello",
        genre="political",
        target_languages=["en-GB"],
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert req.cultural_sphere == "western_english"
    assert req.audience_type == "general_public"


def test_translation_result_response_cultural_adaptation_optional():
    import uuid
    from datetime import datetime, timezone

    resp = TranslationResultResponse(
        id=uuid.uuid4(),
        language="en-GB",
        status="completed",
        translated_text="x",
        acceptance_score=-1,
        risk_annotations=None,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.cultural_adaptation is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && pytest tests/test_cultural_schemas.py -v
```

预期：FAIL，`ImportError: cannot import name 'CulturalLoadedTerm'`。

- [ ] **Step 3: 修改 backend/app/schemas/job.py**

在文件顶部 imports 调整为（保留现有 + 新增 Literal/Optional）：

```python
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
```

在 `CreateJobRequest` 之前新增：

```python
class CulturalLoadedTerm(BaseModel):
    term: str
    culture_gap: Literal["low", "medium", "high"]
    adaptation_strategy: Literal["literal", "explanatory", "analogical", "reconstruction"]
    suggested_rendering: str
    reason: str


class CulturalPreprocessResult(BaseModel):
    culture_loaded_terms: list[CulturalLoadedTerm] = Field(default_factory=list)
    cultural_notes: list[str] = Field(default_factory=list)
    taboo_warnings: list[str] = Field(default_factory=list)
```

把 `CreateJobRequest` 改为：

```python
class CreateJobRequest(BaseModel):
    source_text: str
    genre: str  # political | news | policy | brand
    strategy: str = "semantic_equivalence"
    target_languages: list[str]  # BCP-47 codes
    cultural_sphere: Optional[str] = None
    audience_type: Optional[str] = None
```

把 `TranslationResultResponse` 改为：

```python
class TranslationResultResponse(BaseModel):
    id: uuid.UUID
    language: str
    status: str
    translated_text: str | None
    acceptance_score: int
    risk_annotations: list | None
    cultural_adaptation: Optional[CulturalPreprocessResult] = None
    created_at: datetime
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && pytest tests/test_cultural_schemas.py -v
```

预期：6 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/job.py backend/tests/test_cultural_schemas.py
git commit -m "feat(backend): add cultural context fields to schemas"
```

---

## Task 4：扩展 SQLAlchemy 模型 + Alembic 迁移

**Files:**
- Modify: `backend/app/models/job.py`
- Create: `backend/alembic/versions/<rev>_add_cultural_context_fields.py`

为 `translation_jobs` 表新增 `cultural_sphere` / `audience_type`。`translation_results` 不存 `cultural_adaptation`（每次返回时计算并随 job 透出，不入库；如需后续持久化可独立任务）。

> ⚠️ 简化决定：本计划范围内 `cultural_adaptation` 仅放在 `translation_results.risk_annotations` 同位置，作为另一个 JSONB 列存。这是为了让前端轮询能读到。新增列 `cultural_adaptation`（JSONB, nullable）。

- [ ] **Step 1: 修改 backend/app/models/job.py**

`TranslationJob` 类追加两列（在 `glossary_ids` 后、`created_at` 前）：

```python
    cultural_sphere: Mapped[str | None] = mapped_column(String(32), nullable=True)
    audience_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

`TranslationResult` 类追加一列（在 `decision_log_ids` 后、`created_at` 前）：

```python
    cultural_adaptation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: 生成 Alembic 迁移**

```bash
cd backend && source .venv/bin/activate && alembic revision -m "add cultural context fields"
```

记下生成的文件名（形如 `backend/alembic/versions/<revision>_add_cultural_context_fields.py`）。

- [ ] **Step 3: 把迁移文件 upgrade/downgrade 改为以下内容**

```python
def upgrade() -> None:
    op.add_column(
        'translation_jobs',
        sa.Column('cultural_sphere', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'translation_jobs',
        sa.Column('audience_type', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'translation_results',
        sa.Column('cultural_adaptation', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('translation_results', 'cultural_adaptation')
    op.drop_column('translation_jobs', 'audience_type')
    op.drop_column('translation_jobs', 'cultural_sphere')
```

确保文件顶部已有 `from sqlalchemy.dialects import postgresql` 这一行（Alembic 模板默认带）。

- [ ] **Step 4: 运行迁移**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

预期：输出 `Running upgrade ad7cfe796694 -> <new_rev>, add cultural context fields`，无错误。

- [ ] **Step 5: 验证表结构**

```bash
cd backend && source .venv/bin/activate && python -c "
import asyncio
from sqlalchemy import text
from app.core.database import engine

async def check():
    async with engine.connect() as conn:
        rows = await conn.execute(text(
            \"SELECT column_name FROM information_schema.columns \"
            \"WHERE table_name='translation_jobs' AND column_name IN ('cultural_sphere','audience_type')\"
        ))
        print(sorted(r[0] for r in rows))
        rows = await conn.execute(text(
            \"SELECT column_name FROM information_schema.columns \"
            \"WHERE table_name='translation_results' AND column_name='cultural_adaptation'\"
        ))
        print(sorted(r[0] for r in rows))

asyncio.run(check())
"
```

预期输出：
```
['audience_type', 'cultural_sphere']
['cultural_adaptation']
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/job.py backend/alembic/versions/*_add_cultural_context_fields.py
git commit -m "feat(backend): add cultural context columns to db"
```

---

## Task 5：新增 CULTURAL_PREPROCESS_PROMPT 模板

**Files:**
- Modify: `backend/app/llm/prompts.py`
- Test: `backend/tests/test_cultural_preprocess_prompt.py`

新增预处理 prompt 模板，注入文化圈描述、受众指引、文体，并约束 LLM 输出严格 JSON。

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_cultural_preprocess_prompt.py`：

```python
"""验证 CULTURAL_PREPROCESS_PROMPT 注入文化圈/受众/文体后的结果。"""
from app.llm.cultural_profiles import (
    AUDIENCE_TYPE_GUIDELINES,
    CULTURAL_SPHERE_PROFILES,
)
from app.llm.prompts import CULTURAL_PREPROCESS_PROMPT


def test_prompt_contains_required_placeholders():
    for placeholder in (
        "{source_text}",
        "{cultural_sphere_profile}",
        "{audience_type_guideline}",
        "{genre}",
    ):
        assert placeholder in CULTURAL_PREPROCESS_PROMPT, placeholder


def test_prompt_renders_with_known_values():
    rendered = CULTURAL_PREPROCESS_PROMPT.format(
        source_text="共同富裕不是平均主义。",
        cultural_sphere_profile=CULTURAL_SPHERE_PROFILES["western_english"],
        audience_type_guideline=AUDIENCE_TYPE_GUIDELINES["general_public"],
        genre="political",
    )
    assert "共同富裕不是平均主义。" in rendered
    assert "欧美英语圈" in rendered
    assert "公众读者" in rendered
    assert "political" in rendered
    # JSON 输出说明
    assert "culture_loaded_terms" in rendered
    assert "cultural_notes" in rendered
    assert "taboo_warnings" in rendered
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && pytest tests/test_cultural_preprocess_prompt.py -v
```

预期：FAIL，`ImportError: cannot import name 'CULTURAL_PREPROCESS_PROMPT'`。

- [ ] **Step 3: 修改 backend/app/llm/prompts.py，在文件末尾追加**

```python
CULTURAL_PREPROCESS_PROMPT = """你是一位资深的国际传播专家，擅长跨文化内容适配。请阅读下面的中文源文本，并基于目标文化圈与受众类型，识别文本中可能造成跨文化障碍的"文化负载词"。

目标文化圈特征：
{cultural_sphere_profile}

目标受众类型：
{audience_type_guideline}

文体：{genre}

任务要求：
1. 识别源文本中的文化负载词或短语（最多 10 个）。"文化负载词"指那些在目标文化圈中缺少直接对应概念、容易引起误解、或需要额外背景才能理解的中文表达。
2. 对每个识别出的词，给出以下字段：
   - term：原文中的中文词或短语，必须与原文片段完全一致
   - culture_gap："low" | "medium" | "high"，表示与目标文化圈的认知差异程度
   - adaptation_strategy："literal"（直译，文化距离低）| "explanatory"（解释型翻译，需补充背景）| "analogical"（类比翻译，目标文化有相近概念）| "reconstruction"（场景重构，需要重新组织表达）
   - suggested_rendering：建议的目标语译法或译文片段
   - reason：用简体中文一句话说明为什么需要这种适配
3. 给出 cultural_notes：1-3 条目标文化圈下的整体表达注意事项（中文）
4. 给出 taboo_warnings：0-3 条目标文化圈下应避免的表达或叙事框架（中文），无则返回空数组

输出严格 JSON，不要包含任何其他文字、解释、markdown 代码围栏：

{{
  "culture_loaded_terms": [
    {{
      "term": "...",
      "culture_gap": "low|medium|high",
      "adaptation_strategy": "literal|explanatory|analogical|reconstruction",
      "suggested_rendering": "...",
      "reason": "..."
    }}
  ],
  "cultural_notes": ["..."],
  "taboo_warnings": ["..."]
}}

源文本：
{source_text}
"""
```

注意 `{{` / `}}` 用于在 `.format()` 时输出字面量花括号。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && pytest tests/test_cultural_preprocess_prompt.py -v
```

预期：2 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/prompts.py backend/tests/test_cultural_preprocess_prompt.py
git commit -m "feat(backend): add cultural preprocess prompt template"
```

---

## Task 6：实现 cultural.py 预处理服务

**Files:**
- Create: `backend/app/services/cultural.py`
- Test: `backend/tests/test_cultural_service.py`

提供 `cultural_preprocess(...)` 函数：构建 prompt → 调用 LLM → 解析 JSON → 验证字段 → 失败则降级返回 None。

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_cultural_service.py`：

```python
"""文化预处理服务的单元测试。

LLM 客户端通过参数注入，便于伪造响应。
"""
from typing import Any

import pytest

from app.schemas.job import CulturalPreprocessResult
from app.services.cultural import cultural_preprocess


class FakeClient:
    """伪造的 bailian client。chat() 返回预设的字符串作为 LLM 内容。"""

    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict[str, Any]] = []

    async def chat(self, *, model: str, messages: list, temperature: float = 0.1) -> dict:
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        return {"content": self._content}


@pytest.mark.asyncio
async def test_returns_parsed_result_on_valid_json():
    payload = """{
      "culture_loaded_terms": [
        {
          "term": "共同富裕",
          "culture_gap": "high",
          "adaptation_strategy": "explanatory",
          "suggested_rendering": "a policy initiative for balanced wealth distribution",
          "reason": "西方受众缺少政策语境"
        }
      ],
      "cultural_notes": ["避免国家主导叙事"],
      "taboo_warnings": []
    }"""
    client = FakeClient(payload)
    result = await cultural_preprocess(
        text="共同富裕不是平均主义。",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert isinstance(result, CulturalPreprocessResult)
    assert len(result.culture_loaded_terms) == 1
    assert result.culture_loaded_terms[0].term == "共同富裕"
    assert result.cultural_notes == ["避免国家主导叙事"]
    assert result.taboo_warnings == []


@pytest.mark.asyncio
async def test_strips_markdown_code_fences():
    payload = "```json\n" + '{"culture_loaded_terms": [], "cultural_notes": [], "taboo_warnings": []}' + "\n```"
    client = FakeClient(payload)
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert result is not None
    assert result.culture_loaded_terms == []


@pytest.mark.asyncio
async def test_returns_none_on_invalid_json():
    client = FakeClient("not a json")
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_unknown_cultural_sphere():
    client = FakeClient('{"culture_loaded_terms": [], "cultural_notes": [], "taboo_warnings": []}')
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="atlantis",  # 不在白名单
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_llm_exception():
    class FailingClient:
        async def chat(self, **_):
            raise RuntimeError("upstream timeout")

    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=FailingClient(),
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_unknown_audience_type():
    client = FakeClient('{"culture_loaded_terms": [], "cultural_notes": [], "taboo_warnings": []}')
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="aliens",
        genre="political",
        llm_client=client,
    )
    assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && pytest tests/test_cultural_service.py -v
```

预期：FAIL，`ImportError: cannot import name 'cultural_preprocess'`。

- [ ] **Step 3: 实现 backend/app/services/cultural.py**

```python
"""文化语境预处理服务。

输入源文本+文化圈+受众+文体；调用 LLM 识别文化负载词并产出本土化约束。
任何失败（白名单不命中、LLM 异常、JSON 解析失败、字段验证失败）都返回 None，
让上层管线降级（继续主翻译，不注入文化约束）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Protocol

from pydantic import ValidationError

from app.llm.cultural_profiles import (
    AUDIENCE_TYPE_GUIDELINES,
    CULTURAL_SPHERE_PROFILES,
)
from app.llm.prompts import CULTURAL_PREPROCESS_PROMPT
from app.schemas.job import CulturalPreprocessResult

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    async def chat(self, *, model: str, messages: list, temperature: float = ...) -> dict[str, Any]: ...


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        # 去掉首行（``` 或 ```json）和尾部 ```
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


async def cultural_preprocess(
    *,
    text: str,
    cultural_sphere: str,
    audience_type: str,
    genre: str,
    llm_client: _LLMClient,
    model: str = "qwen-plus",
) -> Optional[CulturalPreprocessResult]:
    """识别源文本中的文化负载词并生成本土化约束。

    任何失败都返回 None，调用方应降级处理（不注入文化约束继续主翻译）。
    """
    if cultural_sphere not in CULTURAL_SPHERE_PROFILES:
        logger.info("cultural_preprocess skipped: unknown cultural_sphere=%s", cultural_sphere)
        return None
    if audience_type not in AUDIENCE_TYPE_GUIDELINES:
        logger.info("cultural_preprocess skipped: unknown audience_type=%s", audience_type)
        return None

    prompt = CULTURAL_PREPROCESS_PROMPT.format(
        source_text=text,
        cultural_sphere_profile=CULTURAL_SPHERE_PROFILES[cultural_sphere],
        audience_type_guideline=AUDIENCE_TYPE_GUIDELINES[audience_type],
        genre=genre,
    )

    try:
        response = await llm_client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
    except Exception as e:
        logger.warning("cultural_preprocess LLM call failed: %s", e)
        return None

    raw = response.get("content", "") if isinstance(response, dict) else ""
    cleaned = _strip_code_fences(raw)
    if not cleaned:
        logger.warning("cultural_preprocess got empty content")
        return None

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("cultural_preprocess JSON parse failed: %s; head=%r", e, cleaned[:200])
        return None

    try:
        return CulturalPreprocessResult(**data)
    except ValidationError as e:
        logger.warning("cultural_preprocess schema validation failed: %s", e)
        return None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && pytest tests/test_cultural_service.py -v
```

预期：6 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cultural.py backend/tests/test_cultural_service.py
git commit -m "feat(backend): add cultural preprocess service with graceful fallback"
```

---

## Task 7：扩展主翻译 prompt 支持 `<cultural_constraints>` 段

**Files:**
- Modify: `backend/app/llm/prompts.py`
- Modify: `backend/app/services/translation.py`
- Test: `backend/tests/test_cultural_prompt_injection.py`

主翻译 prompt 改造：把构建 system prompt 的逻辑抽到独立函数 `build_translation_system_prompt`，可选注入 cultural_constraints。原有 `TRANSLATION_SYSTEM_PROMPT` 模板保留，新增 `<cultural_constraints>` 占位（可为空）。

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_cultural_prompt_injection.py`：

```python
"""验证主翻译 system prompt 在有/无 cultural_constraints 时的差异。"""
from app.schemas.job import (
    CulturalLoadedTerm,
    CulturalPreprocessResult,
)
from app.services.translation import build_translation_system_prompt


def _make_result() -> CulturalPreprocessResult:
    return CulturalPreprocessResult(
        culture_loaded_terms=[
            CulturalLoadedTerm(
                term="共同富裕",
                culture_gap="high",
                adaptation_strategy="explanatory",
                suggested_rendering="a policy initiative for balanced wealth distribution",
                reason="lacks Western context",
            ),
            CulturalLoadedTerm(
                term="新质生产力",
                culture_gap="medium",
                adaptation_strategy="explanatory",
                suggested_rendering="innovation-driven productive forces",
                reason="abstract policy term",
            ),
            CulturalLoadedTerm(
                term="熊猫",
                culture_gap="low",
                adaptation_strategy="literal",
                suggested_rendering="panda",
                reason="universally known",
            ),
        ],
        cultural_notes=["避免国家主导叙事框架"],
        taboo_warnings=["避免宗教治理表述"],
    )


def test_prompt_without_cultural_constraints_omits_section():
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_constraints=None,
        cultural_sphere=None,
        audience_type=None,
    )
    assert "<cultural_constraints>" not in prompt
    assert "en-GB" in prompt
    assert "political" in prompt


def test_prompt_with_cultural_constraints_includes_section():
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_constraints=_make_result(),
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "<cultural_constraints>" in prompt
    assert "</cultural_constraints>" in prompt
    # 高文化差异 -> MUST_USE
    assert "MUST_USE" in prompt and "共同富裕" in prompt
    # 中文化差异 -> SUGGEST
    assert "SUGGEST" in prompt and "新质生产力" in prompt
    # 低文化差异 -> 不生成约束（不出现 LITERAL 这种关键字）
    assert "熊猫" not in prompt or prompt.count("熊猫") == 0
    # 文化注意事项 + 禁忌
    assert "避免国家主导叙事框架" in prompt
    assert "避免宗教治理表述" in prompt
    # 文化圈 / 受众也注入
    assert "欧美英语圈" in prompt
    assert "公众读者" in prompt


def test_prompt_with_empty_constraints_still_includes_section():
    """没有文化负载词，但仍传入 cultural_sphere/audience_type 时仍应注入特征段。"""
    empty = CulturalPreprocessResult()
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_constraints=empty,
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "<cultural_constraints>" in prompt
    assert "欧美英语圈" in prompt
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && pytest tests/test_cultural_prompt_injection.py -v
```

预期：FAIL，`ImportError: cannot import name 'build_translation_system_prompt'`。

- [ ] **Step 3: 修改 backend/app/services/translation.py 顶部 import**

把现有的：
```python
from app.llm.prompts import RISK_ANNOTATION_PROMPT, STRATEGY_DESCRIPTIONS, TRANSLATION_SYSTEM_PROMPT
```
改为：
```python
from app.llm.cultural_profiles import AUDIENCE_TYPE_GUIDELINES, CULTURAL_SPHERE_PROFILES
from app.llm.prompts import RISK_ANNOTATION_PROMPT, STRATEGY_DESCRIPTIONS, TRANSLATION_SYSTEM_PROMPT
from app.schemas.job import CulturalPreprocessResult
```

在 `pipeline = TranslationPipeline()` 之前新增 helper 函数：

```python
def build_translation_system_prompt(
    *,
    target_language: str,
    genre: str,
    strategy: str,
    cultural_constraints: CulturalPreprocessResult | None = None,
    cultural_sphere: str | None = None,
    audience_type: str | None = None,
) -> str:
    """构建主翻译的 system prompt。可选注入 <cultural_constraints> 段。"""
    strategy_desc = STRATEGY_DESCRIPTIONS.get(strategy, STRATEGY_DESCRIPTIONS["semantic_equivalence"])
    base = TRANSLATION_SYSTEM_PROMPT.format(
        target_language=target_language,
        genre=genre,
        strategy_description=strategy_desc,
    )

    if cultural_sphere not in (CULTURAL_SPHERE_PROFILES if cultural_sphere is not None else {}):
        # 没有文化圈 → 不注入文化段，行为与现有完全一致
        return base

    sphere_profile = CULTURAL_SPHERE_PROFILES[cultural_sphere]
    audience_guideline = AUDIENCE_TYPE_GUIDELINES.get(audience_type or "", "")

    must_lines: list[str] = []
    suggest_lines: list[str] = []
    notes: list[str] = []
    taboos: list[str] = []
    if cultural_constraints is not None:
        for t in cultural_constraints.culture_loaded_terms:
            if t.culture_gap == "high":
                must_lines.append(
                    f'- "{t.term}" → MUST_USE {t.adaptation_strategy} 翻译: "{t.suggested_rendering}"\n  原因: {t.reason}'
                )
            elif t.culture_gap == "medium":
                suggest_lines.append(
                    f'- "{t.term}" → SUGGEST {t.adaptation_strategy} 翻译: "{t.suggested_rendering}"\n  原因: {t.reason}'
                )
            # low: 不生成约束
        notes = list(cultural_constraints.cultural_notes)
        taboos = list(cultural_constraints.taboo_warnings)

    parts = ["<cultural_constraints>"]
    parts.append(f"[文化圈特征] {sphere_profile}")
    if audience_guideline:
        parts.append(f"[受众类型] {audience_guideline}")
    if must_lines:
        parts.append("[术语约束 - 必须遵守]")
        parts.extend(must_lines)
    if suggest_lines:
        parts.append("[术语约束 - 建议遵守]")
        parts.extend(suggest_lines)
    if notes:
        parts.append("[文化注意事项]")
        parts.extend(f"- {n}" for n in notes)
    if taboos:
        parts.append("[禁忌提醒]")
        parts.extend(f"- {t}" for t in taboos)
    parts.append("</cultural_constraints>")

    cultural_block = "\n".join(parts)
    return f"{base}\n\n{cultural_block}\n"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && pytest tests/test_cultural_prompt_injection.py -v
```

预期：3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/translation.py backend/tests/test_cultural_prompt_injection.py
git commit -m "feat(backend): inject cultural constraints into main translation prompt"
```

---

## Task 8：把 cultural_preprocess 接入 TranslationPipeline

**Files:**
- Modify: `backend/app/services/translation.py`

把流程从 2 步扩展为 3 步：预处理 → 主翻译（带约束）→ 风险标注。预处理失败不阻断主流程。

- [ ] **Step 1: 修改 backend/app/services/translation.py 顶部 import 增加**

```python
from app.services.cultural import cultural_preprocess
```

- [ ] **Step 2: 把 TranslationPipeline 的 translate 方法替换为以下实现**

完整替换原 `translate` 和 `_main_translation` 方法（保留 `_risk_annotation`、`translate_stream` 不动）：

```python
    async def translate(
        self,
        source_text: str,
        genre: str,
        strategy: str,
        target_language: str,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
    ) -> dict:
        """Run the pipeline. Returns {translated_text, risk_annotations, cultural_adaptation, acceptance_score}."""
        # Step 1: cultural preprocessing (optional, graceful fallback to None)
        cultural_result = None
        if cultural_sphere:
            cultural_result = await cultural_preprocess(
                text=source_text,
                cultural_sphere=cultural_sphere,
                audience_type=audience_type or "general_public",
                genre=genre,
                llm_client=bailian_client,
            )

        # Step 2: main translation
        translated_text = await self._main_translation(
            source_text=source_text,
            genre=genre,
            strategy=strategy,
            target_language=target_language,
            cultural_constraints=cultural_result,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )

        # Step 3: risk annotation (unchanged)
        risk_annotations = await self._risk_annotation(source_text, translated_text, target_language)

        return {
            "translated_text": translated_text,
            "risk_annotations": risk_annotations,
            "cultural_adaptation": cultural_result.model_dump() if cultural_result else None,
            "acceptance_score": -1,
        }

    async def _main_translation(
        self,
        source_text: str,
        genre: str,
        strategy: str,
        target_language: str,
        cultural_constraints: CulturalPreprocessResult | None = None,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
    ) -> str:
        system_prompt = build_translation_system_prompt(
            target_language=target_language,
            genre=genre,
            strategy=strategy,
            cultural_constraints=cultural_constraints,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ]
        result = await bailian_client.chat(model="qwen-max", messages=messages)
        return result["content"]
```

- [ ] **Step 3: 验证现有 prompt 注入测试仍然通过**

```bash
cd backend && pytest tests/test_cultural_prompt_injection.py tests/test_cultural_service.py -v
```

预期：9 passed。

- [ ] **Step 4: 验证模块导入无错误**

```bash
cd backend && source .venv/bin/activate && python -c "from app.services.translation import pipeline, build_translation_system_prompt; print('ok')"
```

预期：输出 `ok`。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/translation.py
git commit -m "feat(backend): wire cultural preprocess into translation pipeline"
```

---

## Task 9：API 层 + Celery 任务接入新字段

**Files:**
- Modify: `backend/app/api/jobs.py`
- Modify: `backend/app/tasks.py`

`create_job` 把 `cultural_sphere` / `audience_type` 写入 TranslationJob；`run_translation` 任务把字段传给 pipeline，并把 `cultural_adaptation` 落到 `translation_results.cultural_adaptation`；`_build_job_response` 透出该字段。

- [ ] **Step 1: 修改 backend/app/api/jobs.py 中的 create_job**

把 `TranslationJob(...)` 构造调用改为：

```python
    job = TranslationJob(
        user_id=user.id,
        source_text=body.source_text,
        genre=body.genre,
        strategy=body.strategy,
        target_languages=body.target_languages,
        cultural_sphere=body.cultural_sphere,
        audience_type=body.audience_type,
        status="pending",
    )
```

- [ ] **Step 2: 修改 _build_job_response 中的 TranslationResultResponse 构造**

把列表生成式中的 `TranslationResultResponse(...)` 改为：

```python
            TranslationResultResponse(
                id=r.id,
                language=r.language,
                status=r.status,
                translated_text=r.translated_text,
                acceptance_score=r.acceptance_score,
                risk_annotations=r.risk_annotations,
                cultural_adaptation=r.cultural_adaptation,
                created_at=r.created_at,
            )
```

- [ ] **Step 3: 修改 backend/app/tasks.py 中的 _run_translation**

把 `pipeline.translate(...)` 调用改为：

```python
                    output = await pipeline.translate(
                        source_text=job.source_text,
                        genre=job.genre,
                        strategy=job.strategy,
                        target_language=lang,
                        cultural_sphere=job.cultural_sphere,
                        audience_type=job.audience_type,
                    )
```

紧随其后写入字段，把：
```python
                    tr.translated_text = output["translated_text"]
                    tr.risk_annotations = output["risk_annotations"]
                    tr.acceptance_score = output["acceptance_score"]
```
改为：
```python
                    tr.translated_text = output["translated_text"]
                    tr.risk_annotations = output["risk_annotations"]
                    tr.cultural_adaptation = output["cultural_adaptation"]
                    tr.acceptance_score = output["acceptance_score"]
```

- [ ] **Step 4: 验证模块导入无错误**

```bash
cd backend && source .venv/bin/activate && python -c "from app.api.jobs import router; from app.tasks import run_translation; print('ok')"
```

预期：输出 `ok`。

- [ ] **Step 5: 验证旧请求仍然兼容（不带新字段）**

启动后端（用项目惯用方式，例如 `uvicorn app.main:app --reload --port 8000`），然后在另一个 shell：

```bash
# 用现有用户登录拿 token，假设 user/pass 已存在；如未存在，先 register
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"<your_user>","password":"<your_pass>"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 不传 cultural_sphere / audience_type，应能正常创建（向后兼容）
curl -s -X POST http://localhost:8000/api/jobs \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"source_text":"测试","genre":"news","strategy":"audience_first","target_languages":["en-GB"]}' | python -m json.tool
```

预期：响应包含 `cultural_adaptation: null`，无错误。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/jobs.py backend/app/tasks.py
git commit -m "feat(backend): plumb cultural fields through API and Celery task"
```

---

## Task 10：前端 store 类型与 action 扩展

**Files:**
- Modify: `frontend/stores/workspace-store.ts`
- Modify: `frontend/stores/translation-store.ts`

新增 `CulturalSphere` / `AudienceType` 类型与 setter；`LangResult` 增 `culturalAdaptation` 字段。

- [ ] **Step 1: 修改 frontend/stores/workspace-store.ts**

完整替换为：

```typescript
import { create } from "zustand";

export type Genre = "political" | "news" | "policy" | "brand";
export type Strategy = "semantic_equivalence" | "audience_first" | "literal_reference";
export type CulturalSphere =
  | "western_english"
  | "european_continental"
  | "islamic_middle_east"
  | "east_asian_confucian"
  | "latin_american"
  | "russian_sphere"
  | "south_asian"
  | "african";
export type AudienceType =
  | "general_public"
  | "media"
  | "government"
  | "academic"
  | "business"
  | "diaspora_chinese";

interface WorkspaceInput {
  text: string;
  genre: Genre;
  strategy: Strategy;
  culturalSphere: CulturalSphere;
  audienceType: AudienceType;
}

interface WorkspaceState {
  input: WorkspaceInput;
  languages: string[];
  isTranslating: boolean;
  currentJobId: string | null;
  setText: (text: string) => void;
  setGenre: (genre: Genre) => void;
  setStrategy: (strategy: Strategy) => void;
  setCulturalSphere: (sphere: CulturalSphere) => void;
  setAudienceType: (audience: AudienceType) => void;
  setLanguages: (languages: string[]) => void;
  setIsTranslating: (v: boolean) => void;
  setCurrentJobId: (id: string | null) => void;
  reset: () => void;
}

const initialState = {
  input: {
    text: "",
    genre: "political" as Genre,
    strategy: "semantic_equivalence" as Strategy,
    culturalSphere: "western_english" as CulturalSphere,
    audienceType: "general_public" as AudienceType,
  },
  languages: ["en-GB"],
  isTranslating: false,
  currentJobId: null as string | null,
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,
  setText: (text) => set((s) => ({ input: { ...s.input, text } })),
  setGenre: (genre) => set((s) => ({ input: { ...s.input, genre } })),
  setStrategy: (strategy) => set((s) => ({ input: { ...s.input, strategy } })),
  setCulturalSphere: (culturalSphere) => set((s) => ({ input: { ...s.input, culturalSphere } })),
  setAudienceType: (audienceType) => set((s) => ({ input: { ...s.input, audienceType } })),
  setLanguages: (languages) => set({ languages }),
  setIsTranslating: (isTranslating) => set({ isTranslating }),
  setCurrentJobId: (currentJobId) => set({ currentJobId }),
  reset: () => set(initialState),
}));
```

- [ ] **Step 2: 修改 frontend/stores/translation-store.ts**

在 `RiskSpan` 接口下方（约第 25 行），新增类型：

```typescript
export type AdaptationStrategy = "literal" | "explanatory" | "analogical" | "reconstruction";

export interface CulturalLoadedTerm {
  term: string;
  culture_gap: "low" | "medium" | "high";
  adaptation_strategy: AdaptationStrategy;
  suggested_rendering: string;
  reason: string;
}

export interface CulturalAdaptation {
  culture_loaded_terms: CulturalLoadedTerm[];
  cultural_notes: string[];
  taboo_warnings: string[];
}
```

修改 `LangResult` 接口增加字段：

```typescript
interface LangResult {
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
  highlightedIndex: number | null;
  culturalAdaptation: CulturalAdaptation | null;
}
```

把每一处 `defaults: LangResult = { ... }` 字面量都新增 `culturalAdaptation: null`，确保所有 5 个出现位置（`setResult`、`appendText`、`acceptRisk`、`dismissRisk`、`revertRisk`、`setAnnotations`）都包含该字段。

例如 `setResult` 内：
```typescript
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
```

`appendText` 内的 inline default：
```typescript
      const existing = s.results[lang] || { status: "streaming" as ResultStatus, translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
```

其余 `defaults` 同理统一新增 `culturalAdaptation: null`。

- [ ] **Step 3: 验证 TypeScript 编译通过**

```bash
cd frontend && pnpm exec tsc --noEmit
```

预期：无错误输出。

- [ ] **Step 4: Commit**

```bash
git add frontend/stores/workspace-store.ts frontend/stores/translation-store.ts
git commit -m "feat(frontend): extend stores with cultural sphere, audience type, adaptation"
```

---

## Task 11：文化圈选择器组件

**Files:**
- Create: `frontend/components/workspace/culture-sphere-selector.tsx`

下拉式选择器，类似 GenreSelector 的 UI 风格但用 select 元素（8 项较多，按钮组太挤）。带 tooltip 显示覆盖国家。

- [ ] **Step 1: 写组件**

```tsx
"use client";

import { CulturalSphere, useWorkspaceStore } from "@/stores/workspace-store";

const SPHERES: { value: CulturalSphere; label: string; tip: string }[] = [
  { value: "western_english", label: "欧美英语圈", tip: "美国、英国、加拿大、澳大利亚" },
  { value: "european_continental", label: "欧洲大陆", tip: "德国、法国、意大利、北欧" },
  { value: "islamic_middle_east", label: "伊斯兰中东", tip: "沙特、阿联酋、伊朗、埃及" },
  { value: "east_asian_confucian", label: "东亚儒家", tip: "日本、韩国" },
  { value: "latin_american", label: "拉美", tip: "巴西、墨西哥、阿根廷" },
  { value: "russian_sphere", label: "俄语圈", tip: "俄罗斯、中亚" },
  { value: "south_asian", label: "南亚", tip: "印度、巴基斯坦、孟加拉" },
  { value: "african", label: "非洲", tip: "南非、尼日利亚、肯尼亚" },
];

export function CultureSphereSelector() {
  const sphere = useWorkspaceStore((s) => s.input.culturalSphere);
  const setSphere = useWorkspaceStore((s) => s.setCulturalSphere);
  const current = SPHERES.find((s) => s.value === sphere) ?? SPHERES[0];

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="shrink-0">文化圈</span>
      <select
        value={sphere}
        onChange={(e) => setSphere(e.target.value as CulturalSphere)}
        title={current.tip}
        className="cursor-pointer rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
      >
        {SPHERES.map((s) => (
          <option key={s.value} value={s.value} title={s.tip}>
            {s.label}
          </option>
        ))}
      </select>
      <span className="text-[11px] text-muted-foreground/70">{current.tip}</span>
    </div>
  );
}
```

- [ ] **Step 2: 验证 TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit
```

预期：无错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/culture-sphere-selector.tsx
git commit -m "feat(frontend): add culture sphere selector"
```

---

## Task 12：受众类型选择器组件

**Files:**
- Create: `frontend/components/workspace/audience-type-selector.tsx`

按钮组，6 项可以放下。

- [ ] **Step 1: 写组件**

```tsx
"use client";

import { AudienceType, useWorkspaceStore } from "@/stores/workspace-store";

const AUDIENCES: { value: AudienceType; label: string; tip: string }[] = [
  { value: "general_public", label: "公众", tip: "简明、故事化、避免术语" },
  { value: "media", label: "媒体", tip: "客观、可引用、Reuters 风格" },
  { value: "government", label: "政府", tip: "正式、精准、政策语言" },
  { value: "academic", label: "学术", tip: "概念完整、引用规范" },
  { value: "business", label: "企业", tip: "数据驱动、商业语言" },
  { value: "diaspora_chinese", label: "海外华人", tip: "文化共鸣 + 当地语境" },
];

export function AudienceTypeSelector() {
  const audience = useWorkspaceStore((s) => s.input.audienceType);
  const setAudience = useWorkspaceStore((s) => s.setAudienceType);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="shrink-0 text-xs text-muted-foreground">受众</span>
      {AUDIENCES.map((a) => (
        <button
          key={a.value}
          onClick={() => setAudience(a.value)}
          title={a.tip}
          className={`cursor-pointer rounded px-2.5 py-1 text-xs transition-colors ${
            audience === a.value
              ? "bg-teal text-white"
              : "bg-muted text-muted-foreground hover:bg-teal-lightest"
          }`}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 验证 TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit
```

预期：无错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/audience-type-selector.tsx
git commit -m "feat(frontend): add audience type selector"
```

---

## Task 13：把两个新选择器嵌入 InputPanel 并把字段传到 API

**Files:**
- Modify: `frontend/components/workspace/input-panel.tsx`

在 GenreSelector 与 TextEditor 之间插入两个新选择器；调用 `/api/jobs` 时带上 `cultural_sphere` / `audience_type`；轮询 `/api/jobs/{id}` 时把 `cultural_adaptation` 写回 store。

- [ ] **Step 1: 在 import 顶部加两个新组件**

```tsx
import { CultureSphereSelector } from "./culture-sphere-selector";
import { AudienceTypeSelector } from "./audience-type-selector";
```

- [ ] **Step 2: 修改 handleTranslate 中的 POST body**

把：
```tsx
      const data = await apiClient.post("/api/jobs", {
        source_text: store.input.text,
        genre: store.input.genre,
        strategy: store.input.strategy,
        target_languages: store.languages,
      });
```
改为：
```tsx
      const data = await apiClient.post("/api/jobs", {
        source_text: store.input.text,
        genre: store.input.genre,
        strategy: store.input.strategy,
        target_languages: store.languages,
        cultural_sphere: store.input.culturalSphere,
        audience_type: store.input.audienceType,
      });
```

- [ ] **Step 3: 修改 pollJobStatus 内的 setResult 调用**

把：
```tsx
        for (const r of data.results) {
          setResult(r.language, {
            status: r.status,
            translatedText: r.translated_text || "",
            riskAnnotations: r.risk_annotations || [],
            acceptanceScore: r.acceptance_score,
          });
        }
```
改为：
```tsx
        for (const r of data.results) {
          setResult(r.language, {
            status: r.status,
            translatedText: r.translated_text || "",
            riskAnnotations: r.risk_annotations || [],
            acceptanceScore: r.acceptance_score,
            culturalAdaptation: r.cultural_adaptation || null,
          });
        }
```

- [ ] **Step 4: 修改 JSX 布局**

把：
```tsx
  return (
    <div className="flex h-full flex-col gap-3">
      <GenreSelector />
      <TextEditor />
      <StrategySelector />
```
改为：
```tsx
  return (
    <div className="flex h-full flex-col gap-3">
      <GenreSelector />
      <CultureSphereSelector />
      <AudienceTypeSelector />
      <TextEditor />
      <StrategySelector />
```

- [ ] **Step 5: 验证 TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit
```

预期：无错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/components/workspace/input-panel.tsx
git commit -m "feat(frontend): wire cultural selectors into input panel"
```

---

## Task 14：文化适配展示面板

**Files:**
- Create: `frontend/components/workspace/cultural-adaptation-panel.tsx`
- Modify: `frontend/components/workspace/translation-result.tsx`

折叠面板显示文化负载词、注意事项、禁忌。

- [ ] **Step 1: 写 cultural-adaptation-panel.tsx**

```tsx
"use client";

import { useState } from "react";
import { useTranslationStore, type AdaptationStrategy } from "@/stores/translation-store";

const STRATEGY_LABELS: Record<AdaptationStrategy, string> = {
  literal: "直译",
  explanatory: "解释型翻译",
  analogical: "类比翻译",
  reconstruction: "场景重构",
};

const GAP_LABELS: Record<"low" | "medium" | "high", string> = {
  low: "差异度: 低",
  medium: "差异度: 中",
  high: "差异度: 高",
};

const GAP_COLORS: Record<"low" | "medium" | "high", string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-orange-100 text-orange-700",
  high: "bg-red-100 text-red-700",
};

export function CulturalAdaptationPanel({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const [open, setOpen] = useState(false);

  const adaptation = result?.culturalAdaptation;
  if (!adaptation) return null;

  const totalTerms = adaptation.culture_loaded_terms.length;
  const hasNotes = adaptation.cultural_notes.length > 0;
  const hasTaboos = adaptation.taboo_warnings.length > 0;
  if (totalTerms === 0 && !hasNotes && !hasTaboos) return null;

  return (
    <div className="mb-2 rounded-md border border-border bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-xs text-foreground hover:bg-muted"
      >
        <span>
          ▾ 文化适配说明
          <span className="ml-2 text-muted-foreground">
            （识别 {totalTerms} 个文化负载词
            {hasNotes ? `、${adaptation.cultural_notes.length} 条注意事项` : ""}
            {hasTaboos ? `、${adaptation.taboo_warnings.length} 条禁忌` : ""}）
          </span>
        </span>
        <span className="text-muted-foreground">{open ? "收起" : "展开"}</span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3 text-xs leading-relaxed">
          {totalTerms > 0 && (
            <div className="space-y-2">
              {adaptation.culture_loaded_terms.map((t, i) => (
                <div key={i} className="rounded border border-border/60 bg-muted/30 p-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium text-foreground">{t.term}</span>
                    <span className="rounded bg-teal-lightest px-1.5 py-0.5 text-[11px] text-teal">
                      {STRATEGY_LABELS[t.adaptation_strategy]}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-[11px] ${GAP_COLORS[t.culture_gap]}`}>
                      {GAP_LABELS[t.culture_gap]}
                    </span>
                  </div>
                  <div className="mt-1 text-muted-foreground">
                    译法：<span className="text-foreground">{t.suggested_rendering}</span>
                  </div>
                  <div className="text-muted-foreground">原因：{t.reason}</div>
                </div>
              ))}
            </div>
          )}
          {hasNotes && (
            <div>
              <div className="mb-1 text-muted-foreground">⚠️ 文化注意事项</div>
              <ul className="list-disc space-y-0.5 pl-5">
                {adaptation.cultural_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
          {hasTaboos && (
            <div>
              <div className="mb-1 text-danger">🚫 禁忌提醒</div>
              <ul className="list-disc space-y-0.5 pl-5 text-danger">
                {adaptation.taboo_warnings.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 修改 frontend/components/workspace/translation-result.tsx**

在 imports 顶部新增：
```tsx
import { CulturalAdaptationPanel } from "./cultural-adaptation-panel";
```

把最终 return 的 JSX 从：
```tsx
  return (
    <div className="h-full overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-white p-3 text-sm leading-relaxed text-foreground">
      {content}
    </div>
  );
```
改为：
```tsx
  return (
    <div className="h-full overflow-y-auto rounded-md border border-border bg-white p-3 text-sm leading-relaxed text-foreground">
      <CulturalAdaptationPanel language={language} />
      <div className="whitespace-pre-wrap">{content}</div>
    </div>
  );
```

- [ ] **Step 3: 验证 TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit
```

预期：无错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/components/workspace/cultural-adaptation-panel.tsx frontend/components/workspace/translation-result.tsx
git commit -m "feat(frontend): show cultural adaptation panel above translation result"
```

---

## Task 15：端到端验证

**Files:** （仅运行项目，不改代码）

启动后端 + Celery worker + 前端，从 UI 跑一次完整翻译，确认链路通畅。

- [ ] **Step 1: 跑一次后端测试套件**

```bash
cd backend && source .venv/bin/activate && pytest -v
```

预期：所有 cultural 相关测试 PASS（约 17 个），没有 FAIL。

- [ ] **Step 2: 启动后端 + Celery + 前端**

按项目惯用方式启动（参考之前 commit 历史的本地启动文档；通常是 3 个终端：`uvicorn app.main:app --reload`、`celery -A app.celery_app worker -l info`、`pnpm dev`）。

- [ ] **Step 3: 浏览器打开 workspace 页**

打开 http://localhost:3000/workspace（或项目实际 URL），登录后应能看到：
- 顶部「文化圈」下拉，默认选中「欧美英语圈」
- 「受众」按钮组，默认选中「公众」
- 现有 GenreSelector / StrategySelector / 语言选择都还在

- [ ] **Step 4: 输入测试文本并触发翻译**

在文本框输入：
```
共同富裕不是平均主义，而是更有质量、更可持续的发展。
```
选择「政治」文体、「欧美英语圈」+「公众」、目标语言英(英)、点击「开始转译」。

- [ ] **Step 5: 等到翻译完成（status 变为 completed），观察右侧结果区**

预期看到：
1. 翻译文本正常出现
2. 翻译文本上方有「▾ 文化适配说明（识别 N 个文化负载词…）」可折叠区
3. 点击展开后能看到至少 1 条文化负载词条目（含术语+策略+差异度+译法+原因）

- [ ] **Step 6: 切换文化圈再翻译一次，验证结果差异**

把文化圈切到「伊斯兰中东」，受众保持「公众」，重新翻译同一段文本，观察文化适配面板里识别的词或注意事项与上一次有差异（哪怕是 cultural_notes / taboo_warnings 不同也算通过）。

- [ ] **Step 7: 向后兼容回归（可选）**

直接用 curl 不带新字段调用 `/api/jobs` 接口（同 Task 9 Step 5），确认依然返回 200 且 `cultural_adaptation: null`。

- [ ] **Step 8: 没有代码改动则不需要 commit**

如果 Step 5/6/7 全部通过，本任务完成；如发现问题，回到对应任务修复并补 commit。

---

## Self-Review

**Spec coverage：**
- 8 个文化圈枚举 → Task 2 / 11 / 数据模型字段
- 6 个受众类型枚举 → Task 2 / 12
- 4 种本土化策略 → Task 3 schema + Task 14 标签
- DB 列 `cultural_sphere` / `audience_type` → Task 4
- DB 列 `cultural_adaptation` → Task 4（spec 文中未单列但流程需要）
- Schema：`CulturalLoadedTerm`、`CulturalPreprocessResult`、`CreateJobRequest` 扩展、`TranslationResultResponse` 扩展 → Task 3
- `CULTURAL_PREPROCESS_PROMPT` → Task 5
- `CULTURAL_SPHERE_PROFILES` / `AUDIENCE_TYPE_GUIDELINES` → Task 2
- `cultural_preprocess` 服务（含降级） → Task 6
- 主翻译 prompt 注入 `<cultural_constraints>` 段（含 MUST_USE / SUGGEST 分级） → Task 7
- Pipeline 编排 3 步 → Task 8
- `create_job` / Celery 接入 → Task 9
- 前端 store / 类型 → Task 10
- 文化圈选择器 / 受众类型选择器 → Task 11 / 12
- InputPanel 集成 / API 调用扩展 → Task 13
- 翻译结果文化适配面板 → Task 14
- 错误处理：预处理失败不阻断主翻译 → Task 6 测试覆盖 + Task 8 编排
- 向后兼容：未传文化字段保持现有行为 → Task 7 测试覆盖 + Task 15 Step 7 回归

**Placeholder scan：** 没有 TBD/TODO；所有代码片段都是完整可运行的内容。

**Type 一致性：**
- 后端 `cultural_sphere` / `audience_type` (str | None) 在 model / schema / API / pipeline / cultural service 中签名一致
- `CulturalPreprocessResult` 在 schema、cultural service、translation service、pipeline 输出中一致
- `cultural_adaptation` 在 ORM 列、`output["cultural_adaptation"]`（dict）、API 响应（CulturalPreprocessResult）一致 —— Pydantic 在 `_build_job_response` 中能直接接受 dict 实例化（v2 默认 model_validate-ish 行为支持 dict 入参）。✓
- 前端 `culturalAdaptation: CulturalAdaptation | null` 与后端 `cultural_adaptation` 字段名映射在 input-panel.tsx Step 3 中显式处理（`r.cultural_adaptation || null`）。✓
- `CulturalSphere` / `AudienceType` 类型字面量在 store 与两个选择器组件中一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-16-cultural-context.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
