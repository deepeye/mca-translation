import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.schemas.job import CreateJobRequest, JobListItem, JobResponse, TranslationResultResponse
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
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    for r in results:
        await db.delete(r)
    await db.delete(job)
    await db.commit()


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
