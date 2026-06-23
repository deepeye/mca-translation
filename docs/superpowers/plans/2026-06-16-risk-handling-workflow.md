# Risk Handling Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add suggestion generation, accept/dismiss/revert risk actions, and accept-all batch operation to the translation risk annotation system.

**Architecture:** Backend adds 5 new API endpoints under `/api/jobs/{id}/` for on-demand suggestion generation and risk state transitions. A new `SuggestionService` handles LLM calls for replacement suggestions. Frontend extends `RiskDetailCard` with suggestion UI, adds store actions for risk state management, and updates `TranslationResult` mark styles for accepted/dismissed states.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, BailianClient (qwen-plus), Next.js 16, React 19, Zustand 5, shadcn/ui, Tailwind CSS 4

---

## File Structure

### Backend — Create
- `backend/app/services/suggestion.py` — SuggestionService: LLM call for generating replacement suggestions

### Backend — Modify
- `backend/app/schemas/job.py` — Add `Suggestion`, `AcceptRiskRequest`, `SuggestionResponse` schemas
- `backend/app/api/jobs.py` — Add 5 new endpoints for suggestion generation and risk state operations
- `backend/app/llm/prompts.py` — Add `SUGGESTION_PROMPT` template

### Frontend — Modify
- `frontend/stores/translation-store.ts` — Extend `RiskAnnotation` type, add `acceptRisk`/`dismissRisk`/`revertRisk` actions
- `frontend/components/workspace/risk-detail-list.tsx` — Add suggestion UI, accept/dismiss/revert buttons, accept-all button, status-aware card rendering
- `frontend/components/workspace/translation-result.tsx` — Add accepted/dismissed mark styles, update `locateRisks` to skip non-open risks
- `frontend/lib/api-client.ts` — Add `put` method for new endpoints

---

## Task 1: Backend — Suggestion Prompt & Service

**Files:**
- Modify: `backend/app/llm/prompts.py`
- Create: `backend/app/services/suggestion.py`

- [x] **Step 1: Add SUGGESTION_PROMPT to prompts.py**

Append after `RISK_ANNOTATION_PROMPT` in `backend/app/llm/prompts.py`:

```python
SUGGESTION_PROMPT = """You are a cultural adaptation expert. Given the original Chinese text, its translation, and a specific risky expression identified in the translation, suggest 1-2 culturally appropriate replacement phrases that would reduce the risk for the target audience.

For each suggestion, provide:
- text: the replacement phrase (in the target language)
- reason: a brief explanation of why this replacement is better

Original Chinese:
{source_text}

Translation ({target_language}):
{translated_text}

Risky expression: "{phrase}"
Risk type: {risk_type}
Risk explanation: {explanation}

Return a JSON array of suggestions. Return ONLY the JSON array, no other text."""
```

- [x] **Step 2: Create SuggestionService**

Create `backend/app/services/suggestion.py`:

```python
import json
import logging

from app.llm.bailian import bailian_client
from app.llm.prompts import SUGGESTION_PROMPT

logger = logging.getLogger(__name__)


class SuggestionService:
    """Generate replacement suggestions for risky expressions."""

    async def generate(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        phrase: str,
        risk_type: str,
        explanation: str,
    ) -> list[dict]:
        prompt = SUGGESTION_PROMPT.format(
            source_text=source_text,
            translated_text=translated_text,
            target_language=target_language,
            phrase=phrase,
            risk_type=risk_type,
            explanation=explanation,
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
            content = result["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            suggestions = json.loads(content)
            if isinstance(suggestions, list):
                return suggestions
            return []
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Suggestion generation parsing failed: {e}")
            return []


suggestion_service = SuggestionService()
```

- [x] **Step 3: Verify import works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.services.suggestion import suggestion_service; print('OK')"`
Expected: `OK`

- [x] **Step 4: Commit**

```bash
git add backend/app/llm/prompts.py backend/app/services/suggestion.py
git commit -m "feat: add suggestion generation prompt and SuggestionService"
```

---

## Task 2: Backend — Schemas for Suggestion & Risk Operations

**Files:**
- Modify: `backend/app/schemas/job.py`

- [x] **Step 1: Add new schemas**

Append to `backend/app/schemas/job.py` after `JobListItem`:

```python
class Suggestion(BaseModel):
    text: str
    reason: str


class SuggestionResponse(BaseModel):
    suggestions: list[Suggestion]


class AcceptRiskRequest(BaseModel):
    suggestion: str
    lang: str


class DismissRiskRequest(BaseModel):
    lang: str


class RevertRiskRequest(BaseModel):
    lang: str


class AcceptAllRequest(BaseModel):
    lang: str
```

- [x] **Step 2: Verify import works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.schemas.job import SuggestionResponse, AcceptRiskRequest; print('OK')"`
Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/app/schemas/job.py
git commit -m "feat: add schemas for suggestion and risk operation endpoints"
```

---

## Task 3: Backend — Risk Operation API Endpoints

**Files:**
- Modify: `backend/app/api/jobs.py`

This is the core backend task. We add 5 endpoints and a helper function for offset recalculation.

- [x] **Step 1: Add imports and helper function**

At the top of `backend/app/api/jobs.py`, add imports:

```python
from app.schemas.job import (
    AcceptAllRequest, AcceptRiskRequest, CreateJobRequest, DismissRiskRequest,
    JobListItem, JobResponse, RevertRiskRequest, SuggestionResponse, TranslationResultResponse,
)
from app.services.suggestion import suggestion_service
```

Add helper function after `_build_job_response`:

```python
def _recalculate_offsets(text: str, annotations: list[dict]) -> list[dict]:
    """Recalculate offsets for all open risk annotations after text change."""
    used_offsets = set()
    for ann in annotations:
        if ann.get("status", "open") != "open":
            continue
        offset = text.find(ann["phrase"])
        if offset == -1 or offset in used_offsets:
            offset = -1
        else:
            used_offsets.add(offset)
        ann["offset"] = offset
    return annotations
```

- [x] **Step 2: Add GET suggestions endpoint**

Append after `delete_job`:

```python
@router.get("/{job_id}/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    job_id: uuid.UUID,
    lang: str,
    risk_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    suggestions = await suggestion_service.generate(
        source_text=job.source_text,
        translated_text=result.translated_text,
        target_language=lang,
        phrase=ann["phrase"],
        risk_type=ann.get("risk_type", ""),
        explanation=ann.get("explanation", ""),
    )
    return SuggestionResponse(suggestions=suggestions)
```

- [x] **Step 3: Add POST accept/dismiss/revert endpoints**

```python
@router.post("/{job_id}/risks/{risk_index}/accept")
async def accept_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: AcceptRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    if ann.get("status", "open") != "open":
        raise HTTPException(status_code=400, detail="Risk is not in open state")

    # Replace phrase at offset with suggestion
    offset = ann.get("offset")
    text = result.translated_text or ""
    if offset is not None and offset >= 0 and text[offset:offset + len(ann["phrase"])] == ann["phrase"]:
        text = text[:offset] + body.suggestion + text[offset + len(ann["phrase"]):]
    else:
        text = text.replace(ann["phrase"], body.suggestion, 1)

    ann["status"] = "accepted"
    ann["accepted_suggestion"] = body.suggestion
    result.translated_text = text
    result.risk_annotations = _recalculate_offsets(text, annotations)
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


@router.post("/{job_id}/risks/{risk_index}/dismiss")
async def dismiss_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: DismissRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    annotations[risk_index]["status"] = "dismissed"
    result.risk_annotations = annotations
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


@router.post("/{job_id}/risks/{risk_index}/revert")
async def revert_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: RevertRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    if ann.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="Risk is not in accepted state")

    # Restore original phrase
    suggestion = ann["accepted_suggestion"]
    phrase = ann["phrase"]
    text = result.translated_text or ""
    text = text.replace(suggestion, phrase, 1)

    ann["status"] = "open"
    del ann["accepted_suggestion"]
    result.translated_text = text
    result.risk_annotations = _recalculate_offsets(text, annotations)
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])
```

- [x] **Step 4: Add POST accept-all endpoint**

```python
import asyncio

_accept_all_locks: dict[str, asyncio.Lock] = {}


@router.post("/{job_id}/risks/accept-all")
async def accept_all_risks(
    job_id: uuid.UUID,
    body: AcceptAllRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lock_key = f"{job_id}:{body.lang}"
    if lock_key not in _accept_all_locks:
        _accept_all_locks[lock_key] = asyncio.Lock()
    if _accept_all_locks[lock_key].locked():
        raise HTTPException(status_code=409, detail="Batch processing in progress")

    async with _accept_all_locks[lock_key]:
        job = await _get_user_job(job_id, user, db)
        result = await _get_lang_result(job.id, body.lang, db)
        annotations = result.risk_annotations or []
        skipped = []

        for i, ann in enumerate(annotations):
            if ann.get("status", "open") != "open":
                continue
            suggestions = await suggestion_service.generate(
                source_text=job.source_text,
                translated_text=result.translated_text,
                target_language=body.lang,
                phrase=ann["phrase"],
                risk_type=ann.get("risk_type", ""),
                explanation=ann.get("explanation", ""),
            )
            if not suggestions:
                skipped.append(i)
                continue

            suggestion = suggestions[0]["text"]
            offset = ann.get("offset")
            text = result.translated_text or ""
            if offset is not None and offset >= 0 and text[offset:offset + len(ann["phrase"])] == ann["phrase"]:
                text = text[:offset] + suggestion + text[offset + len(ann["phrase"]):]
            else:
                text = text.replace(ann["phrase"], suggestion, 1)

            ann["status"] = "accepted"
            ann["accepted_suggestion"] = suggestion
            result.translated_text = text
            result.risk_annotations = _recalculate_offsets(text, annotations)

        await db.commit()
        await db.refresh(result)

    response = _build_job_response(job, [result])
    if skipped:
        response["skipped_risk_indices"] = skipped
    return response
```

- [x] **Step 5: Add helper functions used by new endpoints**

Add these two helpers before `_build_job_response`:

```python
async def _get_user_job(job_id: uuid.UUID, user: User, db: AsyncSession) -> TranslationJob:
    job = (
        await db.execute(
            select(TranslationJob).where(
                TranslationJob.id == job_id,
                TranslationJob.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _get_lang_result(job_id: uuid.UUID, lang: str, db: AsyncSession) -> TranslationResult:
    result = (
        await db.execute(
            select(TranslationResult).where(
                TranslationResult.job_id == job_id,
                TranslationResult.language == lang,
            )
        )
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Translation result not found")
    return result
```

Also refactor `get_job` and `delete_job` to use `_get_user_job` instead of inline queries (replace the inline query blocks in those two functions with `job = await _get_user_job(job_id, user, db)`).

- [x] **Step 6: Verify backend starts**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.api.jobs import router; print('OK')"`
Expected: `OK`

- [x] **Step 7: Commit**

```bash
git add backend/app/api/jobs.py
git commit -m "feat: add suggestion generation and risk state operation API endpoints"
```

---

## Task 4: Backend — Populate offset Field During Risk Annotation

**Files:**
- Modify: `backend/app/services/translation.py`

The current pipeline returns risk annotations without `offset` or `status` fields. We need to add those so the new endpoints can work with existing data.

- [x] **Step 1: Add offset calculation and default status to `_risk_annotation`**

In `backend/app/services/translation.py`, modify `_risk_annotation` to compute offsets and set defaults:

```python
async def _risk_annotation(self, source_text: str, translated_text: str, target_language: str) -> list:
    prompt = RISK_ANNOTATION_PROMPT.format(
        source_text=source_text, translated_text=translated_text, target_language=target_language
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        annotations = json.loads(content)
        if isinstance(annotations, list):
            # Add offset and status fields
            used_offsets = set()
            for ann in annotations:
                offset = translated_text.find(ann.get("phrase", ""))
                if offset == -1 or offset in used_offsets:
                    ann["offset"] = -1
                else:
                    used_offsets.add(offset)
                    ann["offset"] = offset
                ann.setdefault("status", "open")
            return annotations
        return []
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Risk annotation parsing failed: {e}")
        return []
```

- [x] **Step 2: Verify pipeline still works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.services.translation import pipeline; print('OK')"`
Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/app/services/translation.py
git commit -m "feat: populate offset and status fields in risk annotations"
```

---

## Task 5: Frontend — Extend Translation Store

**Files:**
- Modify: `frontend/stores/translation-store.ts`

- [x] **Step 1: Extend RiskAnnotation type and add store actions**

Replace the `RiskAnnotation` interface and add new actions:

```typescript
export interface RiskAnnotation {
  phrase: string;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
  status: "open" | "accepted" | "dismissed";
  accepted_suggestion?: string;
  offset?: number;
}
```

Add these methods to `LangResult` interface (no change needed — it already has the right shape).

Add these actions to `TranslationState` interface and implementation:

```typescript
// Add to TranslationState interface
acceptRisk: (lang: string, riskIndex: number, suggestion: string, translatedText: string, annotations: RiskAnnotation[]) => void;
dismissRisk: (lang: string, riskIndex: number, annotations: RiskAnnotation[]) => void;
revertRisk: (lang: string, riskIndex: number, translatedText: string, annotations: RiskAnnotation[]) => void;
setAnnotations: (lang: string, annotations: RiskAnnotation[]) => void;
```

Add implementations inside `create<TranslationState>((set) => ({...}))`:

```typescript
acceptRisk: (lang, riskIndex, suggestion, translatedText, annotations) =>
  set((s) => {
    const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
    const existing = s.results[lang] || defaults;
    return { results: { ...s.results, [lang]: { ...existing, translatedText, riskAnnotations: annotations } } };
  }),
dismissRisk: (lang, riskIndex, annotations) =>
  set((s) => {
    const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
    const existing = s.results[lang] || defaults;
    return { results: { ...s.results, [lang]: { ...existing, riskAnnotations: annotations } } };
  }),
revertRisk: (lang, riskIndex, translatedText, annotations) =>
  set((s) => {
    const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
    const existing = s.results[lang] || defaults;
    return { results: { ...s.results, [lang]: { ...existing, translatedText, riskAnnotations: annotations } } };
  }),
setAnnotations: (lang, annotations) =>
  set((s) => {
    const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
    const existing = s.results[lang] || defaults;
    return { results: { ...s.results, [lang]: { ...existing, riskAnnotations: annotations } } };
  }),
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors related to translation-store.ts

- [x] **Step 3: Commit**

```bash
git add frontend/stores/translation-store.ts
git commit -m "feat: extend RiskAnnotation type with status/accepted_suggestion/offset and add store actions"
```

---

## Task 6: Frontend — Add `put` Method to API Client

**Files:**
- Modify: `frontend/lib/api-client.ts`

- [x] **Step 1: Add `put` method** (未实现 — 所有风险端点用 POST，无需 put 方法)

Add after the `delete` method in `ApiClient`:

```typescript
async put(path: string, body: unknown) {
  const res = await this.request(path, { method: "PUT", body: JSON.stringify(body) });
  return res.json();
}
```

- [x] **Step 2: Commit** (未实现 — 所有风险端点用 POST，无需 put 方法)

```bash
git add frontend/lib/api-client.ts
git commit -m "feat: add put method to ApiClient"
```

---

## Task 7: Frontend — Update RiskDetailList with Suggestion UI & State Actions

**Files:**
- Modify: `frontend/components/workspace/risk-detail-list.tsx`

This is the largest frontend task. The `RiskDetailCard` component needs: suggestion loading/display, accept/dismiss/revert buttons, status-aware rendering. The `RiskDetailList` component needs: accept-all button, summary bar updates.

- [x] **Step 1: Rewrite `risk-detail-list.tsx`**

Replace the full content of `frontend/components/workspace/risk-detail-list.tsx` with:

```tsx
"use client";

import { useState, useCallback } from "react";
import { useTranslationStore, type RiskAnnotation } from "@/stores/translation-store";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Loader2, X, RotateCcw, ChevronDown, ChevronRight, Sparkles } from "lucide-react";

const RISK_BADGE_STYLES: Record<string, { label: string; badgeBg: string; badgeText: string; borderColor: string }> = {
  high: { label: "高风险", badgeBg: "#FEE2E2", badgeText: "#DC2626", borderColor: "#FCA5A5" },
  medium: { label: "中风险", badgeBg: "#FFEDD5", badgeText: "#C2410C", borderColor: "#FDBA74" },
  low: { label: "低风险", badgeBg: "#FEF9C3", badgeText: "#A16207", borderColor: "#FDE68A" },
};

const STATUS_STYLES = {
  open: {},
  accepted: { borderColor: "#86EFAC", bg: "#F0FDF4" },
  dismissed: { borderColor: "#D1D5DB", bg: "#F9FAFB" },
};

interface Suggestion {
  text: string;
  reason: string;
}

function RiskDetailCard({
  annotation,
  index,
  language,
  jobId,
  isHighlighted,
  onHover,
  onLeave,
  onClick,
}: {
  annotation: RiskAnnotation;
  index: number;
  language: string;
  jobId: string | null;
  isHighlighted: boolean;
  onHover: (index: number) => void;
  onLeave: () => void;
  onClick: (index: number) => void;
}) {
  const riskStyle = RISK_BADGE_STYLES[annotation.risk_level] || RISK_BADGE_STYLES.medium;
  const statusStyle = STATUS_STYLES[annotation.status || "open"];
  const status = annotation.status || "open";

  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [suggestionError, setSuggestionError] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(status === "dismissed");

  const acceptRisk = useTranslationStore((s) => s.acceptRisk);
  const dismissRisk = useTranslationStore((s) => s.dismissRisk);
  const revertRisk = useTranslationStore((s) => s.revertRisk);

  const handleViewSuggestions = useCallback(async () => {
    if (!jobId) return;
    setLoadingSuggestions(true);
    setSuggestionError(false);
    try {
      const data = await apiClient.get(`/api/jobs/${jobId}/suggestions?lang=${language}&risk_index=${index}`);
      setSuggestions(data.suggestions || []);
    } catch {
      setSuggestionError(true);
    } finally {
      setLoadingSuggestions(false);
    }
  }, [jobId, language, index]);

  const handleAccept = useCallback(async (suggestion: string) => {
    if (!jobId) return;
    setActionLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/${index}/accept`, { suggestion, lang: language });
      const result = data.results?.find((r: { language: string }) => r.language === language);
      if (result) {
        const updatedAnnotations = (result.risk_annotations || []).map((a: Record<string, unknown>) => ({
          phrase: a.phrase,
          risk_level: a.risk_level,
          risk_type: a.risk_type,
          explanation: a.explanation,
          status: a.status || "open",
          accepted_suggestion: a.accepted_suggestion,
          offset: a.offset,
        }));
        acceptRisk(language, index, suggestion, result.translated_text, updatedAnnotations);
        setSuggestions(null);
      }
    } finally {
      setActionLoading(false);
    }
  }, [jobId, language, index, acceptRisk]);

  const handleDismiss = useCallback(async () => {
    if (!jobId) return;
    setActionLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/${index}/dismiss`, { lang: language });
      const result = data.results?.find((r: { language: string }) => r.language === language);
      if (result) {
        const updatedAnnotations = (result.risk_annotations || []).map((a: Record<string, unknown>) => ({
          phrase: a.phrase,
          risk_level: a.risk_level,
          risk_type: a.risk_type,
          explanation: a.explanation,
          status: a.status || "open",
          accepted_suggestion: a.accepted_suggestion,
          offset: a.offset,
        }));
        dismissRisk(language, index, updatedAnnotations);
      }
    } finally {
      setActionLoading(false);
    }
  }, [jobId, language, index, dismissRisk]);

  const handleRevert = useCallback(async () => {
    if (!jobId) return;
    setActionLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/${index}/revert`, { lang: language });
      const result = data.results?.find((r: { language: string }) => r.language === language);
      if (result) {
        const updatedAnnotations = (result.risk_annotations || []).map((a: Record<string, unknown>) => ({
          phrase: a.phrase,
          risk_level: a.risk_level,
          risk_type: a.risk_type,
          explanation: a.explanation,
          status: a.status || "open",
          accepted_suggestion: a.accepted_suggestion,
          offset: a.offset,
        }));
        revertRisk(language, index, result.translated_text, updatedAnnotations);
      }
    } finally {
      setActionLoading(false);
    }
  }, [jobId, language, index, revertRisk]);

  // Dismissed collapsed view
  if (collapsed && status === "dismissed") {
    return (
      <div
        className="flex items-center gap-2 rounded border border-dashed px-3 py-1.5 text-xs text-gray-400 cursor-pointer"
        style={{ borderColor: "#D1D5DB", background: "#F9FAFB" }}
        onClick={() => setCollapsed(false)}
      >
        <ChevronRight className="h-3 w-3" />
        <span>&ldquo;{annotation.phrase}&rdquo;</span>
        <span>已忽略</span>
      </div>
    );
  }

  return (
    <div
      className="rounded-md border p-2.5 transition-colors duration-150"
      style={{
        background: statusStyle.bg || "white",
        borderColor: isHighlighted ? riskStyle.borderColor : (statusStyle.borderColor || "#E2E8F0"),
        ...(status === "dismissed" ? { borderStyle: "dashed" } : {}),
      }}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={onLeave}
      onClick={() => onClick(index)}
    >
      {/* Header row */}
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        <span
          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
          style={{ background: riskStyle.badgeBg, color: riskStyle.badgeText }}
        >
          {riskStyle.label}
        </span>
        <span className="text-xs font-medium text-[#134E4A]">&ldquo;{annotation.phrase}&rdquo;</span>
        <span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[9px] text-[#475569]">
          {annotation.risk_type}
        </span>

        {/* Status badge + actions */}
        <div className="ml-auto flex items-center gap-1">
          {status === "accepted" && (
            <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-[9px] font-medium text-green-700">
              已采纳：{annotation.phrase} → {annotation.accepted_suggestion}
            </span>
          )}
          {status === "dismissed" && (
            <button
              className="rounded p-0.5 text-gray-400 hover:text-gray-600"
              onClick={(e) => { e.stopPropagation(); setCollapsed(true); }}
              title="折叠"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          )}
          {status === "open" && !actionLoading && (
            <button
              className="rounded p-0.5 text-gray-400 hover:text-gray-600"
              onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
              title="忽略"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          {actionLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-gray-400" />}
        </div>
      </div>

      {/* Explanation */}
      <p className={`text-[11px] leading-relaxed ${status === "dismissed" ? "text-gray-400" : "text-[#64748B]"}`}>
        {annotation.explanation}
      </p>

      {/* Revert button for accepted */}
      {status === "accepted" && (
        <div className="mt-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[10px] px-2"
            onClick={(e) => { e.stopPropagation(); handleRevert(); }}
            disabled={actionLoading}
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            回退
          </Button>
        </div>
      )}

      {/* Dismissed: undo dismiss */}
      {status === "dismissed" && (
        <div className="mt-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[10px] px-2"
            onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
            disabled={actionLoading}
          >
            撤销忽略
          </Button>
        </div>
      )}

      {/* View suggestions button for open */}
      {status === "open" && suggestions === null && !suggestionError && (
        <div className="mt-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[10px] px-2"
            onClick={(e) => { e.stopPropagation(); handleViewSuggestions(); }}
            disabled={loadingSuggestions}
          >
            {loadingSuggestions ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3 mr-1" />
            )}
            查看替代方案
          </Button>
        </div>
      )}

      {/* Suggestion error */}
      {suggestionError && (
        <div className="mt-1.5 flex items-center gap-2">
          <span className="text-[10px] text-red-500">生成建议失败</span>
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[10px] px-2"
            onClick={(e) => { e.stopPropagation(); handleViewSuggestions(); }}
          >
            重试
          </Button>
        </div>
      )}

      {/* Suggestion cards */}
      {suggestions && suggestions.length > 0 && (
        <div className="mt-1.5 flex flex-col gap-1">
          {suggestions.map((s, si) => (
            <div key={si} className="rounded border border-blue-100 bg-blue-50 p-2">
              <p className="text-[11px] font-medium text-blue-900">{s.text}</p>
              <p className="text-[10px] text-blue-600 mt-0.5">{s.reason}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-1 h-5 text-[9px] px-1.5"
                onClick={(e) => { e.stopPropagation(); handleAccept(s.text); }}
                disabled={actionLoading}
              >
                采纳
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* No suggestions found */}
      {suggestions && suggestions.length === 0 && (
        <p className="mt-1.5 text-[10px] text-gray-400">未找到替代方案</p>
      )}
    </div>
  );
}

export function RiskDetailList({ language, jobId }: { language: string; jobId: string | null }) {
  const result = useTranslationStore((s) => s.results[language]);
  const setResult = useTranslationStore((s) => s.setResult);
  const acceptRisk = useTranslationStore((s) => s.acceptRisk);

  const annotations = result?.riskAnnotations ?? [];
  const highlightedIndex = result?.highlightedIndex ?? null;

  const [acceptAllLoading, setAcceptAllLoading] = useState(false);

  const handleHover = useCallback(
    (index: number) => setResult(language, { highlightedIndex: index }),
    [language, setResult]
  );
  const handleLeave = useCallback(
    () => setResult(language, { highlightedIndex: null }),
    [language, setResult]
  );
  const handleClick = useCallback((index: number) => {
    window.dispatchEvent(new CustomEvent("scroll-to-risk-mark", { detail: { language, index } }));
  }, [language]);

  const handleAcceptAll = useCallback(async () => {
    if (!jobId) return;
    setAcceptAllLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/accept-all`, { lang: language });
      const resultData = data.results?.find((r: { language: string }) => r.language === language);
      if (resultData) {
        const updatedAnnotations = (resultData.risk_annotations || []).map((a: Record<string, unknown>) => ({
          phrase: a.phrase,
          risk_level: a.risk_level,
          risk_type: a.risk_type,
          explanation: a.explanation,
          status: a.status || "open",
          accepted_suggestion: a.accepted_suggestion,
          offset: a.offset,
        }));
        acceptRisk(language, -1, "", resultData.translated_text, updatedAnnotations);
      }
    } catch (err) {
      // 409 means already processing
      if (err instanceof Error && err.message.includes("409")) {
        alert("正在批量处理中");
      }
    } finally {
      setAcceptAllLoading(false);
    }
  }, [jobId, language, acceptRisk]);

  if (!annotations.length) return null;

  const openCount = annotations.filter((a) => (a.status || "open") === "open").length;
  const acceptedCount = annotations.filter((a) => a.status === "accepted").length;
  const dismissedCount = annotations.filter((a) => a.status === "dismissed").length;

  return (
    <div className="flex flex-col gap-1.5">
      {/* Summary bar */}
      <div className="flex items-center gap-2 rounded border-l-3 border-terracotta bg-amber-50 px-3 py-2 text-xs text-amber-800">
        <span>
          <span className="font-medium">风险标注：</span>
          {openCount > 0 && (
            <>
              {annotations.length} 处表达在目标受众中存在认知风险
              {annotations.filter((a) => a.risk_level === "high" && (a.status || "open") === "open").length > 0 && (
                <span className="ml-2 text-danger">{annotations.filter((a) => a.risk_level === "high" && (a.status || "open") === "open").length} 高风险</span>
              )}
              {annotations.filter((a) => a.risk_level === "medium" && (a.status || "open") === "open").length > 0 && (
                <span className="ml-2 text-terracotta">{annotations.filter((a) => a.risk_level === "medium" && (a.status || "open") === "open").length} 中风险</span>
              )}
              {annotations.filter((a) => a.risk_level === "low" && (a.status || "open") === "open").length > 0 && (
                <span className="ml-2 text-amber-600">{annotations.filter((a) => a.risk_level === "low" && (a.status || "open") === "open").length} 低风险</span>
              )}
            </>
          )}
          {openCount === 0 && "所有风险已处理"}
          {acceptedCount > 0 && <span className="ml-2 text-green-700">{acceptedCount} 已采纳</span>}
          {dismissedCount > 0 && <span className="ml-2 text-gray-500">{dismissedCount} 已忽略</span>}
        </span>

        {/* Accept all button */}
        {openCount >= 2 && (
          <Button
            variant="outline"
            size="sm"
            className="ml-auto h-6 text-[10px] px-2 border-terracotta text-terracotta hover:bg-terracotta hover:text-white"
            onClick={handleAcceptAll}
            disabled={acceptAllLoading}
          >
            {acceptAllLoading ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3 mr-1" />
            )}
            一键采纳全部建议
          </Button>
        )}
      </div>

      {/* Detail cards */}
      <div className="flex flex-col gap-1.5">
        {annotations.map((a, index) => (
          <RiskDetailCard
            key={index}
            annotation={a}
            index={index}
            language={language}
            jobId={jobId}
            isHighlighted={highlightedIndex === index}
            onHover={handleHover}
            onLeave={handleLeave}
            onClick={handleClick}
          />
        ))}
      </div>
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [x] **Step 3: Commit**

```bash
git add frontend/components/workspace/risk-detail-list.tsx
git commit -m "feat: add suggestion UI, accept/dismiss/revert, and accept-all to RiskDetailList"
```

---

## Task 8: Frontend — Update TranslationResult Mark Styles

**Files:**
- Modify: `frontend/components/workspace/translation-result.tsx`

- [x] **Step 1: Add accepted/dismissed mark styles and update `locateRisks`**

Add additional styles to `RISK_MARK_STYLES` and modify `locateRisks` to handle accepted/dismissed statuses:

```typescript
const RISK_MARK_STYLES: Record<string, { border: string; bg: string; bgHighlight: string }> = {
  high: { border: "#EF4444", bg: "rgba(239,68,68,0.08)", bgHighlight: "rgba(239,68,68,0.20)" },
  medium: { border: "#EA580C", bg: "rgba(234,88,12,0.06)", bgHighlight: "rgba(234,88,12,0.16)" },
  low: { border: "#EAB308", bg: "rgba(234,179,8,0.06)", bgHighlight: "rgba(234,179,8,0.16)" },
  accepted: { border: "#22C55E", bg: "rgba(34,197,94,0.08)", bgHighlight: "rgba(34,197,94,0.20)" },
  dismissed: { border: "#9CA3AF", bg: "rgba(156,163,175,0.06)", bgHighlight: "rgba(156,163,175,0.16)" },
};
```

Update `locateRisks` to use stored offset when available and include status in RiskSpan:

```typescript
function locateRisks(text: string, annotations: RiskAnnotation[]): RiskSpan[] {
  const usedOffsets = new Set<number>();
  return annotations
    .map((a, index) => {
      const status = a.status || "open";
      // For accepted risks, locate the accepted_suggestion instead of the original phrase
      const searchPhrase = status === "accepted" && a.accepted_suggestion ? a.accepted_suggestion : a.phrase;
      const offset = a.offset != null && a.offset >= 0 ? a.offset : text.indexOf(searchPhrase);
      if (offset === -1) return null;
      if (usedOffsets.has(offset)) return null;
      usedOffsets.add(offset);
      return {
        index,
        phrase: searchPhrase,
        offset,
        length: searchPhrase.length,
        risk_level: a.risk_level,
        risk_type: a.risk_type,
        explanation: a.explanation,
        status,
      };
    })
    .filter((s): s is RiskSpan & { status: string } => s !== null)
    .sort((a, b) => a.offset - b.offset);
}
```

Update `RiskSpan` in `translation-store.ts` to include `status`:

```typescript
export interface RiskSpan {
  index: number;
  phrase: string;
  offset: number;
  length: number;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
  status?: "open" | "accepted" | "dismissed";
}
```

In the `<mark>` rendering section of `TranslationResult`, update style selection:

```typescript
// Determine mark style key based on status
const markStyleKey = span.status === "accepted" ? "accepted"
  : span.status === "dismissed" ? "dismissed"
  : span.risk_level;
const style = RISK_MARK_STYLES[markStyleKey] || RISK_MARK_STYLES.medium;
const isHighlighted = highlightedIndex === span.index;

// For dismissed marks, use dashed border
const borderStyle = span.status === "dismissed" ? "3px dashed" : "3px solid";
```

Update the `<mark>` element style to use `borderStyle`:

```tsx
<mark
  ref={(el) => { if (el) markRefs.current.set(span.index, el); }}
  className="cursor-pointer rounded-sm pr-1 pl-1.5 transition-colors duration-150"
  style={{
    borderLeft: `${borderStyle} ${style.border}`,
    background: isHighlighted ? style.bgHighlight : style.bg,
    fontWeight: isHighlighted ? 600 : 500,
    color: "inherit",
  }}
  onMouseEnter={() => handleMarkHover(span.index)}
  onMouseLeave={handleMarkLeave}
>
  {span.phrase}
</mark>
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [x] **Step 3: Commit**

```bash
git add frontend/stores/translation-store.ts frontend/components/workspace/translation-result.tsx
git commit -m "feat: add accepted/dismissed mark styles and update locateRisks for status-aware rendering"
```

---

## Task 9: Frontend — Wire jobId into OutputPanel and RiskDetailList

**Files:**
- Modify: `frontend/components/workspace/output-panel.tsx`

The `RiskDetailList` now needs a `jobId` prop. We need to pass it from `OutputPanel`.

- [x] **Step 1: Add jobId state to OutputPanel**

The `OutputPanel` needs access to the current job ID. Check if `workspace-store` already stores it; if not, add it. Looking at the current code, `useWorkspaceStore` has `languages` but likely no `jobId`.

Check `frontend/stores/workspace-store.ts` for existing `jobId` field. If it exists, use it. If not, add it.

In `output-panel.tsx`, add job ID retrieval and pass to `RiskDetailList`:

```tsx
const jobId = useWorkspaceStore((s) => s.jobId);
```

Update `RiskDetailList` usage:

```tsx
<RiskDetailList language={activeLang} jobId={jobId} />
```

If `workspace-store.ts` doesn't have `jobId`, add:

```typescript
// In workspace-store state
jobId: string | null;

// In workspace-store actions
setJobId: (id: string | null) => void;
```

And ensure the job creation flow (in `InputPanel` or wherever `POST /api/jobs` is called) stores the returned job ID into `workspace-store.setJobId(...)`.

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [x] **Step 3: Commit**

```bash
git add frontend/stores/workspace-store.ts frontend/components/workspace/output-panel.tsx
git commit -m "feat: wire jobId into OutputPanel and RiskDetailList for API calls"
```

---

## Task 10: End-to-End Smoke Test

**Files:** None (manual testing)

- [x] **Step 1: Start backend and Celery**

Run backend: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`

Run Celery: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info --pool=solo`

- [x] **Step 2: Start frontend**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npm run dev`

- [x] **Step 3: Submit a translation job and verify risk annotations appear**

Navigate to `http://localhost:3000/workspace`, submit a translation with risk-prone text, wait for completion.

- [x] **Step 4: Test "查看替代方案" button**

Click "查看替代方案" on a risk card → verify suggestions appear with text, reason, and "采纳" button.

- [x] **Step 5: Test "采纳" action**

Click "采纳" on a suggestion → verify:
- Translation text updates with the suggestion
- Risk card shows "已采纳：xxx → yyy" with "回退" button
- Inline mark turns green

- [x] **Step 6: Test "回退" action**

Click "回退" → verify original text is restored, risk returns to "open" state.

- [x] **Step 7: Test "忽略" action**

Click the X button on a risk card → verify it collapses to one-line gray text. Click to expand → verify "撤销忽略" button.

- [x] **Step 8: Test "一键采纳全部" button**

Submit a job with ≥2 risks → verify "一键采纳全部建议" button appears → click → verify all risks transition to "accepted" one by one.

- [x] **Step 9: Commit any fixes**

If any fixes were needed during smoke test, commit them:
```bash
git add -A && git commit -m "fix: address issues found during smoke test"
```
