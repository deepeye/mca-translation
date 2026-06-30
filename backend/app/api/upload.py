import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".txt", ".docx", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _extract_text_from_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _extract_text_from_docx(content: bytes) -> str:
    from docx import Document
    from io import BytesIO

    doc = Document(BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_text_from_pdf(content: bytes) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(stream=content, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


EXTRACTORS = {
    ".txt": _extract_text_from_txt,
    ".docx": _extract_text_from_docx,
    ".pdf": _extract_text_from_pdf,
}


@router.post("")
async def upload_file(file: UploadFile, user: User = Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(content)} bytes). Maximum: {MAX_FILE_SIZE} bytes",
        )

    # Save to disk
    file_id = str(uuid.uuid4())
    os.makedirs(settings.MCA_FILE_STORE_DIR, exist_ok=True)
    file_path = os.path.join(settings.MCA_FILE_STORE_DIR, f"{file_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text content
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        text_content = ""
    else:
        try:
            text_content = extractor(content)
        except Exception as e:
            text_content = ""
            # Continue: return text_content empty rather than failing the upload entirely

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "text_content": text_content,
    }
