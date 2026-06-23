import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.llm.bailian import bailian_client
from app.models.glossary import GlossaryEntry, UserGlossaryEntry
from app.models.user import User
from app.schemas.glossary import (
    GlossaryEntryCreate,
    GlossaryEntryResponse,
    GlossaryEntryUpdate,
    UserGlossaryEntryCreate,
    UserGlossaryEntryResponse,
)
from app.services.hardcoded_glossary import find_terms_in_text, get_term_translation

router = APIRouter(prefix="/api/glossary", tags=["glossary"])


# --- System Glossary (admin-managed) ---

@router.post("/entries", response_model=GlossaryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: GlossaryEntryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # TODO: Implement proper admin role check when RBAC is available
    raise HTTPException(status_code=403, detail="System glossary management is restricted")
    embeddings = await bailian_client.embed([body.source_term])
    embedding = embeddings[0] if embeddings else None

    entry = GlossaryEntry(
        source_term=body.source_term,
        term_type=body.term_type,
        translations={k: v.model_dump() for k, v in body.translations.items()},
        risk_notes=body.risk_notes,
        applicable_genres=body.applicable_genres or [],
        embedding=embedding,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/entries", response_model=list[GlossaryEntryResponse])
async def list_entries(
    q: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GlossaryEntry).order_by(GlossaryEntry.created_at.desc()).limit(50)
    if q:
        stmt = stmt.where(GlossaryEntry.source_term.ilike(f"%{q}%"))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/entries/{entry_id}", response_model=GlossaryEntryResponse)
async def get_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(GlossaryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.put("/entries/{entry_id}", response_model=GlossaryEntryResponse)
async def update_entry(
    entry_id: uuid.UUID,
    body: GlossaryEntryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # TODO: Implement proper admin role check when RBAC is available
    raise HTTPException(status_code=403, detail="System glossary management is restricted")
    entry = await db.get(GlossaryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_data = body.model_dump(exclude_unset=True)
    if "translations" in update_data and update_data["translations"] is not None:
        update_data["translations"] = {k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in update_data["translations"].items()}

    if "source_term" in update_data:
        embeddings = await bailian_client.embed([update_data["source_term"]])
        update_data["embedding"] = embeddings[0] if embeddings else None

    for field, value in update_data.items():
        setattr(entry, field, value)

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # TODO: Implement proper admin role check when RBAC is available
    raise HTTPException(status_code=403, detail="System glossary management is restricted")
    entry = await db.get(GlossaryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.commit()


# --- User Glossary ---

@router.post("/user-entries", response_model=UserGlossaryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_user_entry(
    body: UserGlossaryEntryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        embeddings = await bailian_client.embed([body.source_term])
        embedding = embeddings[0] if embeddings else None
    except Exception:
        embedding = None

    entry = UserGlossaryEntry(
        user_id=user.id,
        source_term=body.source_term,
        term_type=body.term_type,
        translations={k: v.model_dump() for k, v in body.translations.items()},
        risk_notes=body.risk_notes,
        applicable_genres=body.applicable_genres or [],
        embedding=embedding,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/user-entries", response_model=list[UserGlossaryEntryResponse])
async def list_user_entries(
    q: str = "",
    offset: int = 0,
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserGlossaryEntry)
        .where(UserGlossaryEntry.user_id == user.id)
        .order_by(UserGlossaryEntry.created_at.desc())
    )
    if q:
        stmt = stmt.where(UserGlossaryEntry.source_term.ilike(f"%{q}%"))
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/user-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(UserGlossaryEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.commit()


# --- Legacy detect endpoint (hardcoded, keep for backward compat) ---

class _DetectRequest(BaseModel):
    text: str


class _DetectedTermItem(BaseModel):
    source_term: str
    term_type: str
    risk_notes: str
    translations: dict


class _DetectResponse(BaseModel):
    terms: list[_DetectedTermItem]


@router.post("/detect", response_model=_DetectResponse)
async def detect_terms(
    body: _DetectRequest,
    user: User = Depends(get_current_user),
):
    matched = find_terms_in_text(body.text)
    items = []
    for term in matched:
        trans = {}
        for lang in ["en-GB", "de-DE", "ja-JP", "es-ES", "fr-FR"]:
            t = get_term_translation(term, lang)
            if t["preferred"]:
                trans[lang] = t
        items.append(_DetectedTermItem(
            source_term=term.source_term,
            term_type=term.term_type,
            risk_notes=term.risk_notes,
            translations=trans,
        ))
    return _DetectResponse(terms=items)
