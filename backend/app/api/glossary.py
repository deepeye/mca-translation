import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.constants.languages import SUPPORTED_LANGUAGE_CODES
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
    UserGlossaryEntryUpdate,
)
from app.services.cultural import cultural_preprocess
from app.services.glossary_autofill import generate_translation
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


@router.put("/user-entries/{entry_id}", response_model=UserGlossaryEntryResponse)
async def update_user_entry(
    entry_id: uuid.UUID,
    body: UserGlossaryEntryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(UserGlossaryEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_data = body.model_dump(exclude_unset=True)
    if "translations" in update_data and update_data["translations"] is not None:
        update_data["translations"] = {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in update_data["translations"].items()
        }

    # Re-generate embedding if source_term changed
    if "source_term" in update_data:
        try:
            embeddings = await bailian_client.embed([update_data["source_term"]])
            update_data["embedding"] = embeddings[0] if embeddings else None
        except Exception:
            update_data["embedding"] = None

    for field, value in update_data.items():
        setattr(entry, field, value)

    await db.commit()
    await db.refresh(entry)
    return entry


class _AutoFillResponse(BaseModel):
    entry: UserGlossaryEntryResponse
    filled_languages: list[str]
    skipped: list[dict]


@router.post("/user-entries/{entry_id}/auto-fill", response_model=_AutoFillResponse)
async def autofill_user_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为单个用户词条自动填充缺失语言的 LLM 译文。

    遍历未翻译的目标语言，逐一调用 LLM 生成译文。
    已有翻译的语言保持不变，不覆盖。
    """
    entry = await db.get(UserGlossaryEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")

    existing = set(entry.translations.keys())
    missing = SUPPORTED_LANGUAGE_CODES - existing
    filled: list[str] = []
    skipped: list[dict] = []

    en_ref = entry.translations.get("en-GB", {}).get("preferred")
    for lang in sorted(missing):
        generated = await generate_translation(entry.source_term, lang, en_ref)
        if generated:
            entry.translations[lang] = generated
            filled.append(lang)
        else:
            skipped.append({"code": lang, "reason": "llm_failed"})

    if filled:
        await db.commit()
        await db.refresh(entry)

    return _AutoFillResponse(entry=entry, filled_languages=filled, skipped=skipped)


# --- Legacy detect endpoint (hybrid: DB first, hardcoded fallback) ---

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
    db: AsyncSession = Depends(get_db),
):
    """Detect glossary terms in source text.

    Hybrid mode:
    1.  Query user glossary entries (substring match, current user)
    2.  Query system glossary entries (substring match)
    3.  If combined DB results exist, deduplicate (user > system) and return
    4.  Otherwise fall back to hardcoded glossary
    """
    if not body.text:
        return _DetectResponse(terms=[])

    # --- Step 1: Query DB for substring matches ---
    db_terms: list[_DetectedTermItem] = []
    seen_sources: set[str] = set()

    # User glossary (higher priority)
    user_stmt = select(UserGlossaryEntry).where(UserGlossaryEntry.user_id == user.id)
    user_rows = (await db.execute(user_stmt)).scalars().all()
    for row in user_rows:
        if row.source_term in body.text and row.source_term not in seen_sources:
            seen_sources.add(row.source_term)
            db_terms.append(
                _DetectedTermItem(
                    source_term=row.source_term,
                    term_type=row.term_type,
                    risk_notes=row.risk_notes or "",
                    translations=dict(row.translations),
                )
            )

    # System glossary
    sys_stmt = select(GlossaryEntry)
    sys_rows = (await db.execute(sys_stmt)).scalars().all()
    for row in sys_rows:
        if row.source_term in body.text and row.source_term not in seen_sources:
            seen_sources.add(row.source_term)
            db_terms.append(
                _DetectedTermItem(
                    source_term=row.source_term,
                    term_type=row.term_type,
                    risk_notes=row.risk_notes or "",
                    translations=dict(row.translations),
                )
            )

    if db_terms:
        return _DetectResponse(terms=db_terms)

    # --- Step 2: Fall back to hardcoded ---
    matched = find_terms_in_text(body.text)
    items = []
    for term in matched:
        trans = {}
        for lang in SUPPORTED_LANGUAGE_CODES:
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


# --- Cultural term detection (LLM-based, input-phase) ---

class _CulturalDetectRequest(BaseModel):
    text: str
    cultural_sphere: str
    audience_type: str
    genre: str


class _CulturalDetectedTerm(BaseModel):
    term: str
    offset: int
    length: int
    culture_gap: str  # low|medium|high
    adaptation_strategy: str  # literal|explanatory|analogical|reconstruction
    suggested_rendering: str
    reason: str
    term_type: str = "cultural_metaphor"  # 固定分类，供前端着色


class _CulturalDetectResponse(BaseModel):
    terms: list[_CulturalDetectedTerm]


def _find_all_occurrences(haystack: str, needle: str) -> list[int]:
    """返回 needle 在 haystack 中所有出现位置的首字符偏移。空串或未命中返回 []。
    多次出现全部计入，用于内联高亮每处命中。"""
    if not needle:
        return []
    offsets: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        offsets.append(idx)
        start = idx + len(needle)
    return offsets


@router.post("/detect-cultural", response_model=_CulturalDetectResponse)
async def detect_cultural_terms(
    body: _CulturalDetectRequest,
    user: User = Depends(get_current_user),
):
    """识别源文本中的文化负载词（隐喻/政治话语），返回带文本偏移的转译建议。

    复用 cultural_preprocess；任何降级（未知文化圈/受众、LLM 失败、JSON 解析失败、
    schema 校验失败）都返回空 terms，不报错 —— 输入期识别为附属能力，不阻塞用户输入。
    """
    if not body.text:
        return _CulturalDetectResponse(terms=[])

    result = await cultural_preprocess(
        text=body.text,
        cultural_sphere=body.cultural_sphere,
        audience_type=body.audience_type,
        genre=body.genre,
        llm_client=bailian_client,
    )
    if result is None:
        return _CulturalDetectResponse(terms=[])

    # 服务端计算每个 term 的全部出现位置（LLM 不返回 offset）
    items: list[_CulturalDetectedTerm] = []
    for t in result.culture_loaded_terms:
        for offset in _find_all_occurrences(body.text, t.term):
            items.append(
                _CulturalDetectedTerm(
                    term=t.term,
                    offset=offset,
                    length=len(t.term),
                    culture_gap=t.culture_gap,
                    adaptation_strategy=t.adaptation_strategy,
                    suggested_rendering=t.suggested_rendering,
                    reason=t.reason,
                )
            )
    return _CulturalDetectResponse(terms=items)
