# System Glossary Category Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frontend-only toggle on the system glossary section that hides/shows category labels (section headings + inline badges), defaulting to hidden (flat list), persisted in `localStorage`.

**Architecture:** A single boolean state `showCategories` (default `false`) in `GlossaryPage` controls whether the system glossary renders as a flat list or grouped-by-`term_type`. A `Button` next to the 「系统知识库」 heading toggles the state and writes to `localStorage`; a mount-time `useEffect` reads the saved preference. The existing system entry card markup is extracted into a `renderSystemEntryCard(entry, showBadge)` helper so the flat and grouped paths share one card definition.

**Tech Stack:** Next.js (App Router, client component), React 19, TypeScript, Tailwind, shadcn `Button`, Vitest + jsdom + @testing-library/react.

## Global Constraints

- Frontend-only. No backend, API, schema, or model changes. `term_type` is still returned by the API; the frontend only chooses whether to render it.
- Scope: system glossary section only. The user-custom glossary section's inline badge is unchanged.
- Default state is **hidden** (`showCategories = false`) — a behavior change for all users.
- `localStorage` key: `glossary:showSystemCategories`, values `"true"` / `"false"` (string). Read/write wrapped in `try/catch` (disabled localStorage falls back to default, session-only).
- Use the existing `Button` primitive (`@/components/ui/button`). Do **not** install `Switch` or `Checkbox` (neither is present in the project).
- Toggle button renders only when `systemEntries.length > 0`.
- Button label is action-oriented: `showCategories ? "隐藏分类" : "显示分类"`.
- `+N` count badge, preferred-translation arrow (`→ pref`), and `risk_notes` always render — they are not category labels.
- Code comments in Chinese for important logic (project convention).
- `groupedSystemEntries` computation is unchanged (reused for stable ordering in both modes).

---

## File Structure

- **Modify:** `frontend/app/(main)/glossary/page.tsx` — add `showCategories` state, `SHOW_SYSTEM_CATEGORIES_KEY` constant, mount `useEffect`, `toggleCategories` handler, `renderSystemEntryCard(entry, showBadge)` helper, and conditional flat/grouped render with the toggle button.
- **Modify:** `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx` — add `localStorage.clear()` to `beforeEach`, add 5 tests covering default-flat, toggle-on, toggle-off, persisted-read, and write-on-toggle.

No new files. No backend files.

---

## Task 1: In-memory category toggle (default flat, click to show/hide)

Adds the `showCategories` state, the toggle button, the `renderSystemEntryCard` helper, and conditional flat/grouped rendering. No persistence yet — that is Task 2.

**Files:**
- Modify: `frontend/app/(main)/glossary/page.tsx`
- Test: `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx`

**Interfaces:**
- Consumes: `SYSTEM_GLOSSARY_TERM_TYPE_LABELS`, `DEFAULT_TERM_TYPE_LABEL` (already imported at `page.tsx:8-12`); existing in-component helpers `getPreferredTranslation`, `getFilledCount`, `getFilledLanguageLabels`; existing `groupedSystemEntries` (`page.tsx:301-311`); existing `Button` import.
- Produces: `showCategories: boolean` state; `toggleCategories(): void`; `renderSystemEntryCard(entry: GlossaryEntry, showBadge: boolean): JSX.Element`.

- [ ] **Step 1: Add `localStorage.clear()` to the test setup**

In `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx`, update `beforeEach` (currently lines 19-23) so each test starts with a clean `localStorage`:

```tsx
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockApiClient.listGlossaryEntries.mockResolvedValue([]);
    mockApiClient.listUserGlossaryEntries.mockResolvedValue([]);
  });
```

- [ ] **Step 2: Write the failing test — default render is flat (no category labels, button reads 「显示分类」)**

Append this test inside the existing `describe("GlossaryPage", () => { ... })` block in `glossary-page.test.tsx`:

```tsx
  it("renders system glossary as a flat list by default (no category labels)", async () => {
    mockApiClient.listGlossaryEntries.mockResolvedValue([
      {
        id: "sys-1",
        source_term: "一带一路",
        term_type: "political_discourse",
        translations: { "en-GB": { preferred: "BRI", alternatives: [], notes: "" } },
        risk_notes: "",
        applicable_genres: [],
      },
      {
        id: "sys-2",
        source_term: "故宫",
        term_type: "cultural_site",
        translations: { "en-GB": { preferred: "the Forbidden City", alternatives: [], notes: "" } },
        risk_notes: "",
        applicable_genres: [],
      },
    ]);

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByText("一带一路")).toBeInTheDocument();
    });
    expect(screen.getByText("故宫")).toBeInTheDocument();

    // 默认隐藏:分类标签(分组标题 + 行内徽章)均不出现
    expect(screen.queryAllByText("政治话语")).toHaveLength(0);
    expect(screen.queryAllByText("文化地标")).toHaveLength(0);

    // 开关按钮存在,文案为「显示分类」(动作语义)
    expect(screen.getByText("显示分类")).toBeInTheDocument();
  });
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: FAIL — `screen.getByText("显示分类")` not found (button doesn't exist yet), and/or `queryAllByText("政治话语")` returns 1 (current code shows the heading + badge by default).

- [ ] **Step 4: Write the failing test — clicking 「显示分类」 shows grouped view**

Append:

```tsx
  it("shows category headings and badges when 「显示分类」 is clicked", async () => {
    mockApiClient.listGlossaryEntries.mockResolvedValue([
      {
        id: "sys-1",
        source_term: "一带一路",
        term_type: "political_discourse",
        translations: { "en-GB": { preferred: "BRI", alternatives: [], notes: "" } },
        risk_notes: "",
        applicable_genres: [],
      },
    ]);

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByText("一带一路")).toBeInTheDocument();
    });

    // 点击前:无分类标签
    expect(screen.queryAllByText("政治话语")).toHaveLength(0);

    fireEvent.click(screen.getByText("显示分类"));

    // 点击后:分组标题(政治话语)出现;按钮文案切换为「隐藏分类」
    expect(screen.getByRole("heading", { name: "政治话语" })).toBeInTheDocument();
    expect(screen.getByText("隐藏分类")).toBeInTheDocument();
  });
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: FAIL — toggle button not found.

- [ ] **Step 6: Write the failing test — clicking 「隐藏分类」 returns to flat**

Append:

```tsx
  it("returns to flat list when 「隐藏分类」 is clicked", async () => {
    mockApiClient.listGlossaryEntries.mockResolvedValue([
      {
        id: "sys-1",
        source_term: "一带一路",
        term_type: "political_discourse",
        translations: { "en-GB": { preferred: "BRI", alternatives: [], notes: "" } },
        risk_notes: "",
        applicable_genres: [],
      },
    ]);

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByText("一带一路")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("显示分类"));
    expect(screen.getByRole("heading", { name: "政治话语" })).toBeInTheDocument();

    fireEvent.click(screen.getByText("隐藏分类"));

    // 切回扁平:分类标签消失,按钮回到「显示分类」
    expect(screen.queryAllByText("政治话语")).toHaveLength(0);
    expect(screen.getByText("显示分类")).toBeInTheDocument();
  });
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: FAIL — toggle button not found.

- [ ] **Step 8: Implement — add `showCategories` state**

In `frontend/app/(main)/glossary/page.tsx`, add the state immediately after the `hasMoreUser` declaration (currently line 73):

```tsx
  // 用户条目分页
  const [userOffset, setUserOffset] = useState(0);
  const [hasMoreUser, setHasMoreUser] = useState(false);

  // 系统知识库分类标签显示开关(默认隐藏 → 扁平列表)
  const [showCategories, setShowCategories] = useState(false);
```

- [ ] **Step 9: Implement — add `toggleCategories` handler**

In `frontend/app/(main)/glossary/page.tsx`, add the handler immediately before the `// ---- Render helpers ----` comment (currently line 313):

```tsx
  // 切换系统知识库分类标签的显示
  function toggleCategories() {
    setShowCategories((v) => !v);
  }

  // ---- Render helpers ----
```

- [ ] **Step 10: Implement — extract `renderSystemEntryCard` helper**

In `frontend/app/(main)/glossary/page.tsx`, add the helper inside the component, immediately after the `toggleCategories` function added in Step 9 (still before `// ---- Render helpers ----`). This moves the existing inline system-entry card markup (currently `page.tsx:607-638`) into a reusable function and gates the badge on `showBadge`:

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
        {(() => {
          const pref = getPreferredTranslation(entry);
          if (pref) {
            return <span className="ml-2 text-sm text-teal-700">→ {pref}</span>;
          }
          return null;
        })()}
        {(() => {
          const count = getFilledCount(entry);
          if (count > 0) {
            return (
              <span
                className="ml-2 inline-flex items-center rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-700"
                title={getFilledLanguageLabels(entry)}
              >
                +{count}
              </span>
            );
          }
          return null;
        })()}
        {entry.risk_notes && (
          <div className="mt-1 text-xs text-orange-600">⚠ {entry.risk_notes}</div>
        )}
      </div>
    );
  }
```

- [ ] **Step 11: Implement — replace the system glossary render block**

In `frontend/app/(main)/glossary/page.tsx`, replace the entire `{/* ---- System glossary ---- */}` block (currently lines 594-644) with:

```tsx
      {/* ---- System glossary ---- */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">系统知识库</h2>
          {systemEntries.length > 0 && (
            <Button variant="outline" size="sm" onClick={toggleCategories}>
              {showCategories ? "隐藏分类" : "显示分类"}
            </Button>
          )}
        </div>
        {systemEntries.length === 0 ? (
          <p className="text-sm text-muted-foreground">系统知识库为空</p>
        ) : showCategories ? (
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
        ) : (
          <div className="space-y-2">
            {groupedSystemEntries.flatMap(([, entries]) =>
              entries.map((entry) => renderSystemEntryCard(entry, false)),
            )}
          </div>
        )}
      </div>
```

- [ ] **Step 12: Run all glossary-page tests to verify they pass**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: PASS — all existing tests plus the 3 new tests pass.

- [ ] **Step 13: Commit**

```bash
git add 'frontend/app/(main)/glossary/page.tsx' 'frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx'
git commit -m "feat(glossary): add in-memory category toggle for system glossary"
```

---

## Task 2: Persist the toggle to `localStorage`

Adds the `SHOW_SYSTEM_CATEGORIES_KEY` constant, a mount-time `useEffect` that reads the saved preference, and writes inside `toggleCategories`. The toggle now survives page reloads.

**Files:**
- Modify: `frontend/app/(main)/glossary/page.tsx`
- Test: `frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx`

**Interfaces:**
- Consumes: `showCategories`, `setShowCategories`, `toggleCategories` from Task 1.
- Produces: module-level `SHOW_SYSTEM_CATEGORIES_KEY` constant; persistence behavior (read on mount, write on toggle).

- [ ] **Step 1: Write the failing test — persisted `"true"` shows grouped view on mount**

Append to the `describe("GlossaryPage", ...)` block in `glossary-page.test.tsx`:

```tsx
  it("shows grouped view on mount when localStorage has \"true\"", async () => {
    localStorage.setItem("glossary:showSystemCategories", "true");
    mockApiClient.listGlossaryEntries.mockResolvedValue([
      {
        id: "sys-1",
        source_term: "一带一路",
        term_type: "political_discourse",
        translations: { "en-GB": { preferred: "BRI", alternatives: [], notes: "" } },
        risk_notes: "",
        applicable_genres: [],
      },
    ]);

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "政治话语" })).toBeInTheDocument();
    });
    expect(screen.getByText("隐藏分类")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: FAIL — heading 「政治话语」 not found (mount read not implemented yet; default stays flat).

- [ ] **Step 3: Write the failing test — toggling writes to `localStorage`**

Append:

```tsx
  it("persists toggle state to localStorage", async () => {
    mockApiClient.listGlossaryEntries.mockResolvedValue([
      {
        id: "sys-1",
        source_term: "一带一路",
        term_type: "political_discourse",
        translations: { "en-GB": { preferred: "BRI", alternatives: [], notes: "" } },
        risk_notes: "",
        applicable_genres: [],
      },
    ]);

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByText("一带一路")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("显示分类"));
    expect(localStorage.getItem("glossary:showSystemCategories")).toBe("true");

    fireEvent.click(screen.getByText("隐藏分类"));
    expect(localStorage.getItem("glossary:showSystemCategories")).toBe("false");
  });
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: FAIL — `localStorage.getItem(...)` returns `null` (toggle does not write yet).

- [ ] **Step 5: Implement — add the `localStorage` key constant**

In `frontend/app/(main)/glossary/page.tsx`, add the constant at module level next to `USER_PAGE_SIZE` (currently line 37):

```tsx
const USER_PAGE_SIZE = 10;
const SHOW_SYSTEM_CATEGORIES_KEY = "glossary:showSystemCategories";
```

- [ ] **Step 6: Implement — add the mount `useEffect` that reads the preference**

In `frontend/app/(main)/glossary/page.tsx`, add the effect immediately after the `showCategories` state declared in Task 1 (i.e., right after `const [showCategories, setShowCategories] = useState(false);`):

```tsx
  // 系统知识库分类标签显示开关(默认隐藏 → 扁平列表)
  const [showCategories, setShowCategories] = useState(false);

  // 挂载时读取持久化的开关偏好(localStorage 不可用时静默回落到默认隐藏)
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

- [ ] **Step 7: Implement — write to `localStorage` inside `toggleCategories`**

In `frontend/app/(main)/glossary/page.tsx`, replace the `toggleCategories` function added in Task 1 with:

```tsx
  // 切换系统知识库分类标签的显示,并持久化到 localStorage
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

- [ ] **Step 8: Run all glossary-page tests to verify they pass**

Run: `cd frontend && pnpm test -- glossary-page`
Expected: PASS — all existing tests plus the 5 new tests (3 from Task 1 + 2 from Task 2) pass.

- [ ] **Step 9: Commit**

```bash
git add 'frontend/app/(main)/glossary/page.tsx' 'frontend/app/(main)/glossary/__tests__/glossary-page.test.tsx'
git commit -m "feat(glossary): persist system glossary category toggle in localStorage"
```

---

## Self-Review

**1. Spec coverage:**
- §1 State & persistence (default `false`, mount read, toggle write, try/catch) → Task 1 Step 8 (state) + Task 2 Steps 5-7 (key, read, write). ✓
- §2 Toggle control placement (flex row, button only when entries exist, action-oriented label) → Task 1 Step 11. ✓
- §3 Rendering — `renderSystemEntryCard(entry, showBadge)` extraction + flat/grouped paths → Task 1 Steps 10-11. ✓
- §4 What does not change (no backend, user section untouched, `groupedSystemEntries` unchanged) → Global Constraints + no backend tasks. ✓
- Edge cases (first visit, reload, search independence, empty glossary, localStorage disabled) → covered by default-false + try/catch + `systemEntries.length > 0` guard; empty-glossary path preserved in Step 11. ✓
- Testing (default flat, toggle on + write, persisted read, toggle off) → Task 1 Steps 2/4/6, Task 2 Steps 1/3. ✓

**2. Placeholder scan:** No TBD/TODO/"add appropriate error handling" — every code step has complete code. Error handling is concrete (`try/catch` with Chinese comment). ✓

**3. Type/name consistency:** `showCategories`, `setShowCategories`, `toggleCategories`, `renderSystemEntryCard(entry, showBadge)`, `SHOW_SYSTEM_CATEGORIES_KEY` — identical across Task 1 and Task 2. `localStorage` key string `"glossary:showSystemCategories"` matches between code (`SHOW_SYSTEM_CATEGORIES_KEY` value) and tests. ✓

No issues found.
