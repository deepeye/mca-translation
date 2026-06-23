# 审校服务（Review Service）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现独立审校页面，支持对照审校（原文+译文）和独立诊断（仅译文）两种模式，输出内联标注、问题卡片和审校报告。

**Architecture:** 后端复用现有 `bailian_client` 和 cultural 参数，新增 `ReviewService` 组装专用审校 prompt 并解析 JSON 响应；前端新建独立 `/review` 页面、Zustand store 和组件，复用现有 mark 渲染和颜色分级模式。

**Tech Stack:** FastAPI, Pydantic, Bailian (qwen-plus), Next.js 16, React 19, Zustand 5, Tailwind CSS 4, shadcn/ui

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/schemas/review.py` | Create | Pydantic schemas: ReviewRequest, ReviewIssue, ReviewCategory, ReviewResult |
| `backend/app/llm/prompts.py` | Modify | Append DUAL_REVIEW_PROMPT, SINGLE_REVIEW_PROMPT |
| `backend/app/services/review.py` | Create | ReviewService: prompt 组装、LLM 调用、JSON 解析、异常处理 |
| `backend/app/api/reviews.py` | Create | FastAPI router, POST /api/reviews |
| `backend/app/main.py` | Modify | Register reviews router |
| `frontend/lib/api-client.ts` | Modify | Add `postReview` method |
| `frontend/stores/review-store.ts` | Create | Review state management (Zustand) |
| `frontend/app/(main)/review/page.tsx` | Create | Review page route |
| `frontend/components/review/review-input-panel.tsx` | Create | Mode switch + source/translated inputs + params + submit |
| `frontend/components/review/score-badge.tsx` | Create | Overall score badge with color grading |
| `frontend/components/review/issue-card.tsx` | Create | Single issue card with severity/category/original/suggestion |
| `frontend/components/review/review-result-panel.tsx` | Create | Score overview + inline annotated text + issue card list |
| `frontend/components/review/review-report-panel.tsx` | Create | Collapsible structured report summary |
| `frontend/app/(main)/layout.tsx` | Modify | Add "审校" nav link |

---

## Task 1: Backend — Review Schemas

**Files:**
- Create: `backend/app/schemas/review.py`

- [x] **Step 1: Write the schemas**

Create `backend/app/schemas/review.py`:

```python
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    category: str
    severity: Literal["low", "medium", "high"]
    span: Optional[dict] = None
    original: str
    suggestion: str
    explanation: str
    source_reference: Optional[str] = None


class ReviewCategory(BaseModel):
    name: str
    score: int = Field(..., ge=0, le=100)
    issue_count: int
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    mode: Literal["dual", "single"]
    source_text: Optional[str] = None
    translated_text: str
    target_language: str
    genre: Optional[str] = None
    cultural_sphere: Optional[str] = None
    audience_type: Optional[str] = None


class ReviewResult(BaseModel):
    review_id: uuid.UUID
    mode: Literal["dual", "single"]
    overall_score: int = Field(..., ge=0, le=100)
    target_language: str
    audience_baseline: str
    categories: list[ReviewCategory]
    summary: str
    created_at: datetime
```

- [x] **Step 2: Verify import works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.schemas.review import ReviewRequest, ReviewResult; print('OK')"`

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/app/schemas/review.py
git commit -m "feat(backend): add review service schemas"
```

---

## Task 2: Backend — Review Prompts

**Files:**
- Modify: `backend/app/llm/prompts.py`

- [x] **Step 1: Append review prompts to prompts.py**

Add at the end of `backend/app/llm/prompts.py`:

```python
DUAL_REVIEW_PROMPT = """你是一位资深国际传播审校专家。请对照下面的中文原文和外文译文，从以下四个维度进行审校分析，指出译文中的问题并给出修改建议。

审校维度：
1. 术语准确性（terminology）：政治话语专有术语、政策文件固定译法是否准确、是否缺少必要的注释
2. 文化适配（cultural）：译文表达在目标受众文化中是否会产生负面联想或误读
3. 表达清晰度（clarity）：是否存在歧义、术语堆砌、过度直译导致难以理解
4. 叙事逻辑（narrative）：段落结构、因果链、论证顺序是否与原文一致（允许因受众偏好微调，但需标注）

输出要求：
- 以 JSON 格式返回
- overall_score：总体评分（0-100）
- summary：一段中文摘要（100字以内），概括主要问题和建议
- categories：按四个维度分类，每个维度包含 name（"术语准确性"/"文化适配"/"表达清晰度"/"叙事逻辑"）、score（0-100）和 issues 列表
- 每个 issue 必须包含：
  - category：分类标识（terminology / cultural / clarity / narrative）
  - severity："low"、"medium"、"high"
  - span：{"start": 字符偏移, "end": 字符偏移, "text": "译文中的对应文本"}
  - original：译文中需要修改的原文片段
  - suggestion：修改建议
  - explanation：为什么需要修改（中文，50字以内）
  - source_reference：对应的中文原文片段（如有）

原文中文：
{source_text}

译文（{target_language}）：
{translated_text}

目标受众：{audience}（{cultural_sphere}文化圈）

只返回 JSON，不要包含其他文本。"""

SINGLE_REVIEW_PROMPT = """你是一位资深国际传播审校专家。请对下面的外文译文进行独立诊断，假设该译文已经发布给目标受众，请评估其传播效果和潜在风险。

诊断维度：
1. 受众接受度（cultural）：目标受众是否会产生误读、负面联想或认知偏差
2. 表达清晰度（clarity）：是否存在歧义、术语滥用、句子过长、逻辑跳跃
3. 传播效果优化（narrative）：如何调整表达以提升说服力和可读性
4. 文化风险（terminology）：哪些表达在目标文化中是高风险的，建议如何规避

输出要求：
- 以 JSON 格式返回，结构与双模式相同
- 单模式时 source_reference 字段可为 null
- overall_score：总体评分（0-100），基于受众接受度和表达清晰度综合评估
- categories：按四个维度分类，每个维度包含 name、score（0-100）和 issues 列表
- 每个 issue 必须包含：
  - category：cultural / clarity / narrative / terminology
  - severity："low"、"medium"、"high"
  - span：{"start": 字符偏移, "end": 字符偏移, "text": "译文中的对应文本"}
  - original：译文中需要修改的片段
  - suggestion：修改建议
  - explanation：为什么需要修改（中文，50字以内）
  - source_reference：null

译文（{target_language}）：
{translated_text}

目标受众：{audience}（{cultural_sphere}文化圈）

只返回 JSON，不要包含其他文本。"""
```

- [x] **Step 2: Verify import works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.llm.prompts import DUAL_REVIEW_PROMPT, SINGLE_REVIEW_PROMPT; print('OK')"`

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/app/llm/prompts.py
git commit -m "feat(backend): add dual and single review prompts"
```

---

## Task 3: Backend — ReviewService

**Files:**
- Create: `backend/app/services/review.py`

- [x] **Step 1: Write ReviewService**

Create `backend/app/services/review.py`:

```python
import json
import logging
import uuid
from datetime import datetime

from app.llm.bailian import bailian_client
from app.llm.prompts import DUAL_REVIEW_PROMPT, SINGLE_REVIEW_PROMPT
from app.schemas.review import ReviewCategory, ReviewIssue, ReviewResult

logger = logging.getLogger(__name__)


class ReviewService:
    """Generate review analysis for published translation content."""

    async def dual_review(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        audience: str,
        cultural_sphere: str,
    ) -> ReviewResult:
        prompt = DUAL_REVIEW_PROMPT.format(
            source_text=source_text,
            translated_text=translated_text,
            target_language=target_language,
            audience=audience,
            cultural_sphere=cultural_sphere,
        )
        return await self._call_llm(prompt, "dual", target_language, translated_text)

    async def single_review(
        self,
        translated_text: str,
        target_language: str,
        audience: str,
        cultural_sphere: str,
    ) -> ReviewResult:
        prompt = SINGLE_REVIEW_PROMPT.format(
            translated_text=translated_text,
            target_language=target_language,
            audience=audience,
            cultural_sphere=cultural_sphere,
        )
        return await self._call_llm(prompt, "single", target_language, translated_text)

    async def _call_llm(
        self,
        prompt: str,
        mode: str,
        target_language: str,
        translated_text: str,
    ) -> ReviewResult:
        messages = [{"role": "user", "content": prompt}]
        try:
            result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
            content = result["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(content)

            categories = []
            for cat_data in data.get("categories", []):
                issues = []
                for issue_data in cat_data.get("issues", []):
                    span = issue_data.get("span")
                    if span and isinstance(span, dict):
                        span = {
                            "start": span.get("start", 0),
                            "end": span.get("end", 0),
                            "text": span.get("text", ""),
                        }
                    issues.append(
                        ReviewIssue(
                            category=issue_data.get("category", "clarity"),
                            severity=issue_data.get("severity", "low"),
                            span=span,
                            original=issue_data.get("original", ""),
                            suggestion=issue_data.get("suggestion", ""),
                            explanation=issue_data.get("explanation", ""),
                            source_reference=issue_data.get("source_reference"),
                        )
                    )
                categories.append(
                    ReviewCategory(
                        name=cat_data.get("name", "未分类"),
                        score=min(100, max(0, int(cat_data.get("score", 0)))),
                        issue_count=len(issues),
                        issues=issues,
                    )
                )

            # Validate spans: clamp to translated_text length
            for cat in categories:
                for issue in cat.issues:
                    if issue.span:
                        issue.span["start"] = max(0, min(issue.span["start"], len(translated_text)))
                        issue.span["end"] = max(issue.span["start"], min(issue.span["end"], len(translated_text)))

            return ReviewResult(
                review_id=uuid.uuid4(),
                mode=mode,
                overall_score=min(100, max(0, int(data.get("overall_score", 0)))),
                target_language=target_language,
                audience_baseline=f"{cultural_sphere}_{audience}",
                categories=categories,
                summary=data.get("summary", ""),
                created_at=datetime.utcnow(),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Review parsing failed: {e}")
            return ReviewResult(
                review_id=uuid.uuid4(),
                mode=mode,
                overall_score=0,
                target_language=target_language,
                audience_baseline="unknown",
                categories=[],
                summary="审校分析失败，请重试。",
                created_at=datetime.utcnow(),
            )


review_service = ReviewService()
```

Note: The `cultural_sphere` and `audience` variables used in `_call_llm` need to be captured. Since they are method-local, we need to adjust. Actually looking at the code, `_call_llm` doesn't receive `cultural_sphere` and `audience`. Let me fix this — the `_call_llm` signature needs them.

Actually wait, in the current code `_call_llm` doesn't receive `cultural_sphere` and `audience`, but `ReviewResult` creation uses them. Let me fix this:

The correct `_call_llm` should take `audience_baseline: str` instead:

```python
    async def _call_llm(
        self,
        prompt: str,
        mode: str,
        target_language: str,
        translated_text: str,
        audience_baseline: str,
    ) -> ReviewResult:
        ...
            return ReviewResult(
                ...
                audience_baseline=audience_baseline,
                ...
            )
```

And update callers:
```python
        return await self._call_llm(
            prompt, "dual", target_language, translated_text,
            f"{cultural_sphere}_{audience}"
        )
```

Let me write this correctly.

- [x] **Step 2: Corrected ReviewService with proper _call_llm signature**

Create `backend/app/services/review.py` with the corrected code:

```python
import json
import logging
import uuid
from datetime import datetime

from app.llm.bailian import bailian_client
from app.llm.prompts import DUAL_REVIEW_PROMPT, SINGLE_REVIEW_PROMPT
from app.schemas.review import ReviewCategory, ReviewIssue, ReviewResult

logger = logging.getLogger(__name__)


class ReviewService:
    """Generate review analysis for published translation content."""

    async def dual_review(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        audience: str,
        cultural_sphere: str,
    ) -> ReviewResult:
        prompt = DUAL_REVIEW_PROMPT.format(
            source_text=source_text,
            translated_text=translated_text,
            target_language=target_language,
            audience=audience,
            cultural_sphere=cultural_sphere,
        )
        return await self._call_llm(
            prompt, "dual", target_language, translated_text,
            f"{cultural_sphere}_{audience}"
        )

    async def single_review(
        self,
        translated_text: str,
        target_language: str,
        audience: str,
        cultural_sphere: str,
    ) -> ReviewResult:
        prompt = SINGLE_REVIEW_PROMPT.format(
            translated_text=translated_text,
            target_language=target_language,
            audience=audience,
            cultural_sphere=cultural_sphere,
        )
        return await self._call_llm(
            prompt, "single", target_language, translated_text,
            f"{cultural_sphere}_{audience}"
        )

    async def _call_llm(
        self,
        prompt: str,
        mode: str,
        target_language: str,
        translated_text: str,
        audience_baseline: str,
    ) -> ReviewResult:
        messages = [{"role": "user", "content": prompt}]
        try:
            result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
            content = result["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(content)

            categories = []
            for cat_data in data.get("categories", []):
                issues = []
                for issue_data in cat_data.get("issues", []):
                    span_raw = issue_data.get("span")
                    span = None
                    if span_raw and isinstance(span_raw, dict):
                        span = {
                            "start": span_raw.get("start", 0),
                            "end": span_raw.get("end", 0),
                            "text": span_raw.get("text", ""),
                        }
                    issues.append(
                        ReviewIssue(
                            category=issue_data.get("category", "clarity"),
                            severity=issue_data.get("severity", "low"),
                            span=span,
                            original=issue_data.get("original", ""),
                            suggestion=issue_data.get("suggestion", ""),
                            explanation=issue_data.get("explanation", ""),
                            source_reference=issue_data.get("source_reference"),
                        )
                    )
                categories.append(
                    ReviewCategory(
                        name=cat_data.get("name", "未分类"),
                        score=min(100, max(0, int(cat_data.get("score", 0)))),
                        issue_count=len(issues),
                        issues=issues,
                    )
                )

            # Validate spans: clamp to translated_text length
            for cat in categories:
                for issue in cat.issues:
                    if issue.span:
                        issue.span["start"] = max(0, min(issue.span["start"], len(translated_text)))
                        issue.span["end"] = max(issue.span["start"], min(issue.span["end"], len(translated_text)))

            return ReviewResult(
                review_id=uuid.uuid4(),
                mode=mode,
                overall_score=min(100, max(0, int(data.get("overall_score", 0)))),
                target_language=target_language,
                audience_baseline=audience_baseline,
                categories=categories,
                summary=data.get("summary", ""),
                created_at=datetime.utcnow(),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Review parsing failed: {e}")
            return ReviewResult(
                review_id=uuid.uuid4(),
                mode=mode,
                overall_score=0,
                target_language=target_language,
                audience_baseline=audience_baseline,
                categories=[],
                summary="审校分析失败，请重试。",
                created_at=datetime.utcnow(),
            )


review_service = ReviewService()
```

- [x] **Step 3: Verify import works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.services.review import review_service; print('OK')"`

Expected: `OK`

- [x] **Step 4: Commit**

```bash
git add backend/app/services/review.py
git commit -m "feat(backend): add ReviewService with dual/single review support"
```

---

## Task 4: Backend — Reviews API Router

**Files:**
- Create: `backend/app/api/reviews.py`

- [x] **Step 1: Write the router**

Create `backend/app/api/reviews.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.review import ReviewRequest, ReviewResult
from app.services.review import review_service

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResult, status_code=status.HTTP_200_OK)
async def create_review(
    body: ReviewRequest,
    user: User = Depends(get_current_user),
):
    if body.mode == "dual":
        if not body.source_text:
            raise HTTPException(status_code=400, detail="对照审校模式需要提供原文")
        return await review_service.dual_review(
            source_text=body.source_text,
            translated_text=body.translated_text,
            target_language=body.target_language,
            audience=body.audience_type or "general_public",
            cultural_sphere=body.cultural_sphere or "western_english",
        )
    else:
        return await review_service.single_review(
            translated_text=body.translated_text,
            target_language=body.target_language,
            audience=body.audience_type or "general_public",
            cultural_sphere=body.cultural_sphere or "western_english",
        )
```

- [x] **Step 2: Verify import works**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.api.reviews import router; print('OK')"`

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/app/api/reviews.py
git commit -m "feat(backend): add reviews API router"
```

---

## Task 5: Backend — Register Router

**Files:**
- Modify: `backend/app/main.py`

- [x] **Step 1: Add import and registration**

In `backend/app/main.py`, add after line 7:

```python
from app.api.reviews import router as reviews_router
```

And after line 20:

```python
app.include_router(reviews_router)
```

The full file should look like:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.reviews import router as reviews_router
from app.api.upload import router as upload_router
from app.api.ws import router as ws_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="CulturalBridge API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(reviews_router)
app.include_router(upload_router)
app.include_router(ws_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [x] **Step 2: Verify backend starts**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.main import app; print('OK')"`

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): register reviews router"
```

---

## Task 6: Frontend — API Client

**Files:**
- Modify: `frontend/lib/api-client.ts`

- [x] **Step 1: Add postReview method** (偏离 — 未包含 genre 参数，前端从不发送)

Add after the existing `post` method (after line 54):

```typescript
  async postReview(body: {
    mode: "dual" | "single";
    source_text?: string;
    translated_text: string;
    target_language: string;
    genre?: string;
    cultural_sphere?: string;
    audience_type?: string;
  }) {
    const res = await this.request("/api/reviews", { method: "POST", body: JSON.stringify(body) });
    return res.json();
  }
```

The full `ApiClient` class after modification:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("token", token);
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("token");
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
    }
  }

  private async request(path: string, options: RequestInit = {}) {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `API error: ${res.status}`);
    }
    return res;
  }

  async post(path: string, body: unknown) {
    const res = await this.request(path, { method: "POST", body: JSON.stringify(body) });
    return res.json();
  }

  async postReview(body: {
    mode: "dual" | "single";
    source_text?: string;
    translated_text: string;
    target_language: string;
    genre?: string;
    cultural_sphere?: string;
    audience_type?: string;
  }) {
    const res = await this.request("/api/reviews", { method: "POST", body: JSON.stringify(body) });
    return res.json();
  }

  async get(path: string) {
    const res = await this.request(path, { method: "GET" });
    return res.json();
  }

  async delete(path: string) {
    await this.request(path, { method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors related to `api-client.ts`.

- [x] **Step 3: Commit**

```bash
git add frontend/lib/api-client.ts
git commit -m "feat(frontend): add postReview method to ApiClient"
```

---

## Task 7: Frontend — Review Store

**Files:**
- Create: `frontend/stores/review-store.ts`

- [x] **Step 1: Write the store**

Create `frontend/stores/review-store.ts`:

```typescript
import { create } from "zustand";

export type ReviewMode = "dual" | "single";
export type ReviewSeverity = "low" | "medium" | "high";

export interface ReviewIssue {
  category: string;
  severity: ReviewSeverity;
  span: { start: number; end: number; text: string } | null;
  original: string;
  suggestion: string;
  explanation: string;
  source_reference: string | null;
}

export interface ReviewCategory {
  name: string;
  score: number;
  issue_count: number;
  issues: ReviewIssue[];
}

export interface ReviewResult {
  review_id: string;
  mode: ReviewMode;
  overall_score: number;
  target_language: string;
  audience_baseline: string;
  categories: ReviewCategory[];
  summary: string;
  created_at: string;
}

interface ReviewState {
  mode: ReviewMode;
  sourceText: string;
  translatedText: string;
  targetLanguage: string;
  genre: string;
  culturalSphere: string;
  audienceType: string;
  result: ReviewResult | null;
  highlightedIssueIndex: number | null;
  isLoading: boolean;
  error: string | null;

  setMode: (mode: ReviewMode) => void;
  setSourceText: (text: string) => void;
  setTranslatedText: (text: string) => void;
  setTargetLanguage: (lang: string) => void;
  setGenre: (genre: string) => void;
  setCulturalSphere: (sphere: string) => void;
  setAudienceType: (audience: string) => void;
  setResult: (result: ReviewResult | null) => void;
  setHighlightedIssue: (index: number | null) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  mode: "dual" as ReviewMode,
  sourceText: "",
  translatedText: "",
  targetLanguage: "en-GB",
  genre: "political",
  culturalSphere: "western_english",
  audienceType: "government",
  result: null as ReviewResult | null,
  highlightedIssueIndex: null as number | null,
  isLoading: false,
  error: null as string | null,
};

export const useReviewStore = create<ReviewState>((set) => ({
  ...initialState,
  setMode: (mode) => set({ mode }),
  setSourceText: (text) => set({ sourceText: text }),
  setTranslatedText: (text) => set({ translatedText: text }),
  setTargetLanguage: (lang) => set({ targetLanguage: lang }),
  setGenre: (genre) => set({ genre }),
  setCulturalSphere: (sphere) => set({ culturalSphere: sphere }),
  setAudienceType: (audience) => set({ audienceType: audience }),
  setResult: (result) => set({ result }),
  setHighlightedIssue: (index) => set({ highlightedIssueIndex: index }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}));
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors related to `review-store.ts`.

- [x] **Step 3: Commit**

```bash
git add frontend/stores/review-store.ts
git commit -m "feat(frontend): add review store with mode/input/result state"
```

---

## Task 8: Frontend — Review Page

**Files:**
- Create: `frontend/app/(main)/review/page.tsx`

- [x] **Step 1: Create the page component**

Create `frontend/app/(main)/review/page.tsx`:

```tsx
"use client";

import { ReviewInputPanel } from "@/components/review/review-input-panel";
import { ReviewResultPanel } from "@/components/review/review-result-panel";
import { ReviewReportPanel } from "@/components/review/review-report-panel";
import { useReviewStore } from "@/stores/review-store";

export default function ReviewPage() {
  const result = useReviewStore((s) => s.result);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col gap-3 p-4">
      <div className="flex flex-1 gap-3 overflow-hidden">
        <div className="w-[42%] min-w-[320px] overflow-hidden">
          <ReviewInputPanel />
        </div>
        <div className="flex flex-1 flex-col gap-3 overflow-hidden">
          <ReviewResultPanel />
        </div>
      </div>
      {result && (
        <div className="shrink-0">
          <ReviewReportPanel />
        </div>
      )}
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors (component files will be created in subsequent tasks).

- [x] **Step 3: Commit**

```bash
git add frontend/app/(main)/review/page.tsx
git commit -m "feat(frontend): add review page shell"
```

---

## Task 9: Frontend — Review Input Panel

**Files:**
- Create: `frontend/components/review/review-input-panel.tsx`

- [x] **Step 1: Write the component**

Create `frontend/components/review/review-input-panel.tsx`:

```tsx
"use client";

import { useReviewStore } from "@/stores/review-store";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

const AVAILABLE_LANGUAGES = [
  { code: "en-GB", label: "英语(英)" },
  { code: "de-DE", label: "德语" },
  { code: "ja-JP", label: "日语" },
  { code: "es-ES", label: "西班牙语" },
  { code: "fr-FR", label: "法语" },
];

const GENRES = [
  { value: "political", label: "政治话语" },
  { value: "news", label: "新闻稿" },
  { value: "policy", label: "政策文件" },
  { value: "brand", label: "品牌传播" },
];

const SPHERES = [
  { value: "western_english", label: "欧美英语圈" },
  { value: "european_continental", label: "欧洲大陆" },
  { value: "islamic_middle_east", label: "伊斯兰中东" },
  { value: "east_asian_confucian", label: "东亚儒家" },
  { value: "latin_american", label: "拉美" },
  { value: "russian_sphere", label: "俄语圈" },
  { value: "south_asian", label: "南亚" },
  { value: "african", label: "非洲" },
];

const AUDIENCES = [
  { value: "general_public", label: "公众" },
  { value: "media", label: "媒体" },
  { value: "government", label: "政府" },
  { value: "academic", label: "学术" },
  { value: "business", label: "企业" },
  { value: "diaspora_chinese", label: "海外华人" },
];

export function ReviewInputPanel() {
  const store = useReviewStore();

  async function handleSubmit() {
    if (!store.translatedText.trim()) return;
    if (store.mode === "dual" && !store.sourceText.trim()) return;

    store.setIsLoading(true);
    store.setError(null);
    store.setResult(null);

    try {
      const data = await apiClient.postReview({
        mode: store.mode,
        source_text: store.mode === "dual" ? store.sourceText : undefined,
        translated_text: store.translatedText,
        target_language: store.targetLanguage,
        genre: store.genre,
        cultural_sphere: store.culturalSphere,
        audience_type: store.audienceType,
      });
      store.setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "审校请求失败";
      store.setError(message);
    } finally {
      store.setIsLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 rounded-md border border-border bg-white p-4">
      <h2 className="text-sm font-semibold text-foreground">审校输入</h2>

      {/* Mode selector */}
      <div className="flex gap-3 text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="review-mode"
            checked={store.mode === "dual"}
            onChange={() => store.setMode("dual")}
            className="h-3.5 w-3.5 accent-teal"
          />
          <span>对照审校</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="review-mode"
            checked={store.mode === "single"}
            onChange={() => store.setMode("single")}
            className="h-3.5 w-3.5 accent-teal"
          />
          <span>独立诊断</span>
        </label>
      </div>

      {/* Source text */}
      <div className={store.mode === "single" ? "hidden" : "flex flex-col gap-1"}>
        <label className="text-xs font-medium text-muted-foreground">原文（中文）</label>
        <textarea
          value={store.sourceText}
          onChange={(e) => store.setSourceText(e.target.value)}
          placeholder="粘贴中文原文..."
          className="h-32 resize-none rounded-md border border-border bg-white p-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-teal focus:outline-none"
        />
      </div>

      {/* Translated text */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">译文（目标语言）</label>
        <textarea
          value={store.translatedText}
          onChange={(e) => store.setTranslatedText(e.target.value)}
          placeholder="粘贴外文译文..."
          className="h-40 resize-none rounded-md border border-border bg-white p-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-teal focus:outline-none"
        />
      </div>

      {/* Parameters */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">目标语言</span>
          <select
            value={store.targetLanguage}
            onChange={(e) => store.setTargetLanguage(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {AVAILABLE_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">文体</span>
          <select
            value={store.genre}
            onChange={(e) => store.setGenre(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {GENRES.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">文化圈</span>
          <select
            value={store.culturalSphere}
            onChange={(e) => store.setCulturalSphere(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {SPHERES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">受众</span>
          <select
            value={store.audienceType}
            onChange={(e) => store.setAudienceType(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {AUDIENCES.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {store.error && (
        <div className="rounded bg-red-50 px-3 py-2 text-xs text-red-600">
          {store.error}
        </div>
      )}

      {/* Submit */}
      <Button
        onClick={handleSubmit}
        disabled={store.isLoading || !store.translatedText.trim()}
        className="mt-auto h-9 text-sm"
      >
        {store.isLoading ? "审校中..." : "开始审校"}
      </Button>
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors (result panel components will be created in subsequent tasks).

- [x] **Step 3: Commit**

```bash
git add frontend/components/review/review-input-panel.tsx
git commit -m "feat(frontend): add review input panel with mode switch and params"
```

---

## Task 10: Frontend — Score Badge

**Files:**
- Create: `frontend/components/review/score-badge.tsx`

- [x] **Step 1: Write the component**

Create `frontend/components/review/score-badge.tsx`:

```tsx
const SCORE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  excellent: { bg: "#DCFCE7", text: "#166534", label: "优秀" },
  good: { bg: "#DBEAFE", text: "#1E40AF", label: "良好" },
  fair: { bg: "#FEF9C3", text: "#854D0E", label: "一般" },
  poor: { bg: "#FFEDD5", text: "#9A3412", label: "待改进" },
  critical: { bg: "#FEE2E2", text: "#991B1B", label: "需重写" },
};

function getScoreGrade(score: number) {
  if (score >= 90) return "excellent";
  if (score >= 75) return "good";
  if (score >= 60) return "fair";
  if (score >= 40) return "poor";
  return "critical";
}

export function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const grade = getScoreGrade(score);
  const style = SCORE_COLORS[grade];

  const sizeClasses = {
    sm: "text-lg w-14 h-14",
    md: "text-2xl w-20 h-20",
    lg: "text-4xl w-28 h-28",
  };

  return (
    <div
      className={`flex flex-col items-center justify-center rounded-full font-bold ${sizeClasses[size]}`}
      style={{ background: style.bg, color: style.text }}
    >
      <span>{score}</span>
      {size !== "sm" && <span className="text-[10px] font-normal">{style.label}</span>}
    </div>
  );
}

export function CategoryScoreBar({ name, score }: { name: string; score: number }) {
  const grade = getScoreGrade(score);
  const style = SCORE_COLORS[grade];

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 text-muted-foreground">{name}</span>
      <div className="h-2 flex-1 rounded-full bg-gray-100">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${score}%`, background: style.text }}
        />
      </div>
      <span className="w-8 text-right font-medium" style={{ color: style.text }}>{score}</span>
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors.

- [x] **Step 3: Commit**

```bash
git add frontend/components/review/score-badge.tsx
git commit -m "feat(frontend): add ScoreBadge and CategoryScoreBar components"
```

---

## Task 11: Frontend — Issue Card

**Files:**
- Create: `frontend/components/review/issue-card.tsx`

- [x] **Step 1: Write the component**

Create `frontend/components/review/issue-card.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { ReviewIssue } from "@/stores/review-store";

const SEVERITY_STYLES: Record<string, { icon: string; badgeBg: string; badgeText: string; borderColor: string }> = {
  high: { icon: "🔴", badgeBg: "#FEE2E2", badgeText: "#DC2626", borderColor: "#FCA5A5" },
  medium: { icon: "🟠", badgeBg: "#FFEDD5", badgeText: "#C2410C", borderColor: "#FDBA74" },
  low: { icon: "🟡", badgeBg: "#FEF9C3", badgeText: "#A16207", borderColor: "#FDE68A" },
};

const CATEGORY_LABELS: Record<string, string> = {
  terminology: "术语",
  cultural: "文化",
  clarity: "清晰",
  narrative: "叙事",
};

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  terminology: { bg: "#E0F2FE", text: "#0369A1" },
  cultural: { bg: "#FCE7F3", text: "#BE185D" },
  clarity: { bg: "#ECFCCB", text: "#3F6212" },
  narrative: { bg: "#F3E8FF", text: "#7C3AED" },
};

export function IssueCard({
  issue,
  index,
  isHighlighted,
  onHover,
  onLeave,
  onClick,
}: {
  issue: ReviewIssue;
  index: number;
  isHighlighted: boolean;
  onHover: (index: number) => void;
  onLeave: () => void;
  onClick: (index: number) => void;
}) {
  const severity = SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.low;
  const category = CATEGORY_LABELS[issue.category] || issue.category;
  const catColor = CATEGORY_COLORS[issue.category] || { bg: "#F1F5F9", text: "#475569" };
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-md border p-2.5 transition-colors duration-150 cursor-pointer"
      style={{
        background: isHighlighted ? severity.badgeBg : "white",
        borderColor: isHighlighted ? severity.borderColor : "#E2E8F0",
      }}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={onLeave}
      onClick={() => onClick(index)}
    >
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        <span
          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
          style={{ background: severity.badgeBg, color: severity.badgeText }}
        >
          {severity.icon} {issue.severity === "high" ? "高风险" : issue.severity === "medium" ? "中风险" : "低风险"}
        </span>
        <span
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium"
          style={{ background: catColor.bg, color: catColor.text }}
        >
          {category}
        </span>
        {issue.source_reference && (
          <span className="text-[10px] text-muted-foreground truncate max-w-[150px]">
            对应：「{issue.source_reference}」
          </span>
        )}
      </div>

      <div className="flex items-start gap-1 text-xs mb-1">
        <span className="font-medium text-slate-700 shrink-0">原文：</span>
        <span className="text-slate-500 line-through">{issue.original}</span>
      </div>
      <div className="flex items-start gap-1 text-xs mb-1">
        <span className="font-medium text-teal-700 shrink-0">建议：</span>
        <span className="text-teal-600">{issue.suggestion}</span>
      </div>

      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        className="text-[10px] text-muted-foreground hover:text-foreground mt-0.5"
      >
        {expanded ? "收起" : "查看说明"}
      </button>

      {expanded && (
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
          {issue.explanation}
        </p>
      )}
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors.

- [x] **Step 3: Commit**

```bash
git add frontend/components/review/issue-card.tsx
git commit -m "feat(frontend): add IssueCard component with severity/category badges"
```

---

## Task 12: Frontend — Review Result Panel

**Files:**
- Create: `frontend/components/review/review-result-panel.tsx`

- [x] **Step 1: Write the component**

Create `frontend/components/review/review-result-panel.tsx`:

```tsx
"use client";

import { useMemo, useRef, useCallback } from "react";
import { useReviewStore } from "@/stores/review-store";
import { ScoreBadge, CategoryScoreBar } from "./score-badge";
import { IssueCard } from "./issue-card";

const MARK_STYLES: Record<string, { border: string; bg: string; bgHover: string }> = {
  terminology: { border: "#0369A1", bg: "rgba(3,105,161,0.08)", bgHover: "rgba(3,105,161,0.20)" },
  cultural: { border: "#BE185D", bg: "rgba(190,24,93,0.08)", bgHover: "rgba(190,24,93,0.20)" },
  clarity: { border: "#3F6212", bg: "rgba(63,98,18,0.08)", bgHover: "rgba(63,98,18,0.20)" },
  narrative: { border: "#7C3AED", bg: "rgba(124,58,237,0.08)", bgHover: "rgba(124,58,237,0.20)" },
};

function buildSpans(translatedText: string, issues: { index: number; category: string; span: { start: number; end: number; text: string } | null }[]) {
  const valid = issues
    .filter((i) => i.span && i.span.start >= 0 && i.span.end > i.span.start)
    .map((i) => ({
      index: i.index,
      category: i.category,
      start: i.span!.start,
      end: i.span!.end,
      text: i.span!.text,
    }))
    .sort((a, b) => a.start - b.start);

  // Remove overlapping spans (keep first)
  const deduped: typeof valid = [];
  let lastEnd = -1;
  for (const span of valid) {
    if (span.start >= lastEnd) {
      deduped.push(span);
      lastEnd = span.end;
    }
  }
  return deduped;
}

export function ReviewResultPanel() {
  const result = useReviewStore((s) => s.result);
  const isLoading = useReviewStore((s) => s.isLoading);
  const highlightedIndex = useReviewStore((s) => s.highlightedIssueIndex);
  const setHighlighted = useReviewStore((s) => s.setHighlightedIssue);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());

  const allIssues = useMemo(() => {
    if (!result) return [];
    let index = 0;
    return result.categories.flatMap((cat) =>
      cat.issues.map((issue) => ({ ...issue, index: index++, category: issue.category }))
    );
  }, [result]);

  const spans = useMemo(() => {
    if (!result) return [];
    const issues = allIssues.map((i, idx) => ({ index: idx, category: i.category, span: i.span }));
    return buildSpans(result.translated_text || "", issues);
  }, [result, allIssues]);

  const handleHover = useCallback((index: number) => setHighlighted(index), [setHighlighted]);
  const handleLeave = useCallback(() => setHighlighted(null), [setHighlighted]);
  const handleClick = useCallback((index: number) => {
    const el = markRefs.current.get(index);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border bg-white">
        <div className="text-sm text-muted-foreground">正在进行审校分析...</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border bg-white">
        <div className="text-sm text-muted-foreground">在左侧输入内容并点击「开始审校」</div>
      </div>
    );
  }

  const content = useMemo(() => {
    const text = result.translated_text || "";
    if (spans.length === 0) {
      return <span className="whitespace-pre-wrap">{text}</span>;
    }

    const parts: React.ReactNode[] = [];
    let cursor = 0;

    for (const span of spans) {
      if (span.start > cursor) {
        parts.push(<span key={`t-${cursor}`}>{text.slice(cursor, span.start)}</span>);
      }

      const style = MARK_STYLES[span.category] || MARK_STYLES.clarity;
      const isHighlighted = highlightedIndex === span.index;

      parts.push(
        <mark
          key={`m-${span.index}`}
          ref={(el) => { if (el) markRefs.current.set(span.index, el); }}
          className="cursor-pointer rounded-sm pr-1 pl-1.5 transition-colors duration-150"
          style={{
            borderLeft: `3px solid ${style.border}`,
            background: isHighlighted ? style.bgHover : style.bg,
            fontWeight: isHighlighted ? 600 : 500,
            color: "inherit",
          }}
          onMouseEnter={() => handleHover(span.index)}
          onMouseLeave={handleLeave}
        >
          {span.text}
        </mark>
      );

      cursor = span.end;
    }

    if (cursor < text.length) {
      parts.push(<span key={`t-${cursor}`}>{text.slice(cursor)}</span>);
    }

    return parts;
  }, [result?.translated_text, spans, highlightedIndex, handleHover, handleLeave]);

  return (
    <div className="flex h-full flex-col gap-3 overflow-hidden">
      {/* Score overview */}
      <div className="shrink-0 rounded-md border border-border bg-white p-4">
        <div className="flex items-center gap-4">
          <ScoreBadge score={result.overall_score} size="md" />
          <div className="flex flex-1 flex-col gap-1.5">
            {result.categories.map((cat) => (
              <CategoryScoreBar key={cat.name} name={cat.name} score={cat.score} />
            ))}
          </div>
        </div>
      </div>

      {/* Inline annotated text */}
      <div className="flex-1 min-h-0 overflow-y-auto rounded-md border border-border bg-white p-3 text-sm leading-relaxed">
        {content}
      </div>

      {/* Issue cards */}
      <div className="shrink-0 flex flex-col gap-1.5 overflow-y-auto max-h-[200px]">
        {allIssues.map((issue, idx) => (
          <IssueCard
            key={idx}
            issue={issue}
            index={idx}
            isHighlighted={highlightedIndex === idx}
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

Expected: No errors.

- [x] **Step 3: Commit**

```bash
git add frontend/components/review/review-result-panel.tsx
git commit -m "feat(frontend): add review result panel with inline marks and issue cards"
```

---

## Task 13: Frontend — Review Report Panel

**Files:**
- Create: `frontend/components/review/review-report-panel.tsx`

- [x] **Step 1: Write the component**

Create `frontend/components/review/review-report-panel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useReviewStore } from "@/stores/review-store";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";

export function ReviewReportPanel() {
  const result = useReviewStore((s) => s.result);
  const [collapsed, setCollapsed] = useState(false);

  if (!result) return null;

  const handleExport = () => {
    const lines: string[] = [];
    lines.push(`# 审校报告`);
    lines.push(`""`);
    lines.push(`**总体评分：** ${result.overall_score}/100`);
    lines.push(`**审校模式：** ${result.mode === "dual" ? "对照审校" : "独立诊断"}`);
    lines.push(`**目标语言：** ${result.target_language}`);
    lines.push(`**受众基准：** ${result.audience_baseline}`);
    lines.push(`""`);
    lines.push(`## 审校摘要`);
    lines.push(result.summary);
    lines.push(`""`);
    lines.push(`## 分类评分`);
    for (const cat of result.categories) {
      lines.push(`- ${cat.name}：${cat.score}/100（${cat.issue_count} 处问题）`);
    }
    lines.push(`""`);
    lines.push(`## 问题详情`);
    let idx = 1;
    for (const cat of result.categories) {
      for (const issue of cat.issues) {
        lines.push(`### 问题 ${idx}`);
        lines.push(`- **分类：** ${cat.name}`);
        lines.push(`- **严重级别：** ${issue.severity === "high" ? "高风险" : issue.severity === "medium" ? "中风险" : "低风险"}`);
        lines.push(`- **原文：** ${issue.original}`);
        lines.push(`- **建议：** ${issue.suggestion}`);
        lines.push(`- **说明：** ${issue.explanation}`);
        if (issue.source_reference) {
          lines.push(`- **对应原文：** ${issue.source_reference}`);
        }
        lines.push(`""`);
        idx++;
      }
    }

    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `审校报告_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rounded-md border border-border bg-white">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium hover:bg-gray-50"
      >
        <span>审校报告</span>
        {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
      </button>

      {!collapsed && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-3 text-sm leading-relaxed text-foreground">{result.summary}</p>

          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {result.categories.map((cat) => (
              <div key={cat.name} className="rounded border border-border p-2 text-center">
                <div className="text-xs text-muted-foreground">{cat.name}</div>
                <div className="text-lg font-semibold text-foreground">{cat.score}</div>
                <div className="text-[10px] text-muted-foreground">{cat.issue_count} 处问题</div>
              </div>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={handleExport}
          >
            <FileText className="mr-1 h-3.5 w-3.5" />
            导出 Markdown
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors.

- [x] **Step 3: Commit**

```bash
git add frontend/components/review/review-report-panel.tsx
git commit -m "feat(frontend): add review report panel with markdown export"
```

---

## Task 14: Frontend — Add Navigation Entry

**Files:**
- Modify: `frontend/app/(main)/layout.tsx`

- [x] **Step 1: Add "审校" nav link**

In `frontend/app/(main)/layout.tsx`, replace the `<nav>` section with:

```tsx
        <nav className="flex gap-4">
          <Link href="/workspace" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">工作台</Link>
          <Link href="/review" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">审校</Link>
        </nav>
```

The full file:

```tsx
"use client";

import Link from "next/link";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center gap-6 bg-teal-dark px-6 text-sm text-teal-lightest shadow-sm shadow-teal-dark/20">
        <Link href="/workspace" className="text-lg font-bold font-heading tracking-tight text-terracotta">
          CulturalBridge
        </Link>
        <nav className="flex gap-4">
          <Link href="/workspace" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">工作台</Link>
          <Link href="/review" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">审校</Link>
        </nav>
        <div className="ml-auto">
          <button
            onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }}
            className="text-teal-light hover:text-white cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
```

- [x] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors.

- [x] **Step 3: Commit**

```bash
git add frontend/app/(main)/layout.tsx
git commit -m "feat(frontend): add review nav link to main layout"
```

---

## Task 15: Build Verification

**Files:** None (verification only)

- [x] **Step 1: Verify frontend builds**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/frontend && npm run build 2>&1 | tail -20`

Expected: `✓ Compiled successfully` with no TypeScript errors.

- [x] **Step 2: Verify backend imports**

Run: `cd /Users/felixwang/devspace/cc-project/mca-translation/backend && python -c "from app.main import app; from app.api.reviews import router; print('OK')"`

Expected: `OK`

- [x] **Step 3: Start services and smoke test**

1. Start backend: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000/review
4. Verify:
   - 导航栏显示「审校」入口，点击进入审校页面
   - 左侧显示输入面板，包含模式切换（对照/独立）
   - 对照模式下显示原文+译文输入框，独立模式只显示译文
   - 参数选择器：目标语言、文体、文化圈、受众
   - 输入内容后点击「开始审校」，显示加载状态
   - 完成后右侧显示：总体评分徽章、四维度条形图、内联标注译文、问题卡片列表
   - Hover 问题卡片高亮对应内联标注
   - 点击问题卡片滚动定位到内联标注
   - 底部报告面板可折叠，点击「导出 Markdown」下载 .md 文件

- [x] **Step 4: Commit any fixes**

If smoke test revealed issues:
```bash
git add -A && git commit -m "fix: address review service smoke test issues"
```

---

## Self-Review Checklist

### 1. Spec coverage

| Spec section | Plan task |
|---|---|
| 双模式输入（对照/独立） | Task 9 (input panel) |
| 四维审校体系 | Task 2 (prompts), Task 3 (service) |
| 内联标注输出 | Task 12 (result panel) |
| 问题卡片 | Task 11 (issue card), Task 12 |
| 审校报告（可导出） | Task 13 (report panel) |
| 独立页面 + 导航 | Task 8, Task 14 |
| 评分颜色分级 | Task 10 (score badge) |
| 数据模型 | Task 1 (schemas) |
| API 端点 | Task 4 (router) |

All spec requirements covered. No gaps.

### 2. Placeholder scan

- No "TBD", "TODO", "implement later" found
- No vague "add error handling" or "write tests for the above" found
- No "Similar to Task N" references found
- All code blocks contain complete, copy-pasteable code

### 3. Type consistency

| Entity | Definition | Usage |
|---|---|---|
| `ReviewResult` | `backend/app/schemas/review.py` | API response + frontend store |
| `ReviewIssue` | `backend/app/schemas/review.py` + `frontend/stores/review-store.ts` | Service output, store, components |
| `ReviewCategory` | `backend/app/schemas/review.py` + `frontend/stores/review-store.ts` | Service output, store, components |
| `ReviewMode` | `"dual" \| "single"` | Request body, store, prompts |
| `severity` | `"low" \| "medium" \| "high"` | Schemas, store, components, prompts |

All types consistent across backend/frontend boundary.
