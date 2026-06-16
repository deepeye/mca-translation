import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.schemas.job import (
    AcceptAllRequest, AcceptRiskRequest, CreateJobRequest, DismissRiskRequest,
    JobListItem, JobResponse, RevertRiskRequest, SuggestionResponse, TranslationResultResponse,
)
from app.services.suggestion import suggestion_service
from app.tasks import run_translation

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = TranslationJob(
        user_id=user.id,
        source_text=body.source_text,
        genre=body.genre,
        strategy=body.strategy,
        target_languages=body.target_languages,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Create empty result rows for each language
    for lang in body.target_languages:
        result = TranslationResult(job_id=job.id, language=lang, status="idle")
        db.add(result)
    await db.commit()

    # Dispatch Celery task
    run_translation.delay(str(job.id))

    # Reload with results
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    return _build_job_response(job, results)


@router.get("", response_model=list[JobListItem])
async def list_jobs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TranslationJob)
        .where(TranslationJob.user_id == user.id)
        .order_by(TranslationJob.created_at.desc())
        .limit(50)
    )
    jobs = result.scalars().all()
    return [
        JobListItem(
            id=j.id,
            status=j.status,
            genre=j.genre,
            target_languages=j.target_languages,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    return _build_job_response(job, results)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    for r in results:
        await db.delete(r)
    await db.delete(job)
    await db.commit()


@router.get("/{job_id}/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    job_id: uuid.UUID,
    lang: str,
    risk_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    suggestions = await suggestion_service.generate(
        source_text=job.source_text,
        translated_text=result.translated_text,
        target_language=lang,
        phrase=ann["phrase"],
        risk_type=ann.get("risk_type", ""),
        explanation=ann.get("explanation", ""),
    )
    return SuggestionResponse(suggestions=suggestions)


@router.post("/{job_id}/risks/{risk_index}/accept")
async def accept_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: AcceptRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    if ann.get("status", "open") != "open":
        raise HTTPException(status_code=400, detail="Risk is not in open state")

    offset = ann.get("offset")
    text = result.translated_text or ""
    if offset is not None and offset >= 0 and text[offset:offset + len(ann["phrase"])] == ann["phrase"]:
        text = text[:offset] + body.suggestion + text[offset + len(ann["phrase"]):]
    else:
        text = text.replace(ann["phrase"], body.suggestion, 1)

    ann["status"] = "accepted"
    ann["accepted_suggestion"] = body.suggestion
    result.translated_text = text
    result.risk_annotations = _recalculate_offsets(text, annotations)
    flag_modified(result, "risk_annotations")
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


@router.post("/{job_id}/risks/{risk_index}/dismiss")
async def dismiss_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: DismissRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    annotations[risk_index]["status"] = "dismissed"
    result.risk_annotations = annotations
    flag_modified(result, "risk_annotations")
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


@router.post("/{job_id}/risks/{risk_index}/revert")
async def revert_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: RevertRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    if ann.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="Risk is not in accepted state")

    suggestion = ann["accepted_suggestion"]
    phrase = ann["phrase"]
    text = result.translated_text or ""
    text = text.replace(suggestion, phrase, 1)

    ann["status"] = "open"
    del ann["accepted_suggestion"]
    result.translated_text = text
    result.risk_annotations = _recalculate_offsets(text, annotations)
    flag_modified(result, "risk_annotations")
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


_accept_all_locks: dict[str, asyncio.Lock] = {}


@router.post("/{job_id}/risks/accept-all")
async def accept_all_risks(
    job_id: uuid.UUID,
    body: AcceptAllRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lock_key = f"{job_id}:{body.lang}"
    if lock_key not in _accept_all_locks:
        _accept_all_locks[lock_key] = asyncio.Lock()
    if _accept_all_locks[lock_key].locked():
        raise HTTPException(status_code=409, detail="Batch processing in progress")

    async with _accept_all_locks[lock_key]:
        job = await _get_user_job(job_id, user, db)
        result = await _get_lang_result(job.id, body.lang, db)
        annotations = result.risk_annotations or []
        skipped = []

        for i, ann in enumerate(annotations):
            if ann.get("status", "open") != "open":
                continue
            suggestions = await suggestion_service.generate(
                source_text=job.source_text,
                translated_text=result.translated_text,
                target_language=body.lang,
                phrase=ann["phrase"],
                risk_type=ann.get("risk_type", ""),
                explanation=ann.get("explanation", ""),
            )
            if not suggestions:
                skipped.append(i)
                continue

            suggestion = suggestions[0]["text"]
            offset = ann.get("offset")
            text = result.translated_text or ""
            if offset is not None and offset >= 0 and text[offset:offset + len(ann["phrase"])] == ann["phrase"]:
                text = text[:offset] + suggestion + text[offset + len(ann["phrase"]):]
            else:
                text = text.replace(ann["phrase"], suggestion, 1)

            ann["status"] = "accepted"
            ann["accepted_suggestion"] = suggestion
            result.translated_text = text
            result.risk_annotations = _recalculate_offsets(text, annotations)
            flag_modified(result, "risk_annotations")

        await db.commit()
        await db.refresh(result)

    response = _build_job_response(job, [result])
    if skipped:
        response["skipped_risk_indices"] = skipped
    return response


async def _get_user_job(job_id: uuid.UUID, user: User, db: AsyncSession) -> TranslationJob:
    job = (
        await db.execute(
            select(TranslationJob).where(
                TranslationJob.id == job_id,
                TranslationJob.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _get_lang_result(job_id: uuid.UUID, lang: str, db: AsyncSession) -> TranslationResult:
    result = (
        await db.execute(
            select(TranslationResult).where(
                TranslationResult.job_id == job_id,
                TranslationResult.language == lang,
            )
        )
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Translation result not found")
    return result


def _recalculate_offsets(text: str, annotations: list[dict]) -> list[dict]:
    """Recalculate offsets for all open risk annotations after text change."""
    used_offsets = set()
    for ann in annotations:
        if ann.get("status", "open") != "open":
            continue
        offset = text.find(ann["phrase"])
        if offset == -1 or offset in used_offsets:
            offset = -1
        else:
            used_offsets.add(offset)
        ann["offset"] = offset
    return annotations


def _build_job_response(job: TranslationJob, results: list[TranslationResult]) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        source_text=job.source_text,
        genre=job.genre,
        strategy=job.strategy,
        target_languages=job.target_languages,
        results=[
            TranslationResultResponse(
                id=r.id,
                language=r.language,
                status=r.status,
                translated_text=r.translated_text,
                acceptance_score=r.acceptance_score,
                risk_annotations=r.risk_annotations,
                created_at=r.created_at,
            )
            for r in results
        ],
        created_at=job.created_at,
    )
