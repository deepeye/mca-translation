# 叙事重排 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现“分析叙事结构 → 生成重排预览 → 确认应用”的手动叙事重排闭环。

**Architecture:** 叙事重排作为翻译完成后的独立编辑增强能力实现，不进入默认翻译 pipeline。后端新增 schema/service，并在 jobs API 下暴露 analyze、preview、apply 三个端点；前端在 translation-store 中维护每个语言的叙事状态，并在 OutputPanel 中展示面板。应用预览后写回译文、清理位置敏感状态、记录 narrative 决策日志，并由前端触发全文接受度重算。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, DashScope Bailian, Next.js App Router, React 19, TypeScript, Zustand, Tailwind CSS, shadcn/ui, pytest, Vitest.

## Global Constraints

- 不在翻译完成后默认自动重写正文；用户必须手动触发分析和应用。
- 不把叙事重排嵌入 `TranslationPipeline.translate` 或默认翻译 pipeline。
- 第一版只支持 `mode = "light_cohesion"`。
- 主因标签固定为 `audience_habit`、`cultural_context`、`communication`。
- `confidence` 必须校验为 `0..1` 闭区间。
- `recommended_outline` 可以为空；为空表示无明显重排价值。
- `text_span` 只用于展示定位，不作为稳定 offset。
- `source_ref_ids` 引用 `current_translation_outline` 中的条目 id。
- preview/apply 的 hash 不匹配时返回 HTTP 409，提示 `当前译文已变化，请重新分析叙事结构`。
- 应用后必须清理旧风险高亮/offset、旧接受度评分缓存、旧叙事建议状态。
- 决策日志新增 `narrative` 阶段，阶段排序在 `suggestion` 之后、`acceptance` 之前。
- 前端异步业务逻辑放在 `translation-store`；组件不直接调用 `apiClient`。
- Next.js 为 16.2.9；如果修改 App Router 约定，先阅读 `frontend/node_modules/next/dist/docs/` 相关文档。

---

## File Structure

- Create `backend/app/schemas/narrative_reframe.py`: Pydantic models for reason labels, outlines, analyze/preview/apply requests and responses.
- Create `backend/app/services/narrative_reframe.py`: text hashing, LLM JSON parsing, analyze and preview generation, stale-text validation helpers, decision-log entry builders.
- Modify `backend/app/api/jobs.py`: add `/narrative-reframe/analyze`, `/preview`, `/apply`; apply endpoint writes translated text and invalidates old state.
- Modify `backend/app/services/decision_log.py`: add `narrative` stage order.
- Modify `backend/app/schemas/decision_log.py` if its Literal stage list rejects `narrative`.
- Test `backend/tests/test_narrative_reframe_schemas.py`, `backend/tests/test_narrative_reframe_service.py`, `backend/tests/test_narrative_reframe_api.py`, and update decision-log tests.
- Modify `frontend/lib/api-client.ts`: export narrative types and API methods.
- Modify `frontend/stores/translation-store.ts`: add `NarrativeReframeState` and actions `analyzeNarrativeReframe`, `previewNarrativeReframe`, `applyNarrativeReframe`, `clearNarrativeReframe`.
- Create `frontend/components/workspace/narrative-reason-badge.tsx`.
- Create `frontend/components/workspace/narrative-structure-card.tsx`.
- Create `frontend/components/workspace/narrative-reframe-preview.tsx`.
- Create `frontend/components/workspace/narrative-reframe-panel.tsx`.
- Modify `frontend/components/workspace/output-panel.tsx`: render the panel after `AcceptanceScorePanel` and before risk details.
- Test frontend store and components under existing `__tests__` directories.

---

### Task 1: Backend schemas and narrative service

**Files:**
- Create: `backend/app/schemas/narrative_reframe.py`
- Create: `backend/app/services/narrative_reframe.py`
- Test: `backend/tests/test_narrative_reframe_schemas.py`
- Test: `backend/tests/test_narrative_reframe_service.py`

**Interfaces:**
- Produces: `NarrativeReframeAnalysis`, `NarrativeAnalyzeRequest`, `NarrativeAnalyzeResponse`, `NarrativePreviewRequest`, `NarrativePreviewResponse`, `NarrativeApplyRequest`, `NarrativeApplyResponse`.
- Produces service functions: `compute_text_hash(text: str) -> str`, `parse_analysis_payload(content: str) -> NarrativeReframeAnalysis`, class `NarrativeReframeService` with async `analyze(...)` and `preview(...)`.

- [ ] **Step 1: Write schema validation tests**

Create `backend/tests/test_narrative_reframe_schemas.py` with tests that assert:

```python
import pytest
from pydantic import ValidationError
from app.schemas.narrative_reframe import (
    NarrativeReframeAnalysis,
    NarrativeRecommendedItem,
    NarrativePreviewRequest,
)


def _analysis(confidence=0.8, reason_label="audience_habit"):
    return NarrativeReframeAnalysis(
        source_outline=[{"id": "s1", "order": 1, "summary": "背景", "text_span": "背景段"}],
        current_translation_outline=[{"id": "t1", "order": 1, "summary": "Background", "text_span": "Background"}],
        recommended_outline=[{
            "id": "r1", "target_order": 1, "source_ref_ids": ["t1"],
            "summary": "Lead with impact", "reason_label": reason_label,
            "reason": "目标受众先看影响", "expected_effect": "更快进入主题",
        }],
        overall_rationale="当前结构背景先行。",
        confidence=confidence,
    )


def test_analysis_accepts_valid_payload():
    assert _analysis().recommended_outline[0].reason_label == "audience_habit"


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence):
    with pytest.raises(ValidationError):
        _analysis(confidence=confidence)


def test_reason_label_must_be_known_literal():
    with pytest.raises(ValidationError):
        _analysis(reason_label="other")


def test_preview_mode_only_supports_light_cohesion():
    NarrativePreviewRequest(lang="en", analysis=_analysis(), text_hash="abc", mode="light_cohesion")
    with pytest.raises(ValidationError):
        NarrativePreviewRequest(lang="en", analysis=_analysis(), text_hash="abc", mode="full_rewrite")
```

- [ ] **Step 2: Run schema tests and confirm failure**

Run: `cd backend && pytest tests/test_narrative_reframe_schemas.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.narrative_reframe'`.

- [ ] **Step 3: Implement narrative schemas**

Create `backend/app/schemas/narrative_reframe.py`:

```python
from typing import Literal
from pydantic import BaseModel, Field

NarrativeReasonLabel = Literal["audience_habit", "cultural_context", "communication"]
NarrativePreviewMode = Literal["light_cohesion"]


class NarrativeOutlineItem(BaseModel):
    id: str
    order: int
    summary: str
    text_span: str


class NarrativeRecommendedItem(BaseModel):
    id: str
    target_order: int
    source_ref_ids: list[str] = Field(default_factory=list)
    summary: str
    reason_label: NarrativeReasonLabel
    reason: str
    expected_effect: str


class NarrativeReframeAnalysis(BaseModel):
    source_outline: list[NarrativeOutlineItem] = Field(default_factory=list)
    current_translation_outline: list[NarrativeOutlineItem] = Field(default_factory=list)
    recommended_outline: list[NarrativeRecommendedItem] = Field(default_factory=list)
    overall_rationale: str
    confidence: float = Field(ge=0, le=1)


class NarrativeAnalyzeRequest(BaseModel):
    lang: str


class NarrativeAnalyzeResponse(BaseModel):
    analysis: NarrativeReframeAnalysis
    text_hash: str


class NarrativePreviewRequest(BaseModel):
    lang: str
    analysis: NarrativeReframeAnalysis
    text_hash: str
    mode: NarrativePreviewMode = "light_cohesion"


class NarrativePreviewResponse(BaseModel):
    preview_text: str
    text_hash: str


class NarrativeApplyRequest(BaseModel):
    lang: str
    preview_text: str
    analysis: NarrativeReframeAnalysis
    text_hash: str


class NarrativeApplyResponse(BaseModel):
    result: dict
    text_hash: str
```

- [ ] **Step 4: Write service tests**

Create `backend/tests/test_narrative_reframe_service.py`:

```python
import json
import pytest
from app.schemas.narrative_reframe import NarrativeReframeAnalysis
from app.services.narrative_reframe import compute_text_hash, parse_analysis_payload, NarrativeReframeService


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, temperature=0.3):
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        return {"content": self.content}


def test_compute_text_hash_is_stable_sha256():
    assert compute_text_hash("Hello") == compute_text_hash("Hello")
    assert compute_text_hash("Hello") != compute_text_hash("Hello!")
    assert len(compute_text_hash("Hello")) == 64


def test_parse_analysis_payload_accepts_json_fenced_block():
    payload = {
        "source_outline": [], "current_translation_outline": [], "recommended_outline": [],
        "overall_rationale": "无需重排", "confidence": 0.7,
    }
    parsed = parse_analysis_payload("```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```")
    assert isinstance(parsed, NarrativeReframeAnalysis)
    assert parsed.overall_rationale == "无需重排"


def test_parse_analysis_payload_rejects_invalid_json():
    with pytest.raises(ValueError, match="Invalid narrative analysis JSON"):
        parse_analysis_payload("not json")


@pytest.mark.asyncio
async def test_analyze_calls_llm_and_returns_schema():
    payload = {
        "source_outline": [{"id": "s1", "order": 1, "summary": "背景", "text_span": "背景"}],
        "current_translation_outline": [{"id": "t1", "order": 1, "summary": "Background", "text_span": "Background"}],
        "recommended_outline": [],
        "overall_rationale": "结构可接受", "confidence": 0.9,
    }
    service = NarrativeReframeService(llm_client=FakeClient(json.dumps(payload, ensure_ascii=False)))
    analysis = await service.analyze(
        source_text="背景", translated_text="Background", genre="news",
        target_language="en", cultural_sphere="western", audience_type="general_public",
    )
    assert analysis.confidence == 0.9


@pytest.mark.asyncio
async def test_preview_returns_llm_text():
    service = NarrativeReframeService(llm_client=FakeClient("Lead first. Background second."))
    analysis = NarrativeReframeAnalysis(source_outline=[], current_translation_outline=[], recommended_outline=[], overall_rationale="ok", confidence=0.8)
    text = await service.preview(translated_text="Background. Lead.", analysis=analysis, target_language="en", mode="light_cohesion")
    assert text == "Lead first. Background second."
```

- [ ] **Step 5: Run service tests and confirm failure**

Run: `cd backend && pytest tests/test_narrative_reframe_service.py -q`

Expected: FAIL because `app.services.narrative_reframe` does not exist.

- [ ] **Step 6: Implement service**

Create `backend/app/services/narrative_reframe.py` with SHA-256 hashing, fenced JSON extraction, and `NarrativeReframeService`. Use `settings.BAILIAN_MODEL` if present, otherwise `qwen-plus`. Prompts must explicitly request JSON for analyze and light-cohesion only for preview.

- [ ] **Step 7: Run task tests**

Run: `cd backend && pytest tests/test_narrative_reframe_schemas.py tests/test_narrative_reframe_service.py -q`

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/narrative_reframe.py backend/app/services/narrative_reframe.py backend/tests/test_narrative_reframe_schemas.py backend/tests/test_narrative_reframe_service.py
git commit -m "feat(narrative): add reframe schemas and service"
```

---

### Task 2: Backend jobs API endpoints and decision log integration

**Files:**
- Modify: `backend/app/api/jobs.py`
- Modify: `backend/app/services/decision_log.py`
- Modify: `backend/app/schemas/decision_log.py` if needed
- Test: `backend/tests/test_narrative_reframe_api.py`
- Test: `backend/tests/test_decision_log_service.py`

**Interfaces:**
- Consumes Task 1 schemas/service.
- Produces endpoints:
  - `POST /api/jobs/{job_id}/narrative-reframe/analyze`
  - `POST /api/jobs/{job_id}/narrative-reframe/preview`
  - `POST /api/jobs/{job_id}/narrative-reframe/apply`

- [ ] **Step 1: Add decision-log ordering test**

Append to `backend/tests/test_decision_log_service.py`:

```python
def test_narrative_stage_ordered_between_suggestion_and_acceptance():
    from app.services.decision_log import _STAGE_ORDER
    assert "narrative" in _STAGE_ORDER
    assert _STAGE_ORDER["suggestion"] < _STAGE_ORDER["narrative"] < _STAGE_ORDER["acceptance"]
```

- [ ] **Step 2: Write API tests**

Create `backend/tests/test_narrative_reframe_api.py`. Seed a user, job, and result like `test_acceptance_api.py`; override `get_current_user` and `get_db`; monkeypatch `app.api.jobs._narrative_service` with a fake service. Cover:

```python
# analyze returns analysis + current text_hash
# analyze returns 400 when source_text is empty or translated_text is empty
# preview returns 409 when text_hash is stale
# preview returns preview_text when hash matches
# apply returns 409 when text_hash is stale
# apply writes preview_text, sets risk_annotations to [], acceptance_score to -1,
# clears acceptance_dimensions, acceptance_sentence_scores, acceptance_confidence,
# returns new text_hash, and creates at least one narrative decision log id
```

The fake service should implement:

```python
class FakeNarrativeService:
    async def analyze(self, **kwargs):
        return NarrativeReframeAnalysis(
            source_outline=[], current_translation_outline=[], recommended_outline=[],
            overall_rationale="结构可接受", confidence=0.8,
        )

    async def preview(self, **kwargs):
        return "Lead first. Background second."
```

- [ ] **Step 3: Run API tests and confirm failure**

Run: `cd backend && pytest tests/test_decision_log_service.py::test_narrative_stage_ordered_between_suggestion_and_acceptance tests/test_narrative_reframe_api.py -q`

Expected: FAIL because endpoints and stage order are missing.

- [ ] **Step 4: Update decision log stage order**

In `backend/app/services/decision_log.py`, change `_STAGE_ORDER` to include:

```python
"suggestion": 4,
"narrative": 5,
"acceptance": 6,
```

Update comments to mention `narrative`.

If `backend/app/schemas/decision_log.py` has a Literal stage list, add `"narrative"` to it.

- [ ] **Step 5: Add route imports and singleton**

In `backend/app/api/jobs.py`, import Task 1 schemas, service, and `compute_text_hash`; create `_narrative_service = NarrativeReframeService()` near `_acceptance_scorer`.

- [ ] **Step 6: Implement analyze endpoint**

Endpoint behavior:
- Load user job and language result.
- If `job.source_text` is empty, raise 400 `Missing source text`.
- If `result.translated_text` is empty, raise 400 `Translation not ready`.
- Call `_narrative_service.analyze(...)` with source text, translated text, genre, lang, cultural sphere, audience type.
- Save a narrative decision log entry with `decision_type="narrative_analysis"` and `reasoning=analysis.overall_rationale`; append ids to `result.decision_log_ids`; commit.
- Return `NarrativeAnalyzeResponse(analysis=analysis, text_hash=compute_text_hash(result.translated_text or ""))`.

- [ ] **Step 7: Implement preview endpoint**

Endpoint behavior:
- Load job/result and validate translated text.
- Compare current hash with request hash; if mismatch, raise HTTP 409 with exact detail.
- Call `_narrative_service.preview(...)` with `mode="light_cohesion"`.
- Save narrative decision log entry with `decision_type="narrative_preview"`, metadata including `mode` and `recommended_count`.
- Return preview text and current text hash.

- [ ] **Step 8: Implement apply endpoint**

Endpoint behavior:
- Load job/result and validate translated text.
- Compare current hash with request hash; if mismatch, raise HTTP 409 with exact detail.
- Set `result.translated_text = body.preview_text`.
- Set `result.risk_annotations = []` and `flag_modified(result, "risk_annotations")`.
- Set `result.acceptance_score = -1`, `result.acceptance_confidence = None`, `result.acceptance_dimensions = None`, `result.acceptance_sentence_scores = None`, `result.audience_baseline = None` and flag JSON fields.
- Save narrative decision log entry with `decision_type="narrative_applied"`.
- Append log ids, commit, refresh, and return `NarrativeApplyResponse(result=_build_job_response(job, [result]).model_dump(mode="json"), text_hash=compute_text_hash(body.preview_text))`.

- [ ] **Step 9: Run backend tests**

Run: `cd backend && pytest tests/test_narrative_reframe_schemas.py tests/test_narrative_reframe_service.py tests/test_narrative_reframe_api.py tests/test_decision_log_service.py -q`

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/jobs.py backend/app/services/decision_log.py backend/app/schemas/decision_log.py backend/tests/test_narrative_reframe_api.py backend/tests/test_decision_log_service.py
git commit -m "feat(narrative): add reframe job endpoints"
```

---

### Task 3: Frontend API client and Zustand narrative state

**Files:**
- Modify: `frontend/lib/api-client.ts`
- Modify: `frontend/stores/translation-store.ts`
- Test: `frontend/stores/__tests__/narrative-reframe-store.test.ts`

**Interfaces:**
- Consumes backend endpoints from Task 2.
- Produces frontend types mirroring backend schema.
- Produces store actions: `analyzeNarrativeReframe(lang)`, `previewNarrativeReframe(lang)`, `applyNarrativeReframe(lang)`, `clearNarrativeReframe(lang)`.

- [ ] **Step 1: Write store tests**

Create `frontend/stores/__tests__/narrative-reframe-store.test.ts` mocking `apiClient` and `useWorkspaceStore` like `acceptance-store.test.ts`. Cover:

```ts
// analyze sets isAnalyzing true, stores analysis and lastAnalyzedTextHash on success
// preview requires existing analysis and text_hash, stores previewText on success
// apply calls apiClient.applyNarrativeReframe, updates translatedText from returned result, clears riskAnnotations, clears acceptance score fields, clears previewText/analysis stale state, then calls triggerFirstScoring with current or default baseline
// stale-text API error stores the exact error message and returns false
// acceptRisk/revertRisk/setResult changing translatedText marks existing narrative state stale by preserving analysis but changing current hash comparison inputs
```

Use expected low-score threshold-independent state assertions; UI threshold belongs to Task 4.

- [ ] **Step 2: Run store tests and confirm failure**

Run: `cd frontend && pnpm test stores/__tests__/narrative-reframe-store.test.ts`

Expected: FAIL because client methods and store actions do not exist.

- [ ] **Step 3: Add API client narrative types and methods**

In `frontend/lib/api-client.ts`:
- Add `"narrative"` to `DecisionLogEntry.stage` union.
- Export `NarrativeReasonLabel`, outline interfaces, `NarrativeReframeAnalysis`, and response interfaces.
- Add methods:

```ts
async analyzeNarrativeReframe(jobId: string, lang: string): Promise<NarrativeAnalyzeResponse> {
  return this.post(`/api/jobs/${jobId}/narrative-reframe/analyze`, { lang });
}

async previewNarrativeReframe(jobId: string, body: NarrativePreviewRequest): Promise<NarrativePreviewResponse> {
  return this.post(`/api/jobs/${jobId}/narrative-reframe/preview`, body);
}

async applyNarrativeReframe(jobId: string, body: NarrativeApplyRequest): Promise<NarrativeApplyResponse> {
  return this.post(`/api/jobs/${jobId}/narrative-reframe/apply`, body);
}
```

- [ ] **Step 4: Add store state defaults**

In `frontend/stores/translation-store.ts`, add exported `NarrativeReframeState` and add `narrativeReframe: NarrativeReframeState` to `LangResult`. Create a `defaultNarrativeReframe()` helper returning all fields from spec.

- [ ] **Step 5: Invalidate narrative state on text changes**

When `setResult`, `appendText`, `acceptRisk`, `revertRisk`, and `loadFromHistory` set or change `translatedText`, ensure each lang has a narrative object and clear `previewText` if the text changes. Keep `analysis` and `lastAnalyzedTextHash` so the UI can show “可能已过期”.

- [ ] **Step 6: Implement store actions**

Implement actions:
- `analyzeNarrativeReframe`: require current job id, call API, store `analysis`, `lastAnalyzedTextHash`, clear `previewText`, clear `error`, toggle `isAnalyzing`.
- `previewNarrativeReframe`: require analysis/hash, call API with `mode: "light_cohesion"`, store `previewText`, toggle `isPreviewing`.
- `applyNarrativeReframe`: require analysis/preview/hash, call API, update current lang from returned `result.results[0]`, clear risk annotations, reset acceptance fields, clear narrative analysis/preview/hash, then call `triggerFirstScoring(lang, existing.audienceBaseline || "policy_media")`.
- `clearNarrativeReframe`: reset narrative state for lang.

- [ ] **Step 7: Run frontend store tests**

Run: `cd frontend && pnpm test stores/__tests__/narrative-reframe-store.test.ts stores/__tests__/acceptance-store.test.ts`

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/api-client.ts frontend/stores/translation-store.ts frontend/stores/__tests__/narrative-reframe-store.test.ts
git commit -m "feat(narrative): add frontend reframe state"
```

---

### Task 4: Frontend narrative UI components and OutputPanel integration

**Files:**
- Create: `frontend/components/workspace/narrative-reason-badge.tsx`
- Create: `frontend/components/workspace/narrative-structure-card.tsx`
- Create: `frontend/components/workspace/narrative-reframe-preview.tsx`
- Create: `frontend/components/workspace/narrative-reframe-panel.tsx`
- Modify: `frontend/components/workspace/output-panel.tsx`
- Test: `frontend/components/workspace/__tests__/narrative-reason-badge.test.tsx`
- Test: `frontend/components/workspace/__tests__/narrative-structure-card.test.tsx`
- Test: `frontend/components/workspace/__tests__/narrative-reframe-panel.test.tsx`

**Interfaces:**
- Consumes store state/actions from Task 3.
- Produces workspace UI for low-score hint, manual analysis, structure cards, preview, cancel, and apply.

- [ ] **Step 1: Write component tests**

Create tests that assert:
- `NarrativeReasonBadge` maps `audience_habit` to `受众阅读习惯`, `cultural_context` to `文化认知差异`, and `communication` to `传播效果`.
- `NarrativeStructureCard` renders current outline and recommended outline, including summary, text span, target order, reason, and expected effect.
- `NarrativeReframePanel` renders nothing unless result is completed with translated text.
- Low-score hint appears when `acceptanceScore < 75`, or `acceptanceDimensions.naturalness < 18`, or `acceptanceDimensions.audience < 18`.
- Clicking `分析叙事结构` calls `analyzeNarrativeReframe(language)`.
- Empty recommendations render `当前结构已较符合目标受众阅读习惯`.
- If current translated text hash differs from `lastAnalyzedTextHash`, UI shows `当前译文可能已变化` and disables apply.
- Clicking preview/apply/cancel calls the corresponding store actions.

- [ ] **Step 2: Run component tests and confirm failure**

Run: `cd frontend && pnpm test components/workspace/__tests__/narrative-reason-badge.test.tsx components/workspace/__tests__/narrative-structure-card.test.tsx components/workspace/__tests__/narrative-reframe-panel.test.tsx`

Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement `NarrativeReasonBadge`**

Create a small pure component that renders labels with subtle Tailwind classes:
- `audience_habit` -> `受众阅读习惯`
- `cultural_context` -> `文化认知差异`
- `communication` -> `传播效果`

- [ ] **Step 4: Implement `NarrativeStructureCard`**

Render two columns/sections:
- `当前译文结构`: ordered list from `current_translation_outline`, showing order, summary, and `text_span` in muted text.
- `建议受众结构`: ordered list from `recommended_outline`, showing `target_order`, summary, `NarrativeReasonBadge`, reason, expected effect, and source ids.
- If recommendations are empty, show `当前结构已较符合目标受众阅读习惯`.

- [ ] **Step 5: Implement `NarrativeReframePreview`**

Render preview text in a bordered block and buttons:
- `取消预览` calls `onCancel`.
- `应用到译文` calls `onApply`, disabled when `disabled` or `isApplying`.

- [ ] **Step 6: Implement `NarrativeReframePanel`**

Behavior:
- Return `null` unless current result is completed and has translated text.
- Header label: `叙事重排建议`.
- Low-score hint condition: `acceptanceScore >= 0 && acceptanceScore < 75`, or `acceptanceDimensions?.naturalness < 18`, or `acceptanceDimensions?.audience < 18`.
- Manual button `分析叙事结构` calls store action and shows loading text while analyzing.
- If `analysis.confidence < 0.5`, show `建议仅供参考`.
- Compute staleness with a frontend SHA-256 helper if available; if not, compare `lastAnalyzedTextHash` only through a store-provided stale flag added in Task 3. Do not enable apply when stale.
- Show errors from state.
- Show structure card after analysis.
- Show `生成重排预览` button after analysis; disable if stale or no recommendations.
- Show preview component after preview generation.

- [ ] **Step 7: Integrate into OutputPanel**

In `frontend/components/workspace/output-panel.tsx`, import `NarrativeReframePanel` and render:

```tsx
<AcceptanceScorePanel language={activeLang} />
<NarrativeReframePanel language={activeLang} />
<RiskDetailList language={activeLang} jobId={jobId} />
```

- [ ] **Step 8: Run frontend component tests**

Run: `cd frontend && pnpm test components/workspace/__tests__/narrative-reason-badge.test.tsx components/workspace/__tests__/narrative-structure-card.test.tsx components/workspace/__tests__/narrative-reframe-panel.test.tsx components/workspace/__tests__/acceptance-score-panel.test.tsx`

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/components/workspace/narrative-*.tsx frontend/components/workspace/output-panel.tsx frontend/components/workspace/__tests__/narrative-*.test.tsx
git commit -m "feat(narrative): add reframe workspace panel"
```

---

### Task 5: End-to-end verification and polish

**Files:**
- Modify only files needed to fix failures from this task.
- No new feature scope.

**Interfaces:**
- Consumes Tasks 1-4.
- Produces a verified feature branch ready for final review.

- [ ] **Step 1: Run backend narrative tests**

Run: `cd backend && pytest tests/test_narrative_reframe_schemas.py tests/test_narrative_reframe_service.py tests/test_narrative_reframe_api.py tests/test_decision_log_service.py -q`

Expected: PASS.

- [ ] **Step 2: Run backend acceptance regression tests**

Run: `cd backend && pytest tests/test_acceptance_api.py tests/test_acceptance_schemas.py tests/test_decisions_api.py -q`

Expected: PASS.

- [ ] **Step 3: Run frontend narrative tests**

Run: `cd frontend && pnpm test stores/__tests__/narrative-reframe-store.test.ts components/workspace/__tests__/narrative-reason-badge.test.tsx components/workspace/__tests__/narrative-structure-card.test.tsx components/workspace/__tests__/narrative-reframe-panel.test.tsx`

Expected: PASS.

- [ ] **Step 4: Run frontend regression tests**

Run: `cd frontend && pnpm test stores/__tests__/acceptance-store.test.ts components/workspace/__tests__/acceptance-score-panel.test.tsx components/workspace/__tests__/decision-log-panel.test.tsx`

Expected: PASS.

- [ ] **Step 5: Run type/build checks**

Run: `cd frontend && pnpm build`

Expected: build succeeds.

- [ ] **Step 6: Manual integration smoke test**

Start app dependencies as usual, then verify:
1. Complete a translation.
2. Click `分析叙事结构`.
3. Confirm structure cards render.
4. Click `生成重排预览`.
5. Click `应用到译文`.
6. Confirm translated text changes, old risk highlights disappear, acceptance score re-enters scoring/loading or refreshes, and decision log includes narrative entries.

- [ ] **Step 7: Commit fixes if any**

If Step 1-6 required code changes:

```bash
git add backend frontend
git commit -m "fix(narrative): polish reframe integration"
```

If no changes were needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: manual analyze, low-score hint, compare current/suggested structure, reason labels, preview, apply with hash, stale state, invalidation, acceptance recompute, and narrative decision logs are covered.
- Placeholder scan: no `TBD`, `TODO`, or `implement later` steps are required for implementation.
- Type consistency: backend and frontend names use `NarrativeReframeAnalysis`, `NarrativePreviewRequest`, `NarrativeApplyRequest`, `light_cohesion`, and the same reason-label values.
