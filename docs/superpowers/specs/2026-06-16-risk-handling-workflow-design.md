# Risk Handling Workflow Design

## Overview

After translation results display risk annotations, users need a workflow to act on them. This design adds suggestion generation, accept/dismiss/revert actions, and a "accept all" batch operation.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Interaction mode | Hybrid: per-risk + accept-all | Users want granular control but also a fast path |
| Suggestion timing | On-demand, per LLM call per click | Saves tokens, simple to implement, 1-3 risks typical |
| Suggestion persistence | Not persisted, regenerated each time | Avoids cache complexity, suggestions are cheap to generate |
| Post-accept state | "Accepted" visual + revert action | Users need to see what changed and undo if needed |
| Replacement method | Offset-based precise replacement | Avoids ambiguity when phrase appears multiple times |

## Section 1: Data Model Changes

### Backend `RiskAnnotation` extension

```python
# Existing fields
phrase: str
risk_level: "low" | "medium" | "high"
risk_type: str
explanation: str

# New fields
status: "open" | "accepted" | "dismissed"  # default "open"
accepted_suggestion: str | None             # accepted suggestion text (for revert)
offset: int | None                          # character offset in translated_text
```

### New `Suggestion` response model (not persisted)

```python
class Suggestion(BaseModel):
    text: str       # suggested replacement text
    reason: str     # why this replacement is better
```

### New API endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jobs/{id}/suggestions?lang={lang}&risk_index={i}` | GET | Generate 1-2 suggestions for risk i |
| `/api/jobs/{id}/risks/{risk_index}/accept` | POST | Accept a suggestion, body: `{suggestion, lang}` |
| `/api/jobs/{id}/risks/{risk_index}/dismiss` | POST | Dismiss this risk |
| `/api/jobs/{id}/risks/{risk_index}/revert` | POST | Revert accepted suggestion, restore original text |
| `/api/jobs/{id}/risks/accept-all` | POST | Accept all open risks |

### Frontend `RiskAnnotation` type extension

```typescript
status: "open" | "accepted" | "dismissed"
acceptedSuggestion: string | null
offset: number | null
```

## Section 2: Frontend Interaction Flow

### Per-risk handling

1. Risk card shows "查看替代方案" button (only when `status: "open"`)
2. Click → button becomes loading → call `/suggestions` API → expand suggestion area
3. Suggestion area shows 1-2 cards, each with replacement text + reason + "采纳" button
4. Click "采纳" → call `/accept` API → backend replaces phrase in translated_text → frontend refreshes result → risk status becomes `accepted`, card shows "已采纳：xxx → yyy" with "回退" button
5. Click "回退" → call `/revert` API → restore original text → risk returns to `open`

### Dismiss risk

- Risk card top-right has "忽略" icon button → call `/dismiss` → status becomes `dismissed`, card collapses to one-line gray text (phrase + "已忽略"), click to expand with "撤销忽略" to restore to `open`

### Accept all

- Top of risk detail area (next to summary bar) shows "一键采纳全部建议" button, only when ≥2 `open` risks exist
- Click → serially call `/suggestions` + `/accept` per risk → each card transitions to `accepted` as it completes → button disappears when done
- Individual "回退" still available during and after batch process

### Translation area highlight changes

| Status | Visual style |
|--------|-------------|
| `open` | Current style (red/orange/yellow left border) |
| `accepted` | Green left border + light green background, hover shows accept details |
| `dismissed` | Gray dashed left border + light gray background, visually de-emphasized |

## Section 3: Backend Implementation

### Suggestion generation LLM call

- Reuse existing `qwen-plus` model and LLM client
- Prompt input: source text + full translated text + target language + risk's `phrase` / `risk_type` / `explanation`
- Prompt requires: 1-2 culturally adapted replacement suggestions for the phrase in current translation context, return JSON `[{text, reason}]`
- Synchronous API call (1-2s response), no Celery task needed

### Translation replacement logic

- `/accept` receives `{suggestion, lang}` → locate phrase at `offset` in `translated_text` → replace with suggestion
- Write `risk_annotations[i].status = "accepted"` and `risk_annotations[i].accepted_suggestion = suggestion`
- `/revert` replaces `accepted_suggestion` with `phrase` at stored offset, clears status and accepted_suggestion
- After each accept/revert, recalculate offsets for all `open` risks and write back

### `accept-all` implementation

- Backend iterates all `status: "open"` risk annotations
- For each: call internal suggestion generation → replace → update status
- After all complete, write back `translated_text` and `risk_annotations` once
- Return full updated result for single frontend refresh

## Section 4: Error Handling & Edge Cases

### LLM call failure

- Suggestion generation fails → frontend shows "生成建议失败，请重试" with retry button, no impact on translation or existing states
- During `accept-all`, if one suggestion fails → skip it, continue with remaining, frontend shows "第 N 条建议生成失败，已跳过"

### Concurrency

- Multiple rapid "采纳" clicks → each risk's `accept` is independent API call, backend locates by risk_index offset, no interference
- `accept-all` and single `accept` simultaneously → `accept-all` locks risk processing for that job, single operations return 409 Conflict during lock, frontend shows "正在批量处理中"

### Translation replacement conflicts

- After accepting risk 2, risk 1's phrase offset may shift → backend recalculates all `open` risk offsets after each accept/revert and writes them back
- Frontend must sync updated offsets from response after each operation

### Frontend state management

- Zustand store `result[lang].riskAnnotations` adds write actions: `acceptRisk(lang, riskIndex, suggestion)`, `dismissRisk(lang, riskIndex)`, `revertRisk(lang, riskIndex)`
- After each successful operation, update local state + `translatedText` synchronously, avoid re-fetching entire job

## Scope Boundaries

- **In scope:** Per-risk suggestion generation, accept/dismiss/revert, accept-all, offset recalculation, state transitions
- **Out of scope:** Whitelist management, acceptance score recalculation, keyboard shortcuts (Tab/Esc), right-click context menu, suggestion caching/persistence
