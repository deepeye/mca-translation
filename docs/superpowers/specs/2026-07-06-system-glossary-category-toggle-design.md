# System Glossary Category Toggle — Design

**Date:** 2026-07-06
**Status:** Approved for implementation
**Scope:** Frontend only — system glossary display on the glossary management page

## Background

The glossary management page (`frontend/app/(main)/glossary/page.tsx`) renders the system knowledge base (系统知识库) grouped by `term_type`. Each group has a section heading (`<h3>`, e.g. 「政治话语」「机构会议」), and each entry row carries an inline category badge — a small muted pill showing the same `term_type` label. The 11 system category labels and their display order are defined in `frontend/lib/glossary-categories.ts` (`SYSTEM_GLOSSARY_TERM_TYPE_LABELS`, `SYSTEM_GLOSSARY_TERM_TYPE_ORDER`).

The inline badge is redundant with the section heading: both surface the same category. For users who only want to read terms and their translations, the category chrome is visual noise.

**Request:** Let users hide the category labels on the frontend — both the section headings and the inline badges — collapsing the system glossary into a flat list of terms + translations. The toggle is a single global on/off switch (not per-category filtering), persisted across sessions, defaulting to hidden.

**What's already in place (no change needed):**
- `groupedSystemEntries` (page.tsx:301-311) already groups system entries by `term_type` in the canonical `SYSTEM_GLOSSARY_TERM_TYPE_ORDER`. This computation is reused as-is to provide a stable ordering for the flat list.
- The page is a Next.js client component (`"use client"`) and already holds all its view state (search, pagination, form) in local `useState`. Adding one more boolean is consistent with the existing pattern.
- `localStorage` is used directly elsewhere in the frontend (`frontend/lib/api-client.ts` for the auth token, `frontend/app/(main)/layout.tsx` for logout). No SSR-safe view-preference hook exists; this spec establishes the standard pattern inline.

## Goals

1. A single toggle control on the system glossary section lets the user switch between **flat list** (no category headings, no inline badges) and **grouped view** (current behavior).
2. The toggle state persists in `localStorage` across sessions.
3. The default state (no saved preference) is **hidden** — flat list. This is an intentional behavior change: the system glossary default appearance becomes the flat list for all users.
4. The change is frontend-only; no backend, API, schema, or model changes.

## Non-Goals

- No per-category filtering (show/hide individual categories). The toggle is binary: all category chrome on, or all off.
- No change to the **user custom glossary** section. Its inline badges remain as-is. (The request explicitly names the system knowledge base.)
- No backend persistence of the preference (no user-settings table, no API). The preference is per-browser via `localStorage`.
- No change to the `+N` filled-language count badge, the preferred-translation arrow (`→ pref`), or `risk_notes` display — these are not category labels and always render.
- No change to `groupedSystemEntries` ordering logic, the inline highlighter, glossary detection, or the translation pipeline.

## Design

### 1. State & persistence

**File:** `frontend/app/(main)/glossary/page.tsx`

Add a local state and a localStorage key:

```ts
const SHOW_SYSTEM_CATEGORIES_KEY = "glossary:showSystemCategories";
const [showCategories, setShowCategories] = useState(false); // 默认隐藏
```

**Mount read** — a `useEffect` that runs once on mount, reads the saved preference, and updates state. Wrapped in `try/catch` so a disabled/blocked `localStorage` falls back to the default (hidden) without throwing:

```ts
useEffect(() => {
  try {
    if (localStorage.getItem(SHOW_SYSTEM_CATEGORIES_KEY) === "true") {
      setShowCategories(true);
    }
  } catch {
    // localStorage 不可用时保持默认隐藏
  }
}, []);
```

**Toggle handler** — flips state and writes back:

```ts
function toggleCategories() {
  setShowCategories((v) => {
    const next = !v;
    try {
      localStorage.setItem(SHOW_SYSTEM_CATEGORIES_KEY, String(next));
    } catch {
      // 写入失败时仅影响当前会话
    }
    return next;
  });
}
```

**SSR / hydration:** The server and the first client render both use `showCategories = false` (flat list), so the hydrated DOM matches the server HTML — no hydration mismatch. Users who previously opted into "show" see a one-frame flip to the grouped view after `useEffect` runs. This is acceptable and unavoidable without server-side preference storage (out of scope).

### 2. Toggle control placement

Replace the bare 「系统知识库」 `<h2>` (page.tsx:596) with a flex row containing the heading and the toggle button. The button renders only when there are system entries to display (an empty glossary has nothing to categorize):

```tsx
<div className="mb-4 flex items-center justify-between">
  <h2 className="text-lg font-semibold">系统知识库</h2>
  {systemEntries.length > 0 && (
    <Button variant="outline" size="sm" onClick={toggleCategories}>
      {showCategories ? "隐藏分类" : "显示分类"}
    </Button>
  )}
</div>
```

The button label is **action-oriented**: it names what clicking will do. When the list is flat (default), the button reads 「显示分类」; when grouped, 「隐藏分类」. Uses the existing `Button` primitive (`frontend/components/ui/button.tsx`) — no new component needed (no `Switch`/`Checkbox` is installed in the project).

### 3. Rendering — flat vs grouped

`groupedSystemEntries` (page.tsx:301-311) is unchanged; it provides stable category-ordered grouping for both modes.

To avoid duplicating the ~30-line system entry card markup, extract it into a helper inside the component. This extraction is a targeted improvement that directly serves this feature (two call sites with different `showBadge` values), not gratuitous refactoring:

```tsx
function renderSystemEntryCard(entry: GlossaryEntry, showBadge: boolean) {
  return (
    <div key={entry.id} className="rounded border border-border p-3">
      <span className="font-medium">{entry.source_term}</span>
      {showBadge && (
        <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          {SYSTEM_GLOSSARY_TERM_TYPE_LABELS[entry.term_type] || DEFAULT_TERM_TYPE_LABEL}
        </span>
      )}
      {/* 首选译法箭头、+N 计数、risk_notes 保持不变 */}
      …
    </div>
  );
}
```

**Grouped mode** (`showCategories === true`, current behavior):

```tsx
<div className="space-y-6">
  {groupedSystemEntries.map(([termType, entries]) => (
    <section key={termType}>
      <h3 className="mb-3 text-base font-semibold text-teal-800">
        {SYSTEM_GLOSSARY_TERM_TYPE_LABELS[termType] || DEFAULT_TERM_TYPE_LABEL}
      </h3>
      <div className="space-y-2">
        {entries.map((entry) => renderSystemEntryCard(entry, true))}
      </div>
    </section>
  ))}
</div>
```

**Flat mode** (`showCategories === false`, default) — single uniform-spaced list, entries in the same canonical category order:

```tsx
<div className="space-y-2">
  {groupedSystemEntries.flatMap(([, entries]) =>
    entries.map((entry) => renderSystemEntryCard(entry, false)),
  )}
</div>
```

### 4. What does not change

- **Backend:** `term_type` is still returned by `GET /api/glossary/entries`; the frontend simply chooses not to render it in flat mode. No API/model/schema changes.
- **User custom glossary section:** inline badge (page.tsx:523-525) remains.
- **Inline highlighter, glossary detection, translation pipeline:** unaffected.
- **`groupedSystemEntries` computation:** unchanged.

## Edge cases

- **First visit (no localStorage):** `showCategories` defaults to `false` → flat list. ✓
- **User toggles on, then reloads:** `useEffect` reads `"true"` → grouped view after hydration. ✓
- **Search filters entries:** the toggle applies to whatever entries are currently shown; search and toggle are independent. ✓
- **Empty system glossary:** toggle button not rendered; the empty-state message 「系统知识库为空」 shows as today. ✓
- **`localStorage` disabled / throws:** `try/catch` around both read and write; falls back to default hidden, session-only. ✓

## Testing

**File:** `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx`

The existing four tests mock system entries as `[]` and only exercise the `user_defined` section, so they are unaffected by the default-hidden change. Add:

1. **Default flat render** — seed `listGlossaryEntries` with ≥2 system entries in different `term_type` groups, no localStorage. Assert no category heading text (e.g. 「政治话语」) and no inline category badge appear; assert both entries render in a flat list (toggle button reads 「显示分类」).
2. **Toggle on** — click 「显示分类」. Assert category headings and inline badges appear, and `localStorage.setItem("glossary:showSystemCategories", "true")` was called.
3. **Persisted preference** — pre-seed `localStorage` with `"true"` before mount. Assert grouped view (heading + badge) renders by default without clicking.
4. **Toggle off from shown** — starting from shown, click 「隐藏分类」. Assert headings/badges disappear and `"false"` is written.

Mock `localStorage` per test via `vi.stubGlobal` / a spy in `beforeEach`, restoring after each.

## Open questions

None. (Default state, toggle scope, persistence, and UI placement are all confirmed.)
