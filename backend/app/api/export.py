"""Export API — download translations as .docx."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from fastapi.responses import Response

from app.services.export_docx import generate_translation_docx
from app.constants.languages import is_supported_language

router = APIRouter(prefix="/api/export", tags=["export"])


class _ExportDocxRequest(BaseModel):
    source_text: str = ""
    translated_text: str
    risk_annotations: list[dict] = []
    language: str = "en-GB"

    @field_validator("language")
    @classmethod
    def _check_language(cls, v: str) -> str:
        if not is_supported_language(v):
            raise ValueError(f"unsupported target language code: {v}")
        return v


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
