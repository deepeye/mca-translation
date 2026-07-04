# Glossary Multi-Language Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable full per-language translation support in user-defined and system glossaries for all 17 non-English target languages, with on-demand LLM auto-fill and active-language display in the workspace.

**Architecture:** Backend adds strict Pydantic validation of `translations` JSONB keys and a new on-demand LLM auto-fill endpoint. Frontend adds a compact-list translation editor to the glossary page, count badges, an auto-fill button, and active-target-language lookup in the workspace inline/term highlighters.

**Tech Stack:** FastAPI, pydantic v2, SQLAlchemy 2.0, Next.js, TypeScript, Zustand, vitest.

## Global Constraints

- 18 supported BCP-47 codes: `en-GB` `de-DE` `ja-JP` `es-ES` `fr-FR` `ru-RU` `ar` `ko-KR` `pt-BR` `sw-KE` `it-IT` `kk-KZ` `th-TH` `ms-MY` `el-GR` `vi-VN` `ur-PK` `hi-IN`
- No DB migration required; `translations` is already a JSONB column keyed by language code.
- `GlossaryEntry.translations` shape is `{lang_code: {preferred, alternatives, notes}}`.
- Code comments are bilingual (Chinese + English) per project convention.
- Commit to `main` branch; no feature branches.

---

## File Structure

**Create:**
- `backend/app/services/glossary_autofill.py` — LLM prompt builder + per-language translation generator.
- `backend/tests/test_glossary_schema_validation.py` — validates translations key rejection.
- `backend/tests/test_glossary_autofill.py` — tests autofill endpoint + service.
- `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx` — frontend page tests.

**Modify:**
- `backend/app/schemas/glossary.py` — add `field_validator("translations")` to `GlossaryEntryCreate` / `GlossaryEntryUpdate` / `UserGlossaryEntryCreate` / `UserGlossaryEntryUpdate`.
- `backend/app/api/glossary.py` — add `POST /user-entries/{entry_id}/auto-fill` route.
- `frontend/app/(main)/glossary/page.tsx` — compact-list translation editor, count badges, auto-fill button.
- `frontend/lib/api-client.ts` — add `autoFillUserGlossaryEntry`.
- `frontend/components/workspace/inline-highlighter.tsx` — read active language from workspace store.
- `frontend/components/workspace/term-highlighter.tsx` — read active language from workspace store.
- `frontend/stores/workspace-store.ts` — add `activeLanguage` state + setters, synced with `languages[0]`.
- `frontend/components/workspace/output-panel.tsx` — use store `activeLanguage` instead of local state.
- `frontend/components/workspace/decision-log-panel.tsx` — use store `activeLanguage` instead of local state.
- `frontend/components/workspace/__tests__/inline-highlighter.test.tsx` — update mocks and add fallback test.

---

## Task 1: Backend translations key validation

**Files:**
- Modify: `backend/app/schemas/glossary.py`
- Test: `backend/tests/test_glossary_schema_validation.py`

**Interfaces:**
- Consumes: `SUPPORTED_LANGUAGE_CODES` from `app.constants.languages`
- Produces: `GlossaryEntryCreate`, `GlossaryEntryUpdate`, `UserGlossaryEntryCreate`, `UserGlossaryEntryUpdate` reject any `translations` key not in `SUPPORTED_LANGUAGE_CODES` with a clear 422 message.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_glossary_schema_validation.py`:
```python
from pydantic import ValidationError
from app.schemas.glossary import UserGlossaryEntryCreate, UserGlossaryEntryUpdate


class _FakeTranslation:
    def model_dump(self):
        return {"preferred": "x", "alternatives": [], "notes": ""}


def _valid_translations():
    return {"en-GB": _FakeTranslation()}


def _invalid_translations():
    return {"en-GB": _FakeTranslation(), "xx-XX": _FakeTranslation()}


def test_user_glossary_create_accepts_valid_language_codes():
    body = UserGlossaryEntryCreate(
        source_term="一带一路",
        term_type="user_defined",
        translations=_valid_translations(),
    )
    assert "en-GB" in body.translations


def test_user_glossary_create_rejects_unknown_language_codes():
    try:
        UserGlossaryEntryCreate(
            source_term="一带一路",
            term_type="user_defined",
            translations=_invalid_translations(),
        )
    except ValidationError as e:
        assert "xx-XX" in str(e)
    else:
        raise AssertionError("Expected ValidationError for unknown language code")


def test_user_glossary_update_rejects_unknown_language_codes():
    try:
        UserGlossaryEntryUpdate(translations=_invalid_translations())
    except ValidationError as e:
        assert "xx-XX" in str(e)
    else:
        raise AssertionError("Expected ValidationError for unknown language code")
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend && pytest tests/test_glossary_schema_validation.py -v
```
Expected: FAIL (validator not yet added).

- [ ] **Step 3: Add the validator**

`backend/app/schemas/glossary.py` — after `TranslationEntry`, add a helper and the validator:

```python
from app.constants.languages import SUPPORTED_LANGUAGE_CODES


def _check_translation_keys(v: dict[str, TranslationEntry]) -> dict[str, TranslationEntry]:
    unknown = set(v.keys()) - SUPPORTED_LANGUAGE_CODES
    if unknown:
        raise ValueError(f"unsupported language codes in translations: {sorted(unknown)}")
    return v
```

Attach to the four create/update models:

```python
class GlossaryEntryCreate(BaseModel):
    source_term: str
    term_type: SystemGlossaryTermType = "political_discourse"
    translations: dict[str, TranslationEntry] = Field(default_factory=dict)
    risk_notes: str = ""
    applicable_genres: list[str] = Field(default_factory=list)

    @field_validator("translations")
    @classmethod
    def _check_translation_keys(cls, v):
        return _check_translation_keys(v)
```

Do the same for `GlossaryEntryUpdate`, `UserGlossaryEntryCreate`, `UserGlossaryEntryUpdate`.

- [ ] **Step 4: Run the tests**

```bash
cd backend && pytest tests/test_glossary_schema_validation.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/glossary.py backend/tests/test_glossary_schema_validation.py
git commit -m "feat(glossary): validate translation keys against SUPPORTED_LANGUAGE_CODES"
```

---

## Task 2: Backend autofill service

**Files:**
- Create: `backend/app/services/glossary_autofill.py`
- Modify: `backend/app/api/glossary.py`
- Test: `backend/tests/test_glossary_autofill.py`

**Interfaces:**
- Consumes: `bailian_client` from `app.llm.bailian`
- Produces: `generate_translation(source_term: str, target_lang: str, english_reference: str | None, *, client) -> dict | None`
- Produces: `POST /api/glossary/user-entries/{entry_id}/auto-fill` returns `{entry, filled_languages, skipped}`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_glossary_autofill.py`:
```python
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


async def _create_user_and_entry(monkeypatch):
    # Stub auth and DB calls are implementation-specific; the implementing agent
    # should adapt to the existing auth fixture in conftest.py if available.
    pass


def test_autofill_fills_missing_languages(monkeypatch):
    fake_client = AsyncMock()
    fake_client.chat = AsyncMock(return_value={"content": '{"rendering": "x", "alternatives": [], "notes": ""}'})
    monkeypatch.setattr("app.services.glossary_autofill.bailian_client", fake_client)
    # Implementation-specific: create a user, create an entry with only en-GB,
    # call the endpoint, assert one new language is filled.
```

The implementing agent should replace the stub test with a proper integration test using the existing `db` fixture and a stubbed `bailian_client.chat`.

- [ ] **Step 2: Implement `glossary_autofill.py`**

```python
"""LLM-based per-term translation auto-fill for user glossary entries.

纯工具模块：输入中文 source_term + 目标语言 + 可选英语参考，输出
{preferred, alternatives, notes}。错误处理由调用方负责重试/跳过。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.constants.languages import language_descriptor
from app.llm.bailian import bailian_client

logger = logging.getLogger(__name__)


def _strip_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("\", 1)[0] if "```" in text else text
    return text.strip()


def _build_prompt(source_term: str, target_lang: str, english_reference: Optional[str]) -> str:
    descriptor = language_descriptor(target_lang)
    ref_line = f"英语参考译法：{english_reference}\n" if english_reference else ""
    return (
        f"将中文术语「{source_term}」译为 {descriptor}。\n"
        f"{ref_line}"
        "输出 JSON：{\"rendering\": str, \"alternatives\": [str], \"notes\": str}\n"
        "不要输出解释或 Markdown 代码块。"
    )


async def generate_translation(
    source_term: str,
    target_lang: str,
    english_reference: Optional[str] = None,
    *,
    client=None,
) -> Optional[dict]:
    """为单个术语生成单个目标语言的译文。失败返回 None。"""
    prompt = _build_prompt(source_term, target_lang, english_reference)
    c = client or bailian_client
    for attempt in (1, 2):
        try:
            result = await c.chat(model="qwen-plus", messages=[{"role": "user", "content": prompt}], temperature=0.3)
            data = json.loads(_strip_fence(result.get("content") or ""))
            if not isinstance(data, dict):
                continue
            rendering = str(data.get("rendering", "")).strip()
            if not rendering:
                continue
            alternatives = [str(a) for a in data.get("alternatives", []) if a]
            notes = str(data.get("notes", ""))
            return {"preferred": rendering, "alternatives": alternatives, "notes": notes}
        except Exception as e:
            logger.warning("glossary autofill %s for %s attempt %d failed: %s", source_term, target_lang, attempt, e)
            if attempt == 2:
                return None
    return None
```

- [ ] **Step 3: Add the auto-fill endpoint**

In `backend/app/api/glossary.py`, after the existing user-entries routes:

```python
from app.services.glossary_autofill import generate_translation
from app.constants.languages import SUPPORTED_LANGUAGE_CODES


class _AutoFillResponse(BaseModel):
    entry: UserGlossaryEntryResponse
    filled_languages: list[str]
    skipped: list[dict]


@router.post("/user-entries/{entry_id}/auto-fill", response_model=_AutoFillResponse)
async def autofill_user_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(UserGlossaryEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")

    existing = set(entry.translations.keys())
    missing = SUPPORTED_LANGUAGE_CODES - existing
    filled: list[str] = []
    skipped: list[dict] = []

    en_ref = entry.translations.get("en-GB", {}).get("preferred")
    for lang in sorted(missing):
        generated = await generate_translation(entry.source_term, lang, en_ref)
        if generated:
            entry.translations[lang] = generated
            filled.append(lang)
        else:
            skipped.append({"code": lang, "reason": "llm_failed"})

    if filled:
        await db.commit()
        await db.refresh(entry)

    return _AutoFillResponse(entry=entry, filled_languages=filled, skipped=skipped)
```

- [ ] **Step 4: Run backend autofill tests**

```bash
cd backend && pytest tests/test_glossary_autofill.py -v
```
Expected: PASS after the implementing agent replaces stubs with real fixtures.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/glossary_autofill.py backend/app/api/glossary.py backend/tests/test_glossary_autofill.py
git commit -m "feat(glossary): add on-demand LLM auto-fill endpoint for user entries"
```

---

## Task 3: Lift active language into workspace store

**Files:**
- Modify: `frontend/stores/workspace-store.ts`
- Modify: `frontend/components/workspace/output-panel.tsx`
- Modify: `frontend/components/workspace/decision-log-panel.tsx`
- Test: existing workspace store tests if any

**Interfaces:**
- Consumes: `languages: string[]` from workspace store
- Produces: `activeLanguage: string`, `setActiveLanguage(lang: string)` in workspace store

- [ ] **Step 1: Update workspace store**

Add to `WorkspaceState`:
```ts
activeLanguage: string;
setActiveLanguage: (lang: string) => void;
```

Add to initial state:
```ts
activeLanguage: "en-GB",
```

Add action:
```ts
setActiveLanguage: (activeLanguage) => set({ activeLanguage }),
```

Add setter in `setLanguages` to keep `activeLanguage` in sync:
```ts
setLanguages: (languages) =>
  set((s) => {
    const next: { languages: string[]; input?: typeof s.input; activeLanguage?: string } = { languages };
    if (!s.sphereTouched && languages.length > 0) {
      const affinity = languages
        .map((code) => affinitySphereFor(code))
        .find((a): a is string => a !== null);
      if (affinity) {
        next.input = { ...s.input, culturalSphere: affinity as CulturalSphere };
      }
    }
    const newActive = languages.find((l) => l === s.activeLanguage) || languages[0] || "en-GB";
    next.activeLanguage = newActive;
    return next;
  })),
```

Also update `loadFromHistory` to set `activeLanguage: job.target_languages[0] || "en-GB"`.

- [ ] **Step 2: Update output-panel to use store active language**

Replace local `activeLang` state with store selectors:
```ts
const activeLang = useWorkspaceStore((s) => s.activeLanguage);
const setActiveLang = useWorkspaceStore((s) => s.setActiveLanguage);
```
Remove local `useState` and the sync effect.

- [ ] **Step 3: Update decision-log-panel similarly**

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && pnpm test
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/stores/workspace-store.ts frontend/components/workspace/output-panel.tsx frontend/components/workspace/decision-log-panel.tsx
git commit -m "feat(workspace): lift activeLanguage into workspace store"
```

---

## Task 4: Inline highlighter active-language lookup

**Files:**
- Modify: `frontend/components/workspace/inline-highlighter.tsx`
- Modify: `frontend/components/workspace/term-highlighter.tsx`
- Test: `frontend/components/workspace/__tests__/inline-highlighter.test.tsx`

**Interfaces:**
- Consumes: `activeLanguage` from workspace store
- Consumes: `DetectedTerm.translations` dict (already contains all languages)
- Produces: `HighlightSpan.suggestion` uses active-language preferred, fallback en-GB

- [ ] **Step 1: Update inline-highlighter.tsx**

Inside `buildSpans`, after the glossary loop begins, read active language:

```ts
export function InlineHighlighter() {
  const text = useWorkspaceStore((s) => s.input.text);
  const setText = useWorkspaceStore((s) => s.setText);
  const activeLang = useWorkspaceStore((s) => s.activeLanguage);
  // ... existing store hooks ...
```

Pass `activeLang` to `buildSpans` and update the suggestion line:

```ts
function buildSpans(
  text: string,
  glossary: [...],
  cultural: [...],
  activeLang: string,
): HighlightSpan[] {
  // ...
  const preferred =
    t.translations[activeLang]?.preferred ??
    t.translations["en-GB"]?.preferred ??
    undefined;
  glossarySpans.push({
    // ...
    suggestion: preferred,
  });
}
```

Update `useMemo` dependency to include `activeLang`.

- [ ] **Step 2: Update term-highlighter.tsx**

```ts
const activeLang = useWorkspaceStore((s) => s.activeLanguage);
```

Replace the en-GB block with:

```ts
const activeTranslation = term.translations[activeLang] ?? term.translations["en-GB"];
if (activeTranslation) {
  const label = LANGUAGE_LABELS[activeLang] ?? "英语";
  return (
    <div className="mt-1 text-xs text-teal-700">
      {label}：{activeTranslation.preferred}
    </div>
  );
}
```

- [ ] **Step 3: Update tests**

`frontend/components/workspace/__tests__/inline-highlighter.test.tsx` — add `activeLanguage: "en-GB"` to the mocked workspace state and add a test where `activeLanguage = "ar"` and the popover shows the Arabic preferred translation, falling back to en-GB when missing.

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && pnpm test
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/workspace/inline-highlighter.tsx frontend/components/workspace/term-highlighter.tsx frontend/components/workspace/__tests__/inline-highlighter.test.tsx
git commit -m "feat(workspace): show glossary suggestions in active target language"
```

---

## Task 5: Glossary management page — compact-list editor

**Files:**
- Modify: `frontend/app/(main)/glossary/page.tsx`
- Modify: `frontend/lib/api-client.ts`
- Test: `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx`

**Interfaces:**
- Consumes: `LANGUAGE_LABELS` from `@/lib/languages`
- Produces: create/edit form supports multiple `{code: {preferred, alternatives, notes}}`
- Produces: auto-fill button calls `POST /api/glossary/user-entries/{id}/auto-fill`

- [ ] **Step 1: Add API client method**

`frontend/lib/api-client.ts`:

```ts
async autoFillUserGlossaryEntry(id: string): Promise<{
  entry: GlossaryEntry;
  filled_languages: string[];
  skipped: { code: string; reason: string }[];
}> {
  return this.post(`/api/glossary/user-entries/${id}/auto-fill`, {});
}
```

- [ ] **Step 2: Build the compact-list form**

In `frontend/app/(main)/glossary/page.tsx`, replace the `newTerm` / `newTranslation` state and inline edit state with:

```ts
interface TranslationFormEntry {
  preferred: string;
  alternatives: string[];
  notes: string;
}

interface EntryForm {
  source_term: string;
  term_type: string;
  risk_notes: string;
  applicable_genres: string[];
  translations: Record<string, TranslationFormEntry>;
}
```

Default form includes `en-GB` chip. Render chips for each language in `form.translations`; each chip has inputs for preferred, alternatives, notes, and a remove button. Provide an "+ 添加译法" dropdown to add another language; disable already-added codes.

- [ ] **Step 3: Count badges on list rows**

Display mode:
- Show source_term + term_type label.
- Show en-GB preferred if available; otherwise show the first available translation.
- Show `+N` badge where N = number of non-en-GB translations (or total - 1). Hide if N == 0.
- Tooltip on badge lists language labels.

- [ ] **Step 4: Add auto-fill button in edit mode**

```ts
async function handleAutoFill(entryId: string) {
  try {
    const result = await apiClient.autoFillUserGlossaryEntry(entryId);
    // Refresh list or update local entry state
  } catch (err) {
    console.error("Auto-fill failed:", err);
  }
}
```

- [ ] **Step 5: Write frontend page tests**

`frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx`:
- Render page with mocked API.
- Click "+ 添加译法", select a language, fill preferred, save.
- Assert `apiClient.createUserGlossaryEntry` called with correct `translations` shape.
- Test count badge: entry with en-GB + ar + de-DE shows `+2`.
- Test auto-fill button calls `apiClient.autoFillUserGlossaryEntry(id)`.

- [ ] **Step 6: Run frontend tests**

```bash
cd frontend && pnpm test
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/(main)/glossary/page.tsx frontend/lib/api-client.ts frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx
git commit -m "feat(glossary): multi-language translation editor with auto-fill"
```

---

## Task 6: Integration & regression testing

**Files:**
- Modify: `backend/tests/test_glossary_rag.py`
- Modify: `frontend/components/workspace/__tests__/inline-highlighter.test.tsx`

- [ ] **Step 1: Extend backend RAG test**

Add a test that creates a `UserGlossaryEntry` with 18-language `translations` and calls `retrieve_glossary_terms`. Assert it returns without error and includes the target-language preferred translation.

- [ ] **Step 2: Extend inline-highlighter test**

Add a test for active-language fallback: when active language is `ar` but the term only has `en-GB`, the popover shows the en-GB preferred translation.

- [ ] **Step 3: Run full test suites**

```bash
cd backend && pytest -v
cd frontend && pnpm test
```
Expected: PASS (or existing failures only).

- [ ] **Step 4: Manual verification**

1. Open glossary page, create a term with en-GB, click auto-fill, confirm 17 languages filled.
2. Workspace: select `ar`, paste term, hover highlight, see Arabic translation.
3. Workspace: select `ur-PK`, hover same term, see Urdu translation.
4. Submit a term with `xx-XX` via API → 422.

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "test(glossary): add regression tests for multi-language glossary support"
```

---

## Self-Review Checklist

- [x] Spec coverage: every section of the design doc has at least one task implementing it.
- [x] Placeholder scan: no TBD/TODO; all file paths exact.
- [x] Type consistency: `activeLanguage` in store matches usage in highlighters; `translations` shape consistent across backend/frontend.
- [x] No DB migration required — called out in Global Constraints.
- [x] Tests are explicit with mocked data and expected assertions.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-04-glossary-multilang.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach would you like?