from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.hardcoded_glossary import find_terms_in_text, get_term_translation

router = APIRouter(prefix="/api/glossary", tags=["glossary"])


class DetectRequest(BaseModel):
    text: str


class DetectedTermItem(BaseModel):
    source_term: str
    term_type: str
    risk_notes: str
    translations: dict


class DetectResponse(BaseModel):
    terms: list[DetectedTermItem]


@router.post("/detect", response_model=DetectResponse)
async def detect_terms(
    body: DetectRequest,
    user: User = Depends(get_current_user),
):
    matched = find_terms_in_text(body.text)
    items = []
    for term in matched:
        trans = {}
        for lang in ["en-GB", "de-DE", "ja-JP", "es-ES", "fr-FR"]:
            t = get_term_translation(term, lang)
            if t["rendering"]:
                trans[lang] = t
        items.append(DetectedTermItem(
            source_term=term.source_term,
            term_type=term.term_type,
            risk_notes=term.risk_notes,
            translations=trans,
        ))
    return DetectResponse(terms=items)
