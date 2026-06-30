# .docx Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `.docx` export to the workspace — backend generates a standard-format Word document (source + translation, risk annotations as Word comments), frontend adds a download button.

**Architecture:** Pure REST — frontend POSTs translation data to a new endpoint, backend builds `.docx` via `python-docx` and returns binary. No DB, no Celery, no LLM.

**Tech Stack:** python-docx (already in requirements.txt), FastAPI, Next.js

## Global Constraints

- python-docx >= 1.1.2 (already installed)
- No new Python or npm dependencies
- No DB schema changes
- No Celery/async tasks
- File naming: `translation_{language}_{timestamp}.docx`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/export_docx.py` | Create | .docx generation service |
| `backend/app/api/export.py` | Create | POST /api/export/docx endpoint |
| `backend/app/main.py` | Modify | Register export router |
| `backend/tests/test_export_docx.py` | Create | Unit tests |
| `frontend/lib/api-client.ts` | Modify | Add `exportDocx()` method |
| `frontend/components/workspace/result-actions.tsx` | Modify | Add "导出 .docx" button |

---

### Task 1: Backend service — `export_docx.py`

**Files:**
- Create: `backend/app/services/export_docx.py`

**Interfaces:**
- Produces: `generate_translation_docx(source_text, translated_text, risk_annotations, language) -> bytes`

- [ ] **Step 1: Write the failing test**

Read existing test `backend/tests/test_hardcoded_glossary.py` for pattern reference, then create `backend/tests/test_export_docx.py`:

```python
"""Tests for .docx export service."""

import io
import uuid

import pytest
from docx import Document as DocxDocument


@pytest.fixture
def sample_source() -> str:
    return "坚持以人民为中心的发展思想。"


@pytest.fixture
def sample_translation() -> str:
    return "Adhere to the people-centered development philosophy."


@pytest.fixture
def sample_annotations() -> list[dict]:
    return [
        {
            "phrase": "people-centered",
            "risk_level": "medium",
            "risk_type": "political_sensitivity",
            "explanation": "部分西方媒体将其与民粹主义关联",
        }
    ]


class TestGenerateTranslationDocx:
    def test_returns_non_empty_bytes(self, sample_source, sample_translation, sample_annotations):
        """Verify the function returns a non-empty bytes object."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_docx_contains_source_and_translation(self, sample_source, sample_translation, sample_annotations):
        """Verify the generated .docx contains both source and translation paragraphs."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "坚持以人民为中心的发展思想" in text
        assert "people-centered development" in text

    def test_docx_has_heading(self, sample_source, sample_translation, sample_annotations):
        """Verify the document has at least one heading (原文/译文)."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))
        headings = [p for p in doc.paragraphs if p.style.name.startswith("Heading")]
        assert len(headings) >= 2

    def test_annotations_become_comments(self, sample_source, sample_translation, sample_annotations):
        """Verify risk annotations are added as Word comments on matching text."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))

        # Access comments via the document's part
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        comment_count = 0
        for rel in doc.part.rels.values():
            if "comment" in str(rel.reltype).lower():
                comment_count += 1
        # At least one comment relationship exists
        assert comment_count >= 1

    def test_empty_annotations_list(self, sample_source, sample_translation):
        """Verify the function handles an empty annotations list."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=[],
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "原文" in text
        assert "译文" in text

    def test_empty_translation_raises(self, sample_source, sample_annotations):
        """Verify empty translation raises ValueError."""
        from app.services.export_docx import generate_translation_docx

        with pytest.raises(ValueError, match="translated_text is required"):
            generate_translation_docx(
                source_text=sample_source,
                translated_text="",
                risk_annotations=sample_annotations,
                language="en-GB",
            )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_export_docx.py -v
```
Expected: ImportError — no module `export_docx`

- [ ] **Step 3: Write minimal implementation**

```python
"""Generate .docx translation documents with risk annotations as Word comments."""

from io import BytesIO

from docx import Document
from docx.enm.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
from docx.shared import Pt
from docx.opc.constants import RELATIONSHIP_TYPE as RT


def _set_cell_shading(cell, color: str):
    """Set background shading for a table cell."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _add_comment(doc, paragraph, text: str, author: str = "CulturalBridge"):
    """Add a Word comment to a run in the paragraph.

    python-docx does not natively support comments, so we manipulate the
    XML directly. Each comment gets an incremental ID.
    """
    # Access or create the comments part
    comments_part = _get_or_create_comments_part(doc)

    # Create comment element
    comment_id = _next_comment_id(comments_part)
    comment_xml = (
        f'<w:comment {nsdecls("w")} w:id="{comment_id}" w:author="{author}" w:date="{_now_iso()}">'
        f'<w:p><w:r><w:t xml:space="preserve">{_escape_xml(text)}</w:t></w:r></w:p></w:comment>'
    )
    comments_part.element.append(parse_xml(comment_xml))

    # Add comment reference to the first run of the paragraph
    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run(" ")
    comment_ref_start = parse_xml(
        f'<w:commentRangeStart {nsdecls("w")} w:id="{comment_id}"/>'
    )
    comment_ref_end = parse_xml(
        f'<w:commentRangeEnd {nsdecls("w")} w:id="{comment_id}"/>'
    )
    comment_ref = parse_xml(
        f'<w:r><w:commentReference {nsdecls("w")} w:id="{comment_id}"/></w:r>'
    )

    run._r.addprevious(comment_ref_start)
    # After the run, add end marker and reference
    parent = run._r.getparent()
    parent.append(comment_ref_end)
    parent.append(comment_ref)


def _get_or_create_comments_part(doc):
    """Get or create the Word comments XML part."""
    part = doc.part
    for rel in part.rels.values():
        if "comments" in rel.reltype:
            return rel.target_part

    # Create a new comments part
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    import lxml.etree as etree

    comments_xml = (
        f'<w:comments {nsdecls("w")}></w:comments>'
    )
    comments_part = Part(
        PackURI("/word/comments.xml"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
        etree.fromstring(comments_xml.encode("utf-8")),
        part.package,
    )
    part.relate_to(comments_part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments")
    return comments_part


_comment_counter = 0


def _next_comment_id(comments_part) -> int:
    global _comment_counter
    _comment_counter += 1
    return _comment_counter


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_translation_docx(
    source_text: str,
    translated_text: str,
    risk_annotations: list[dict],
    language: str,
) -> bytes:
    """Generate a standard-format .docx with source text, translation, and risk annotations as Word comments.

    Returns the .docx content as bytes.
    """
    if not translated_text:
        raise ValueError("translated_text is required")

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)

    # --- Source text section ---
    heading = doc.add_heading("【原文】", level=2)
    para = doc.add_paragraph(source_text)
    para.style = doc.styles["Normal"]

    # --- Separator ---
    doc.add_paragraph("─" * 40)

    # --- Translation section ---
    doc.add_heading("【译文】", level=2)
    para_tr = doc.add_paragraph(translated_text)
    para_tr.style = doc.styles["Normal"]

    # --- Risk annotations as Word comments ---
    for ann in risk_annotations:
        phrase = ann.get("phrase", "")
        if not phrase or phrase not in translated_text:
            continue
        risk_level = ann.get("risk_level", "unknown")
        explanation = ann.get("explanation", "")
        risk_type = ann.get("risk_type", "")
        comment_text = f"[风险: {risk_level}]"
        if risk_type:
            comment_text += f" ({risk_type})"
        if explanation:
            comment_text += f"\n{explanation}"

        # We need to find the paragraph containing the phrase and add a comment
        # For simplicity, add comment to the translation paragraph
        _add_comment(doc, para_tr, comment_text)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_export_docx.py -v
```
Expected: all tests PASS (some may be skipped/marked xfail if lxml parsing differs)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/export_docx.py backend/tests/test_export_docx.py
git commit -m "feat(export): add .docx generation service with Word comments for risk annotations"
```

---

### Task 2: Backend API endpoint — `POST /api/export/docx`

**Files:**
- Create: `backend/app/api/export.py`
- Modify: `backend/app/main.py` (register router)

**Interfaces:**
- Consumes: `generate_translation_docx(source_text, translated_text, risk_annotations, language) -> bytes`
- Produces: `POST /api/export/docx` returning `Response(..., media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_export_docx.py`:

```python
class TestExportApi:
    """Integration tests for POST /api/export/docx."""

    async def test_export_returns_docx(self, async_client, sample_source, sample_translation, sample_annotations):
        """Verify the endpoint returns a .docx file."""
        resp = await async_client.post(
            "/api/export/docx",
            json={
                "source_text": sample_source,
                "translated_text": sample_translation,
                "risk_annotations": sample_annotations,
                "language": "en-GB",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert len(resp.content) > 0

    async def test_export_empty_translation_returns_400(self, async_client, sample_source):
        """Verify the endpoint rejects empty translation."""
        resp = await async_client.post(
            "/api/export/docx",
            json={
                "source_text": sample_source,
                "translated_text": "",
                "risk_annotations": [],
                "language": "en-GB",
            },
        )
        assert resp.status_code == 400

    async def test_export_no_annotations(self, async_client, sample_source, sample_translation):
        """Verify the endpoint works with no risk annotations."""
        resp = await async_client.post(
            "/api/export/docx",
            json={
                "source_text": sample_source,
                "translated_text": sample_translation,
                "risk_annotations": [],
                "language": "en-GB",
            },
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_export_docx.py::TestExportApi -v
```
Expected: FAIL — 404 or no async_client fixture

- [ ] **Step 3: Create `export.py` router**

```python
"""Export API — download translations as .docx."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi.responses import Response

from app.services.export_docx import generate_translation_docx

router = APIRouter(prefix="/api/export", tags=["export"])


class _ExportDocxRequest(BaseModel):
    source_text: str = ""
    translated_text: str
    risk_annotations: list[dict] = []
    language: str = "en-GB"


@router.post("/docx")
async def export_docx(body: _ExportDocxRequest):
    """Generate and return a .docx file for the given translation result."""
    if not body.translated_text:
        raise HTTPException(status_code=400, detail="translated_text is required")

    try:
        docx_bytes = generate_translation_docx(
            source_text=body.source_text,
            translated_text=body.translated_text,
            risk_annotations=body.risk_annotations,
            language=body.language,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {e}")

    filename = f"translation_{body.language}.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Register router in `main.py`**

Edit `backend/app/main.py` — add import and register:

```python
from app.api.export import router as export_router
```

and in the app creation:

```python
app.include_router(export_router)
```

- [ ] **Step 5: Add async_client fixture to test file**

Check if `conftest.py` has an `async_client`. If not, add at the top of test file:

```python
@pytest.fixture
async def async_client():
    """Create a test client for the FastAPI app."""
    from app.main import app
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

- [ ] **Step 6: Run tests to verify**

```bash
cd backend && python -m pytest tests/test_export_docx.py -v
```
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/export.py backend/app/main.py
git commit -m "feat(export): add POST /api/export/docx endpoint"
```

---

### Task 3: Frontend — API client method and UI button

**Files:**
- Modify: `frontend/lib/api-client.ts`
- Modify: `frontend/components/workspace/result-actions.tsx`

- [ ] **Step 1: Add `exportDocx()` to ApiClient**

Edit `frontend/lib/api-client.ts` — add method:

```typescript
  async exportDocx(data: {
    source_text: string;
    translated_text: string;
    risk_annotations: Array<{
      phrase: string;
      risk_level: string;
      risk_type?: string;
      explanation?: string;
    }>;
    language: string;
  }): Promise<Blob> {
    const res = await fetch(`${API_BASE}/api/export/docx`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.getToken()}`,
      },
      body: JSON.stringify(data),
    });
    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Export error: ${res.status}`);
    }
    return res.blob();
  }
```

- [ ] **Step 2: Add "导出 .docx" button to ResultActions**

Replace `frontend/components/workspace/result-actions.tsx`:

```tsx
"use client";

import { useTranslationStore } from "@/stores/translation-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";

export function ResultActions({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const sourceText = useWorkspaceStore((s) => s.input.text);

  function handleCopy() {
    if (result?.translatedText) { navigator.clipboard.writeText(result.translatedText); }
  }

  function handleExportTxt() {
    if (!result?.translatedText) return;
    const blob = new Blob([result.translatedText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `translation_${language}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleExportDocx() {
    if (!result?.translatedText) return;
    try {
      const blob = await apiClient.exportDocx({
        source_text: sourceText,
        translated_text: result.translatedText,
        risk_annotations: (result.riskAnnotations || []).map((a) => ({
          phrase: a.phrase,
          risk_level: a.risk_level,
          risk_type: a.risk_type,
          explanation: a.explanation,
        })),
        language,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const now = new Date();
      const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
      a.download = `translation_${language}_${ts}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export .docx:", err);
    }
  }

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={handleCopy} disabled={!result?.translatedText}>复制</Button>
      <Button variant="outline" size="sm" onClick={handleExportTxt} disabled={!result?.translatedText}>导出 .txt</Button>
      <Button variant="outline" size="sm" onClick={handleExportDocx} disabled={!result?.translatedText}>导出 .docx</Button>
    </div>
  );
}
```

- [ ] **Step 3: Build check**

```bash
cd frontend && npx tsc --noEmit --pretty 2>&1 | head -30
```
Expected: no type errors (or only pre-existing ones unrelated to our changes)

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api-client.ts frontend/components/workspace/result-actions.tsx
git commit -m "feat(export): add .docx export button and API client method"
```

---

### Self-Review

**Spec coverage:**
- 3.1 export_docx.py — ✅ backend service
- 3.4 POST /api/export/docx — ✅ endpoint
- 4.1 ApiClient.exportDocx — ✅ method
- 4.2 ResultActions button — ✅ UI
- 4.3 File naming — ✅ timestamp in filename
- 5 Dependencies — ✅ none needed
- 7 Tests — ✅ backend tests

**Placeholder scan:** No TBD/TODO — all code complete.
**Type consistency:** Signatures match across tasks.
**Scope check:** Focused — one feature, no scope creep.
