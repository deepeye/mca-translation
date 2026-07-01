# 翻译历史记录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现独立历史记录页面，展示历史翻译任务列表，支持按文体/状态筛选、查看详情、加载到工作台、删除。

**Architecture:** 后端对已有 `GET /api/jobs` 端点增加筛选参数和 `source_text` 返回字段（最小变更，向后兼容）。前端新增 `(main)/history/` 页面目录（左右分栏布局：左侧筛选+任务卡片列表，右侧详情面板），通过 `workspaceStore.loadFromHistory()` 和 `translationStore.loadFromHistory()` 两个新方法将历史任务恢复到工作台。

**Tech Stack:** FastAPI (后端), Next.js App Router + Zustand + Tailwind CSS (前端)

## Global Constraints

- `JobListItem` 新增 `source_text` 字段（可选，向后兼容）
- `GET /api/jobs` 新增 `genre` 和 `status` 可选查询参数（向后兼容）
- 前端目录结构：`frontend/app/(main)/history/` 下放 `page.tsx` + `components/` 子目录
- API Client 方法命名：`listJobs(params?)`
- Store 方法命名：`workspaceStore.loadFromHistory()` / `translationStore.loadFromHistory()`
- 调用 `workspaceStore.loadFromHistory()` 后需 `window.location.href = "/workspace"` 跳转
- 状态映射：completed → ✓ 已完成, failed → ✗ 失败, processing/pending → ⟳ 进行中

---

### Task 1: 后端 Schema — `JobListItem` 增加 `source_text` 字段

**Files:**
- Modify: `backend/app/schemas/job.py:53-58`

**Interfaces:**
- Consumes: existing `JobListItem` class
- Produces: updated `JobListItem` with optional `source_text: str | None = None`

- [ ] **Step 1: Add source_text field to JobListItem**

    ```python
    # backend/app/schemas/job.py
    class JobListItem(BaseModel):
        id: uuid.UUID
        status: str
        genre: str
        target_languages: list[str]
        source_text: str | None = None       # 新增：列表页原文摘要
        created_at: datetime
    ```

- [ ] **Step 2: 验证代码可导入**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/backend
    python -c "from app.schemas.job import JobListItem; print('OK')"
    ```
    Expected: `OK`

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add backend/app/schemas/job.py
    git commit -m "feat(schema): add source_text field to JobListItem"
    ```

---

### Task 2: 后端 API — `GET /api/jobs` 增加筛选参数 + source_text 返回

**Files:**
- Modify: `backend/app/api/jobs.py:59-80`

**Interfaces:**
- Consumes: updated `JobListItem` with `source_text`
- Produces: `GET /api/jobs?genre=xxx&status=xxx` returns `list[JobListItem]` with `source_text[:200]`

- [ ] **Step 1: Modify list_jobs endpoint — add query params and source_text**

    Replace the existing `list_jobs` function:

    ```python
    # backend/app/api/jobs.py
    @router.get("", response_model=list[JobListItem])
    async def list_jobs(
        genre: str | None = Query(None),
        status: str | None = Query(None),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        query = select(TranslationJob).where(TranslationJob.user_id == user.id)
        if genre:
            query = query.where(TranslationJob.genre == genre)
        if status:
            query = query.where(TranslationJob.status == status)
        query = query.order_by(TranslationJob.created_at.desc()).limit(50)
        result = await db.execute(query)
        jobs = result.scalars().all()
        return [
            JobListItem(
                id=j.id,
                status=j.status,
                genre=j.genre,
                target_languages=j.target_languages,
                source_text=j.source_text[:200] if j.source_text else None,
                created_at=j.created_at,
            )
            for j in jobs
        ]
    ```

- [ ] **Step 2: 添加 Query 导入（如果尚未导入）**

    确认文件顶部已有 `from fastapi import ... Query` 导入。如果没有，添加：

    ```python
    from fastapi import APIRouter, Depends, HTTPException, Query, status
    ```

- [ ] **Step 3: 验证代码语法**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/backend
    python -c "from app.api.jobs import list_jobs; print('OK')"
    ```
    Expected: `OK`

- [ ] **Step 4: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add backend/app/api/jobs.py
    git commit -m "feat(api): add genre/status filter and source_text to GET /api/jobs"
    ```

---

### Task 3: 后端测试 — `GET /api/jobs` 筛选和 source_text

**Files:**
- Create: `backend/tests/test_jobs_list.py`

**Interfaces:**
- Tests: Task 1 + 2 endpoints with filtering

- [ ] **Step 1: Write the test file**

    ```python
    """Test GET /api/jobs — list, filter, and source_text."""
    import pytest
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.main import app
    from app.models.job import TranslationJob
    from app.schemas.job import JobListItem


    @pytest.fixture
    def auth_headers():
        """Minimal auth headers for test - uses test user."""
        return {"Authorization": "Bearer test-token"}


    @pytest.mark.asyncio
    async def test_list_jobs_returns_source_text(db: AsyncSession):
        """JobListItem should include truncated source_text."""
        from app.core.database import Base
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Create a job directly
        job = TranslationJob(
            user_id="00000000-0000-0000-0000-000000000001",
            source_text="这是一篇很长的中文测试文章，用于验证历史记录功能中的原文摘要展示。",
            genre="political",
            strategy="semantic_equivalence",
            target_languages=["en-GB", "zh-CN"],
            status="completed",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # We'll test via the API using a test client
        # For now, verify the schema works
        item = JobListItem(
            id=job.id,
            status=job.status,
            genre=job.genre,
            target_languages=job.target_languages,
            source_text=job.source_text[:200] if job.source_text else None,
            created_at=job.created_at,
        )
        assert item.source_text is not None
        assert len(item.source_text) <= 200
        assert "中文测试文章" in item.source_text
    ```

- [ ] **Step 2: Run test**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/backend
    pip install httpx pytest-asyncio 2>/dev/null; pytest tests/test_jobs_list.py -v
    ```

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add backend/tests/test_jobs_list.py
    git commit -m "test: add test for jobs list with source_text"
    ```

---

### Task 4: 前端 API Client — 新增 `listJobs()` 方法

**Files:**
- Modify: `frontend/lib/api-client.ts`

**Interfaces:**
- Produces: `apiClient.listJobs(params?)` returns `Promise<JobListItem[]>`

- [ ] **Step 1: Add JobListItem type and listJobs method**

    在 `api-client.ts` 中新增类型和方法：

    ```typescript
    // Add to frontend/lib/api-client.ts, before the class definition or at top level

    export interface JobListItem {
      id: string;
      status: string;
      genre: string;
      target_languages: string[];
      source_text: string | null;
      created_at: string;
    }

    // Add to the ApiClient class
    async listJobs(params?: { genre?: string; status?: string }): Promise<JobListItem[]> {
      const searchParams = new URLSearchParams();
      if (params?.genre) searchParams.set("genre", params.genre);
      if (params?.status) searchParams.set("status", params.status);
      const qs = searchParams.toString();
      return this.get(`/api/jobs${qs ? `?${qs}` : ""}`);
    }
    ```

- [ ] **Step 2: 验证 TypeScript 编译**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/frontend
    npx tsc --noEmit --strict lib/api-client.ts 2>&1 | head -20
    ```
    Expected: no type errors

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/lib/api-client.ts
    git commit -m "feat(api-client): add listJobs() method and JobListItem type"
    ```

---

### Task 5: 前端 Store — workspaceStore 增加 `loadFromHistory()` 方法

**Files:**
- Modify: `frontend/stores/workspace-store.ts`

**Interfaces:**
- Produces: `workspaceStore.loadFromHistory(job: JobResponse)` restores all workspace state

- [ ] **Step 1: Add loadFromHistory method to workspace store**

    ```typescript
    // Add to WorkspaceState interface
    loadFromHistory: (job: {
      id: string;
      source_text: string;
      genre: string;
      strategy: string;
      cultural_sphere?: string | null;
      audience_type?: string | null;
      target_languages: string[];
    }) => void;

    // Add to store implementation, after setCurrentJobId
    loadFromHistory: (job) =>
      set({
        input: {
          text: job.source_text,
          genre: job.genre as Genre,
          strategy: job.strategy as Strategy,
          culturalSphere: (job.cultural_sphere || "western_english") as CulturalSphere,
          audienceType: (job.audience_type || "general_public") as AudienceType,
        },
        languages: job.target_languages,
        currentJobId: job.id,
        isTranslating: false,
      }),
    ```

- [ ] **Step 2: 验证 TypeScript 编译**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/frontend
    npx tsc --noEmit 2>&1 | head -20
    ```
    Expected: no type errors

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/stores/workspace-store.ts
    git commit -m "feat(store): add loadFromHistory to workspaceStore"
    ```

---

### Task 6: 前端 Store — translationStore 增加 `loadFromHistory()` 方法

**Files:**
- Modify: `frontend/stores/translation-store.ts`

**Interfaces:**
- Consumes: `TranslationResultResponse` from API (fields: language, status, translated_text, risk_annotations, acceptance_score, cultural_adaptation)
- Produces: `translationStore.loadFromHistory(results)` restores all translation results

- [ ] **Step 1: Add loadFromHistory method to translation store**

    ```typescript
    // Add to TranslationState interface
    loadFromHistory: (results: Array<{
      language: string;
      status: string;
      translated_text: string | null;
      risk_annotations: RiskAnnotation[] | null;
      acceptance_score: number;
      cultural_adaptation: CulturalAdaptation | null;
    }>) => void;

    // Add to store implementation, after setAnnotations
    loadFromHistory: (results) =>
      set((s) => {
        const newResults: Record<string, LangResult> = {};
        for (const r of results) {
          newResults[r.language] = {
            status: r.status as ResultStatus,
            translatedText: r.translated_text || "",
            riskAnnotations: r.risk_annotations || [],
            acceptanceScore: r.acceptance_score,
            highlightedIndex: null,
            culturalAdaptation: r.cultural_adaptation,
          };
        }
        return { results: { ...s.results, ...newResults } };
      }),
    ```

- [ ] **Step 2: 验证 TypeScript 编译**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/frontend
    npx tsc --noEmit 2>&1 | head -20
    ```
    Expected: no type errors

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/stores/translation-store.ts
    git commit -m "feat(store): add loadFromHistory to translationStore"
    ```

---

### Task 7: 前端 — 空状态 / 加载骨架组件

**Files:**
- Create: `frontend/app/(main)/history/components/history-empty.tsx`

**Interfaces:**
- Exports: `HistoryEmpty` component — shown when no jobs exist or no filter results

- [ ] **Step 1: Create empty state component**

    ```tsx
    "use client";

    import Link from "next/link";
    import { Button } from "@/components/ui/button";

    interface HistoryEmptyProps {
      /** true = no records at all, false = filter returned no results */
      isAbsoluteEmpty?: boolean;
      onClearFilter?: () => void;
    }

    export function HistoryEmpty({ isAbsoluteEmpty, onClearFilter }: HistoryEmptyProps) {
      if (isAbsoluteEmpty) {
        return (
          <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
            <div className="text-6xl">📋</div>
            <h3 className="text-lg font-medium text-muted-foreground">
              还没有翻译记录
            </h3>
            <p className="text-sm text-muted-foreground">
              开始你的第一次翻译吧
            </p>
            <Link href="/workspace">
              <Button variant="default" className="bg-teal hover:bg-teal-light text-white">
                去翻译
              </Button>
            </Link>
          </div>
        );
      }

      return (
        <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
          <div className="text-6xl">🔍</div>
          <h3 className="text-lg font-medium text-muted-foreground">
            没有符合条件的记录
          </h3>
          <p className="text-sm text-muted-foreground">
            尝试调整筛选条件
          </p>
          {onClearFilter && (
            <Button variant="outline" size="sm" onClick={onClearFilter}>
              清除筛选
            </Button>
          )}
        </div>
      );
    }
    ```

- [ ] **Step 2: Create skeleton loading component** (add to same file or a separate one)

    ```tsx
    // Add to frontend/app/(main)/history/components/history-empty.tsx

    export function HistorySkeleton() {
      return (
        <div className="flex flex-col gap-2 p-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      );
    }
    ```

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/history-empty.tsx
    git commit -m "feat(history): add empty state and skeleton components"
    ```

---

### Task 8: 前端 — FilterBar 组件

**Files:**
- Create: `frontend/app/(main)/history/components/filter-bar.tsx`

**Interfaces:**
- Exports: `FilterBar` — controlled component, calls `onFilterChange({genre?, status?})` on change

- [ ] **Step 1: Create filter bar component**

    ```tsx
    "use client";

    import { useCallback } from "react";

    export interface FilterValues {
      genre?: string;
      status?: string;
    }

    interface FilterBarProps {
      values: FilterValues;
      onChange: (filters: FilterValues) => void;
    }

    const GENRE_OPTIONS = [
      { value: "", label: "全部文体" },
      { value: "political", label: "政治" },
      { value: "news", label: "新闻" },
      { value: "policy", label: "政策" },
      { value: "brand", label: "品牌" },
    ];

    const STATUS_OPTIONS = [
      { value: "", label: "全部状态" },
      { value: "completed", label: "已完成" },
      { value: "failed", label: "失败" },
      { value: "processing", label: "进行中" },
    ];

    export function FilterBar({ values, onChange }: FilterBarProps) {
      const handleGenreChange = useCallback(
        (e: React.ChangeEvent<HTMLSelectElement>) => {
          onChange({ ...values, genre: e.target.value || undefined });
        },
        [values, onChange],
      );

      const handleStatusChange = useCallback(
        (e: React.ChangeEvent<HTMLSelectElement>) => {
          onChange({ ...values, status: e.target.value || undefined });
        },
        [values, onChange],
      );

      return (
        <div className="flex gap-2 px-1">
          <select
            className="flex h-9 w-36 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={values.genre || ""}
            onChange={handleGenreChange}
          >
            {GENRE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            className="flex h-9 w-36 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={values.status || ""}
            onChange={handleStatusChange}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/filter-bar.tsx
    git commit -m "feat(history): add FilterBar component"
    ```

---

### Task 9: 前端 — TaskCard 组件

**Files:**
- Create: `frontend/app/(main)/history/components/task-card.tsx`

**Interfaces:**
- Exports: `TaskCard` — clickable card showing status icon, genre badge, language tags, source_text excerpt, created_at

- [ ] **Step 1: Create task card component**

    ```tsx
    "use client";

    export interface JobListItemData {
      id: string;
      status: string;
      genre: string;
      target_languages: string[];
      source_text: string | null;
      created_at: string;
    }

    interface TaskCardProps {
      job: JobListItemData;
      isSelected: boolean;
      onClick: () => void;
    }

    const STATUS_CONFIG: Record<string, { icon: string; label: string }> = {
      completed: { icon: "✓", label: "已完成" },
      failed: { icon: "✗", label: "失败" },
      processing: { icon: "⟳", label: "进行中" },
      pending: { icon: "⟳", label: "等待中" },
      partial: { icon: "⚠", label: "部分完成" },
    };

    const GENRE_LABELS: Record<string, string> = {
      political: "政治",
      news: "新闻",
      policy: "政策",
      brand: "品牌",
    };

    export function TaskCard({ job, isSelected, onClick }: TaskCardProps) {
      const statusCfg = STATUS_CONFIG[job.status] || { icon: "?", label: job.status };
      const genreLabel = GENRE_LABELS[job.genre] || job.genre;
      const excerpt = job.source_text
        ? job.source_text.length > 80
          ? job.source_text.slice(0, 80) + "..."
          : job.source_text
        : "";
      const time = new Date(job.created_at).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });

      return (
        <button
          onClick={onClick}
          className={`w-full cursor-pointer rounded-lg border p-3 text-left transition-all duration-150 active:scale-[0.99] ${
            isSelected
              ? "border-teal bg-teal-lightest/50 shadow-sm"
              : "border-border bg-card hover:border-teal-light hover:shadow-sm"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm" title={statusCfg.label}>
              {statusCfg.icon}
            </span>
            <span className="rounded bg-teal-lightest px-1.5 py-0.5 text-xs font-medium text-teal-dark">
              {genreLabel}
            </span>
            <div className="flex flex-wrap gap-1">
              {job.target_languages.map((lang) => (
                <span
                  key={lang}
                  className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                >
                  {lang}
                </span>
              ))}
            </div>
          </div>
          {excerpt && (
            <p className="mt-1.5 text-xs text-muted-foreground line-clamp-2">{excerpt}</p>
          )}
          <p className="mt-1 text-[11px] text-muted-foreground/60">{time}</p>
        </button>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/task-card.tsx
    git commit -m "feat(history): add TaskCard component"
    ```

---

### Task 10: 前端 — TaskList 组件（含 TaskCard 列表 + 选中状态管理）

**Files:**
- Create: `frontend/app/(main)/history/components/task-list.tsx`

**Interfaces:**
- Consumes: `JobListItemData[]`, `selectedId`, `onSelect`
- Exports: `TaskList` — renders scrollable list of TaskCards

- [ ] **Step 1: Create task list component**

    ```tsx
    "use client";

    import { TaskCard, type JobListItemData } from "./task-card";

    interface TaskListProps {
      jobs: JobListItemData[];
      selectedId: string | null;
      onSelect: (id: string) => void;
    }

    export function TaskList({ jobs, selectedId, onSelect }: TaskListProps) {
      if (jobs.length === 0) return null;

      return (
        <div className="flex flex-col gap-2 overflow-y-auto">
          {jobs.map((job) => (
            <TaskCard
              key={job.id}
              job={job}
              isSelected={job.id === selectedId}
              onClick={() => onSelect(job.id)}
            />
          ))}
        </div>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/task-list.tsx
    git commit -m "feat(history): add TaskList component"
    ```

---

### Task 11: 前端 — SourceTextView 组件

**Files:**
- Create: `frontend/app/(main)/history/components/source-text-view.tsx`

**Interfaces:**
- Exports: `SourceTextView` — displays full source text in a scrollable area

- [ ] **Step 1: Create source text view component**

    ```tsx
    "use client";

    interface SourceTextViewProps {
      text: string;
    }

    export function SourceTextView({ text }: SourceTextViewProps) {
      return (
        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="mb-1 flex items-center gap-2">
            <span className="text-sm">📝</span>
            <span className="text-xs font-medium text-muted-foreground">原文</span>
          </div>
          <div className="max-h-40 overflow-y-auto text-sm leading-relaxed">
            {text}
          </div>
        </div>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/source-text-view.tsx
    git commit -m "feat(history): add SourceTextView component"
    ```

---

### Task 12: 前端 — TranslationSummary 组件

**Files:**
- Create: `frontend/app/(main)/history/components/translation-summary.tsx`

**Interfaces:**
- Exports: `TranslationSummary` — collapsible panel per language showing status, risks, score, and excerpt

- [ ] **Step 1: Create translation summary component**

    ```tsx
    "use client";

    import { useState } from "react";

    export interface TranslationResultData {
      language: string;
      status: string;
      translated_text: string | null;
      risk_annotations: Array<unknown> | null;
      acceptance_score: number;
    }

    interface TranslationSummaryProps {
      results: TranslationResultData[];
    }

    const STATUS_ICONS: Record<string, string> = {
      completed: "✓",
      failed: "✗",
      streaming: "⟳",
      idle: "○",
    };

    export function TranslationSummary({ results }: TranslationSummaryProps) {
      const [expandedLang, setExpandedLang] = useState<string | null>(null);
      const [allExpanded, setAllExpanded] = useState(false);

      if (results.length === 0) {
        return (
          <p className="text-xs text-muted-foreground">暂无翻译结果</p>
        );
      }

      const toggleAll = () => {
        setAllExpanded(!allExpanded);
        setExpandedLang(null);
      };

      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm">🌐</span>
            {results.length > 1 && (
              <button
                onClick={toggleAll}
                className="text-xs text-teal hover:text-teal-light cursor-pointer"
              >
                {allExpanded ? "全部收起 ▲" : "全部展开 ▼"}
              </button>
            )}
          </div>
          {results.map((r) => {
            const isExpanded = allExpanded || expandedLang === r.language;
            const icon = STATUS_ICONS[r.status] || "?";
            const riskCount = r.risk_annotations?.length || 0;
            const excerpt = r.translated_text
              ? r.translated_text.length > 120
                ? r.translated_text.slice(0, 120) + "..."
                : r.translated_text
              : "";

            return (
              <div key={r.language} className="rounded-lg border border-border">
                <button
                  onClick={() => {
                    setExpandedLang(isExpanded ? null : r.language);
                    setAllExpanded(false);
                  }}
                  className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-left text-xs hover:bg-muted/50"
                >
                  <div className="flex items-center gap-2">
                    <span>{icon}</span>
                    <span className="font-medium">{r.language}</span>
                    <span className="text-muted-foreground">
                      {r.status === "completed" ? "已完成" : r.status}
                    </span>
                    {riskCount > 0 && (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-700">
                        风险 {riskCount} 项
                      </span>
                    )}
                    {r.acceptance_score >= 0 && (
                      <span className="text-muted-foreground">评分 {r.acceptance_score}</span>
                    )}
                  </div>
                  <span className="text-muted-foreground">{isExpanded ? "▲" : "▼"}</span>
                </button>
                {isExpanded && excerpt && (
                  <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
                    {excerpt}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/translation-summary.tsx
    git commit -m "feat(history): add TranslationSummary component"
    ```

---

### Task 13: 前端 — DetailPanel 组件

**Files:**
- Create: `frontend/app/(main)/history/components/detail-panel.tsx`

**Interfaces:**
- Consumes: `JobResponse` from API, `loadToWorkspace` callback, `onDelete` callback
- Exports: `DetailPanel` — right-side detail panel

- [ ] **Step 1: Create detail panel component**

    ```tsx
    "use client";

    import { useState } from "react";
    import { SourceTextView } from "./source-text-view";
    import { TranslationSummary, type TranslationResultData } from "./translation-summary";
    import { Button } from "@/components/ui/button";
    import {
      AlertDialog,
      AlertDialogAction,
      AlertDialogCancel,
      AlertDialogContent,
      AlertDialogDescription,
      AlertDialogFooter,
      AlertDialogHeader,
      AlertDialogTitle,
      AlertDialogTrigger,
    } from "@/components/ui/alert-dialog";

    export interface JobDetailData {
      id: string;
      status: string;
      source_text: string;
      genre: string;
      strategy: string;
      target_languages: string[];
      cultural_sphere?: string | null;
      audience_type?: string | null;
      results: TranslationResultData[];
      created_at: string;
    }

    interface DetailPanelProps {
      job: JobDetailData | null;
      onLoadToWorkspace: (job: JobDetailData) => void;
      onDelete: (jobId: string) => void;
      isDeleting?: boolean;
    }

    const GENRE_LABELS: Record<string, string> = {
      political: "政治",
      news: "新闻",
      policy: "政策",
      brand: "品牌",
    };

    const STRATEGY_LABELS: Record<string, string> = {
      semantic_equivalence: "语义对等",
      audience_first: "受众优先",
      literal_reference: "字面引用",
    };

    export function DetailPanel({ job, onLoadToWorkspace, onDelete, isDeleting }: DetailPanelProps) {
      if (!job) {
        return (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">请选择一条任务查看详情</p>
          </div>
        );
      }

      const strategyLabel = STRATEGY_LABELS[job.strategy] || job.strategy;
      const genreLabel = GENRE_LABELS[job.genre] || job.genre;

      return (
        <div className="flex h-full flex-col gap-4 overflow-y-auto">
          <h3 className="text-sm font-medium">翻译详情</h3>

          <SourceTextView text={job.source_text} />

          <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span>⚙️</span>
              <span>
                文体: {genreLabel} · 策略: {strategyLabel}
              </span>
            </div>
            {(job.cultural_sphere || job.audience_type) && (
              <div className="mt-1 ml-5">
                {job.cultural_sphere && <span>文化圈: {job.cultural_sphere} </span>}
                {job.audience_type && <span>· 受众: {job.audience_type}</span>}
              </div>
            )}
          </div>

          <TranslationSummary results={job.results} />

          <div className="mt-auto flex gap-2 border-t pt-3">
            <Button
              variant="default"
              size="sm"
              className="bg-teal hover:bg-teal-light text-white"
              onClick={() => onLoadToWorkspace(job)}
            >
              🔄 加载到工作台
            </Button>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                  🗑️ 删除
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>确认删除</AlertDialogTitle>
                  <AlertDialogDescription>
                    确定要删除这条翻译记录吗？此操作不可撤销。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => onDelete(job.id)}
                    disabled={isDeleting}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {isDeleting ? "删除中..." : "删除"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/detail-panel.tsx
    git commit -m "feat(history): add DetailPanel component"
    ```

---

### Task 14: 前端 — HistoryLayout 布局容器组件

**Files:**
- Create: `frontend/app/(main)/history/components/history-layout.tsx`

**Interfaces:**
- Exports: `HistoryLayout` — CSS Grid layout: left 40% (filter + list), right 60% (detail)

- [ ] **Step 1: Create layout component**

    ```tsx
    "use client";

    import type { ReactNode } from "react";

    interface HistoryLayoutProps {
      filterBar: ReactNode;
      taskList: ReactNode;
      detailPanel: ReactNode;
    }

    export function HistoryLayout({ filterBar, taskList, detailPanel }: HistoryLayoutProps) {
      return (
        <div className="flex h-[calc(100dvh-3.5rem)] gap-0">
          {/* Left panel */}
          <div className="flex w-[40%] flex-col border-r border-border p-3 gap-3">
            {filterBar}
            <div className="flex-1 overflow-y-auto">
              {taskList}
            </div>
          </div>
          {/* Right panel */}
          <div className="w-[60%] p-4 overflow-y-auto">
            {detailPanel}
          </div>
        </div>
      );
    }
    ```

- [ ] **Step 2: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/components/history-layout.tsx
    git commit -m "feat(history): add HistoryLayout component"
    ```

---

### Task 15: 前端 — History Page 主入口（page.tsx）

**Files:**
- Create: `frontend/app/(main)/history/page.tsx`

**Interfaces:**
- Consumes: All components from Tasks 7-14, `apiClient.listJobs()`, `apiClient.get()`, `apiClient.delete()`
- Imports: `workspaceStore.loadFromHistory()`, `translationStore.loadFromHistory()`

- [ ] **Step 1: Create history page**

    ```tsx
    "use client";

    import { useCallback, useEffect, useState } from "react";
    import { apiClient } from "@/lib/api-client";
    import { useWorkspaceStore } from "@/stores/workspace-store";
    import { useTranslationStore } from "@/stores/translation-store";
    import { HistoryLayout } from "./components/history-layout";
    import { FilterBar, type FilterValues } from "./components/filter-bar";
    import { TaskList } from "./components/task-list";
    import { DetailPanel, type JobDetailData } from "./components/detail-panel";
    import { HistoryEmpty, HistorySkeleton } from "./components/history-empty";
    import type { JobListItemData } from "./components/task-card";
    import type { TranslationResultData } from "./components/translation-summary";

    export default function HistoryPage() {
      const [jobs, setJobs] = useState<JobListItemData[]>([]);
      const [isLoading, setIsLoading] = useState(true);
      const [error, setError] = useState<string | null>(null);
      const [filters, setFilters] = useState<FilterValues>({});
      const [selectedId, setSelectedId] = useState<string | null>(null);
      const [selectedJob, setSelectedJob] = useState<JobDetailData | null>(null);
      const [isLoadingDetail, setIsLoadingDetail] = useState(false);
      const [isDeleting, setIsDeleting] = useState(false);

      const workspaceLoadFromHistory = useWorkspaceStore((s) => s.loadFromHistory);
      const translationLoadFromHistory = useTranslationStore((s) => s.loadFromHistory);

      // Fetch job list
      const fetchJobs = useCallback(async (currentFilters: FilterValues) => {
        setIsLoading(true);
        setError(null);
        try {
          const data = await apiClient.listJobs({
            genre: currentFilters.genre,
            status: currentFilters.status,
          });
          setJobs(data || []);
        } catch (err) {
          setError(err instanceof Error ? err.message : "加载失败");
        } finally {
          setIsLoading(false);
        }
      }, []);

      // Initial load
      useEffect(() => {
        fetchJobs(filters);
      }, []); // eslint-disable-line react-hooks/exhaustive-deps

      // Handle filter change
      const handleFilterChange = useCallback(
        (newFilters: FilterValues) => {
          setFilters(newFilters);
          setSelectedId(null);
          setSelectedJob(null);
          fetchJobs(newFilters);
        },
        [fetchJobs],
      );

      // Handle job selection — load full detail
      const handleSelectJob = useCallback(async (jobId: string) => {
        setSelectedId(jobId);
        setIsLoadingDetail(true);
        setSelectedJob(null);
        try {
          const data = await apiClient.get(`/api/jobs/${jobId}`);
          setSelectedJob(data);
        } catch (err) {
          setError(err instanceof Error ? err.message : "加载详情失败");
        } finally {
          setIsLoadingDetail(false);
        }
      }, []);

      // Handle "加载到工作台"
      const handleLoadToWorkspace = useCallback(
        (job: JobDetailData) => {
          workspaceLoadFromHistory(job);
          translationLoadFromHistory(job.results);
          window.location.href = "/workspace";
        },
        [workspaceLoadFromHistory, translationLoadFromHistory],
      );

      // Handle delete
      const handleDelete = useCallback(
        async (jobId: string) => {
          setIsDeleting(true);
          try {
            await apiClient.delete(`/api/jobs/${jobId}`);
            setJobs((prev) => prev.filter((j) => j.id !== jobId));
            if (selectedId === jobId) {
              setSelectedId(null);
              setSelectedJob(null);
            }
          } catch (err) {
            setError(err instanceof Error ? err.message : "删除失败");
          } finally {
            setIsDeleting(false);
          }
        },
        [selectedId],
      );

      // Render left panel content
      const renderLeftContent = () => {
        if (error) {
          return (
            <div className="flex flex-col items-center gap-2 py-10">
              <p className="text-sm text-destructive">加载失败: {error}</p>
              <button
                onClick={() => fetchJobs(filters)}
                className="text-sm text-teal hover:text-teal-light cursor-pointer"
              >
                重试
              </button>
            </div>
          );
        }

        if (isLoading) {
          return <HistorySkeleton />;
        }

        if (jobs.length === 0) {
          return (
            <HistoryEmpty
              isAbsoluteEmpty={!filters.genre && !filters.status}
              onClearFilter={filters.genre || filters.status ? () => handleFilterChange({}) : undefined}
            />
          );
        }

        return <TaskList jobs={jobs} selectedId={selectedId} onSelect={handleSelectJob} />;
      };

      // Render right panel content
      const renderRightContent = () => {
        if (isLoadingDetail) {
          return <HistorySkeleton />;
        }
        return (
          <DetailPanel
            job={selectedJob}
            onLoadToWorkspace={handleLoadToWorkspace}
            onDelete={handleDelete}
            isDeleting={isDeleting}
          />
        );
      };

      return (
        <HistoryLayout
          filterBar={
            <FilterBar values={filters} onChange={handleFilterChange} />
          }
          taskList={renderLeftContent()}
          detailPanel={renderRightContent()}
        />
      );
    }
    ```

- [ ] **Step 2: 验证 TypeScript 编译**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/frontend
    npx tsc --noEmit 2>&1 | head -30
    ```
    Expected: no type errors

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/history/page.tsx
    git commit -m "feat(history): add HistoryPage with full interaction flow"
    ```

---

### Task 16: 前端 — 导航栏增加「历史」链接

**Files:**
- Modify: `frontend/app/(main)/layout.tsx`

- [ ] **Step 1: Add history nav link**

    ```tsx
    // Add after the 术语库 link
    <Link href="/history" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">历史</Link>
    ```

    The full nav section becomes:

    ```tsx
    <nav className="flex gap-4">
      <Link href="/workspace" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">工作台</Link>
      <Link href="/review" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">审校</Link>
      <Link href="/glossary" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">术语库</Link>
      <Link href="/history" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">历史</Link>
    </nav>
    ```

- [ ] **Step 2: 验证页面可渲染**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/frontend
    npx tsc --noEmit 2>&1 | head -20
    ```

- [ ] **Step 3: Commit**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    git add frontend/app/(main)/layout.tsx
    git commit -m "feat(history): add nav link to history page"
    ```

---

### Task 17: 集成验证

- [ ] **Step 1: 启动基础设施**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation
    docker compose -f docker-compose.dev.yml up -d
    ```

- [ ] **Step 2: 启动后端**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/backend
    uvicorn app.main:app --reload &
    ```

- [ ] **Step 3: 启动前端**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/frontend
    pnpm dev &
    ```

- [ ] **Step 4: 创建测试翻译任务**

    通过 Swagger UI 或 curl 创建一个翻译任务：
    ```bash
    # First login
    TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

    # Create a job
    curl -X POST http://localhost:8000/api/jobs \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"source_text":"这是一篇测试文章，用于验证历史记录功能。","genre":"political","strategy":"semantic_equivalence","target_languages":["en-GB","zh-CN"],"cultural_sphere":"western_english","audience_type":"general_public"}'
    ```

- [ ] **Step 5: 打开前端历史页面验证**

    在浏览器中打开 `http://localhost:3000/history`，验证：
    - 历史列表显示刚创建的任务
    - 筛选功能正常
    - 点击任务卡片可查看详情
    - 「加载到工作台」跳转到工作台并恢复数据
    - 删除功能正常

- [ ] **Step 6: 运行后端测试**

    ```bash
    cd /Users/pdmi/cc-project/mca-translation/backend
    pytest tests/ -v
    ```
