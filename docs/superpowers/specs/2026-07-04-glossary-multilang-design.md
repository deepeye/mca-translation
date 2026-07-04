# Glossary Multi-Language Support — Design

**Date:** 2026-07-04
**Status:** Approved for implementation
**Scope:** System glossary + custom/user glossary, all 17 non-`en-GB` target languages

## Background

The glossary module (术语库) supports two flavors:

- **System glossary** — 15 hardcoded Chinese political/cultural terms in `backend/app/services/hardcoded_glossary.py`, persisted to the `glossary_entries` table on seed.
- **User glossary** — per-user CRUD against the `user_glossary_entries` table, surfaced through `/api/glossary/user-entries`.

Both store translations in a single `translations` JSONB column with shape `{lang_code: {preferred, alternatives, notes}}`. The central language list lives in `backend/app/constants/languages.py` (18 codes; mirrored manually in `frontend/lib/languages.ts`).

**Current limitation:** The glossary management page (`frontend/app/(main)/glossary/page.tsx`) and the workspace inline-highlighter (`frontend/components/workspace/inline-highlighter.tsx`) hard-code `"en-GB"` as the only language shown in forms and popovers. There is no UI for adding translations in the other 17 languages, and no schema validation ensuring JSONB keys are valid BCP-47 codes. The user request is to extend the glossary — both system and custom — to support all 17 non-English target languages.

**What's already in place (no change needed):**
- The `translations` JSONB column accepts any BCP-47 code with no schema change.
- The 15 hardcoded system terms already have LLM-generated translations for the 13 newly-added languages (see `backend/app/data/glossary_translations_generated.json`), produced by `backend/app/generate_glossary_translations.py` at seed time.
- Backend retrieval (`glossary_rag.retrieve_glossary_terms`), the hardcoded fallback path (`hardcoded_glossary.find_terms_in_text` + `format_glossary_block`), and translation-pipeline prompt injection (`_format_rag_glossary_block` at `backend/app/services/translation.py:266`) already read `translations[target_language]` correctly. The bug is only in the UI and in schema-level validation.

## Goals

1. Users can add and edit per-language translations on user-defined glossary terms through the existing management page, for all 18 supported languages.
2. Users can request on-demand LLM auto-fill of missing languages for a user-defined term via a dedicated endpoint (one click, no surprise token spend on every save).
3. The workspace inline-highlighter popover shows the translation in the user's currently-selected target language (with `en-GB` fallback), not always English.
4. The backend strictly validates that translation JSONB keys are valid `SUPPORTED_LANGUAGE_CODES`, returning 422 for unknown codes.

## Non-Goals

- No DB migration.
- No change to the translation pipeline's LLM prompts or decision-log shape.
- No batch auto-fill across multiple terms in one request.
- No LLM auto-fill for the system glossary's hardcoded terms — already done at seed time.
- No change to RTL handling for the workspace output area (already handled at export + display layer per recent commits).
- No content-level validation of `translations[lang].preferred` (e.g. we don't reject empty strings; reads already filter them out where appropriate).

## Design

### 1. Backend

#### 1.1 Schema validation — strict BCP-47 keys

**File:** `backend/app/schemas/glossary.py`

Add a `field_validator("translations")` to `GlossaryEntryCreate` that rejects any key not in `SUPPORTED_LANGUAGE_CODES`. The validator runs on the request Pydantic layer before the route handler, so unknown codes produce a 422 with a clear message listing the bad keys.

Apply the same validation to the PUT path by reusing `GlossaryEntryCreate` for the update body (or a dedicated `GlossaryEntryUpdate` that inherits the validator).

`TranslationEntry` (the inner `{preferred, alternatives, notes}` shape) is unchanged.

#### 1.2 New endpoint — on-demand auto-fill

**File:** `backend/app/api/glossary.py` (route), `backend/app/services/glossary_autofill.py` (helper module)

```
POST /api/glossary/user-entries/{entry_id}/auto-fill
Auth: required
Ownership: scoped to current user (404 if not owned)
```

Behavior:
1. Load the user-glossary entry by id; 404 if missing or not owned.
2. Compute missing languages = `{code for code in SUPPORTED_LANGUAGE_CODES if code not in entry.translations}`.
3. For each missing language, call `glossary_autofill.generate_translation(source_term, target_lang, english_reference=entry.translations["en-GB"].preferred if "en-GB" in entry.translations else None)`.
4. Per-language retries: 1 retry on JSON parse error or network error; skip that language on second failure.
5. Merge generated translations into `entry.translations` (new keys only — existing values never overwritten, including by partial LLM output).
6. Persist; return `{entry: <updated>, filled_languages: [...], skipped: [{code, reason}, ...]}`.
7. No re-embedding — auto-fill only touches translations.

**LLM client:** reuse `bailian_client` (model `qwen-plus`, temperature 0.3, timeout 180s per recent bailian.py config).

**Prompt shape:** modeled on `_build_prompt()` in `backend/app/generate_glossary_translations.py`. Per-language, one term at a time (not the batch loop). Output JSON `{rendering, alternatives, notes}`.

**Why a separate endpoint instead of inlining into POST/PUT:**
- Lets users opt in to LLM spend (some want manual control).
- Keeps POST/PUT synchronous and fast.
- Keeps the LLM call outside the validation path — no surprise 30s timeouts on form save.
- Mirrors the existing pattern: `generate_glossary_translations.py` already does the same thing for system terms as a one-shot script; this endpoint is the on-demand version for user terms.

#### 1.3 No change to existing endpoints

`POST /api/glossary/user-entries` and `PUT /user-entries/{id}` continue to accept full `translations` dicts (now strictly validated). The auto-fill endpoint is purely additive.

### 2. Frontend — glossary management page

**File:** `frontend/app/(main)/glossary/page.tsx` (currently 313 lines, single file).

#### 2.1 Compact-list translation editor

Replaces the current "中文术语 + 英语译法" create form and the en-GB-only edit form.

```
+-----------------------------------------+
| 中文术语: [___________________]         |
| 术语类型: [political_discourse ▾]       |
| 风险备注: [___________________]         |
| 适用文体: ☐ 时政新闻 ☐ 学术 ...         |
|                                         |
| 译法列表:                               |
|   [en-GB ×]   英语(英)                  |
|     preferred:    [______________]      |
|     alternatives: [+ 添加备选]           |
|     notes:        [______________]      |
|   [de-DE ×]   德语                       |
|     preferred:    [______________]      |
|     alternatives: [+ 添加备选]           |
|     notes:        [______________]      |
|                                         |
|   + 添加译法  语言: [下拉选择 ▾]         |
|                                         |
| [✨ 一键补齐其余译法 (LLM)]  [保存]      |
+-----------------------------------------+
```

Rules:
- `en-GB` chip is added by default when the form opens.
- Language dropdown lists all 18 codes; disabled for languages already added (shown with a checkmark).
- Removing a language removes that entry from local form state; only remaining entries are sent on save.
- Save is enabled when at least one language has non-empty `preferred`.
- Each language's chip uses Chinese label from `LANGUAGE_LABELS[code]`.

#### 2.2 Auto-fill button

Label: `✨ 一键补齐其余译法 (LLM)`.

- Disabled when `source_term` is empty.
- Disabled before first save (no entry ID yet) — shown with tooltip "保存后可用".
- On click: POST `/api/glossary/user-entries/{id}/auto-fill` → re-render form with new chips.
- Status toast: "已补齐 5 种译法 (ru-RU, ar, ko-KR, pt-BR, fr-FR) · 跳过 2 种 (网络超时)".
- Edit path also has the button. Backend only fills missing keys; re-running is harmless.

#### 2.3 List rows — en-GB + count badge

User-defined list and system glossary display both show:

```
+--------------------------------------------------------------+
| 中华人民共和国                       [+3]                  |
| 政治话语 · en-GB: People's Republic of China              |
|                                  [编辑] [删除]               |
+--------------------------------------------------------------+
```

- Primary row: source_term + term_type + en-GB preferred (when present).
- `+N` badge: count of OTHER filled translations (excluding en-GB). Hidden when N=0.
- Badge tooltip lists the language codes.
- If `en-GB` is missing, primary row falls back to first filled language's `preferred` + label, so rows are never blank.
- System glossary: same display, no edit/delete actions (still read-only).

#### 2.4 Unchanged

- Search/filter (`q=` param).
- Pagination (10/page on user list).
- The `/detect` and `/detect-cultural` flows.

### 3. Frontend — workspace inline highlighter

**Files touched:**
- `frontend/components/workspace/inline-highlighter.tsx` (line 84)
- `frontend/components/workspace/term-highlighter.tsx` (line 79)
- `frontend/stores/glossary-store.ts` — no shape change; `DetectedTerm.translations` already stores the full dict.

**Behavior change:**
1. Both components read the workspace store's active target language (store name verified at implementation time; expected to be `useWorkspaceStore` with a field like `activeTargetLanguage`).
2. Lookup order:
   - `term.translations[activeLang]?.preferred`
   - fallback `term.translations["en-GB"]?.preferred`
   - fallback `undefined` (current behavior)
3. `term-highlighter.tsx` shows the active target language's translation, labeled with `LANGUAGE_LABELS[code]`. Falls back to en-GB only when activeLang is unavailable for this term.

**RTL handling:** Popover chrome stays LTR. The text content (Arabic/Urdu script) renders naturally RTL via the browser — no `dir="rtl"` attribute on the popover. (Implementation may add `dir="auto"` on the text element if measured to improve legibility, but this is optional and out of scope unless we find a visual bug during testing.)

### 4. Testing

**Backend (`backend/tests/`):**

| File | Type | Coverage |
|---|---|---|
| `test_glossary_schema_validation.py` | new | POST/PUT `/user-entries` with unknown language codes → 422; with valid 18 codes → 200 |
| `test_glossary_autofill.py` | new | Stub `bailian_client`; assert: fills only missing; never overwrites; ownership-scoped (other user's entry → 404); `filled_languages` + `skipped` correct; retry on JSON parse error |
| `test_glossary_rag.py` | extend | Regression guard: 18-language `translations` retrieval still works |
| `test_languages_constants.py` | unchanged | 18-code coverage already in place |
| `test_glossary_api.py` | unchanged | Existing detect endpoint test stays |

**Frontend (`frontend/components/workspace/__tests__/` and `frontend/app/(main)/glossary/__tests__/` if absent):**

| File | Type | Coverage |
|---|---|---|
| `inline-highlighter.test.tsx` | update | Mock workspace store `activeTargetLanguage`; assert new lookup; assert en-GB fallback when activeLang missing |
| `term-highlighter.test.tsx` | update (if exists) | Same as above |
| `glossary-page.test.tsx` | new | Render page, mock API; assert compact-list form, count badge on rows, auto-fill button calls new endpoint |

### 5. Manual verification checklist

1. Create a new user term with source_term + en-GB preferred → save → click auto-fill → confirm backend filled 17 (or fewer on failure) languages; reopen edit form and verify all chips appear.
2. Workspace: paste "一带一路" into input, pick `ar` as target → popover shows Arabic `preferred`, not English. Switch target to `ur-PK` → popover switches to Urdu.
3. Workspace: target = `en-GB` → popover still shows en-GB (current behavior).
4. POST a user term with `xx-XX` → 422.
5. Edit a user term, remove all languages except `de-DE`, save → list row shows `de-DE` as primary; badge `+0`.
6. Backend regression: `test_glossary_rag.py`, `test_translation_glossary.py`, `test_hardcoded_glossary.py` pass without modification.

## Files Changed

**Backend (4 files):**
- `backend/app/schemas/glossary.py` — add `field_validator` on `translations` keys
- `backend/app/api/glossary.py` — add `/user-entries/{id}/auto-fill` route
- `backend/app/services/glossary_autofill.py` — new helper module (prompt builder + LLM call)
- `backend/app/services/glossary_autofill.py` tests via `backend/tests/test_glossary_autofill.py` — new
- `backend/tests/test_glossary_schema_validation.py` — new
- `backend/tests/test_glossary_rag.py` — extend

**Frontend (3 files + tests):**
- `frontend/app/(main)/glossary/page.tsx` — compact-list form, count badge, auto-fill button
- `frontend/lib/api-client.ts` — add `autoFillUserGlossaryEntry(id)` method
- `frontend/components/workspace/inline-highlighter.tsx` — read active target language
- `frontend/components/workspace/term-highlighter.tsx` — read active target language
- `frontend/components/workspace/__tests__/inline-highlighter.test.tsx` — update
- `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx` — new (or extend existing)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Existing user terms with `translations` containing only `en-GB` fail schema validation on next PUT | Existing 1-key entries are all valid; the validator only rejects unknown codes, not missing ones |
| Auto-fill endpoint times out under network instability | Per-language retry (1x), then `skipped`; existing entries preserved |
| Inline-highlighter reads wrong store key for active target language | Verify store name at implementation; integration test covers fallback |
| Glossary page becomes long with 17 chips per term | Sticky header on the form; chip list scrolls inside the form panel |
| LLM produces empty `preferred` for some language | Backend filters out empty renderings before merging (same as existing `generate_glossary_translations.py`); `filled_languages` only lists codes actually merged |