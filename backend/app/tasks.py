import asyncio
import logging
import uuid

from app.celery_app import celery_app
from app.core.database import async_session
from app.models.job import TranslationJob, TranslationResult
from app.services.translation import pipeline

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def run_translation(self, job_id: str):
    """Celery task: run translation for all target languages in a job."""
    asyncio.run(_run_translation(job_id))


async def _run_translation(job_id: str):
    async with async_session() as db:
        from sqlalchemy import select

        result = await db.execute(select(TranslationJob).where(TranslationJob.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if job is None:
            logger.error(f"Job {job_id} not found")
            return

        job.status = "processing"
        await db.commit()

        all_completed = True
        for lang in job.target_languages:
            try:
                tr_result = await db.execute(
                    select(TranslationResult).where(
                        TranslationResult.job_id == job.id,
                        TranslationResult.language == lang,
                    )
                )
                tr = tr_result.scalar_one_or_none()
                if tr is None:
                    tr = TranslationResult(job_id=job.id, language=lang, status="streaming")
                    db.add(tr)
                    await db.commit()
                    await db.refresh(tr)
                else:
                    tr.status = "streaming"
                    await db.commit()

                output = await pipeline.translate(
                    source_text=job.source_text,
                    genre=job.genre,
                    strategy=job.strategy,
                    target_language=lang,
                )
                tr.translated_text = output["translated_text"]
                tr.risk_annotations = output["risk_annotations"]
                tr.acceptance_score = output["acceptance_score"]
                tr.status = "completed"
                await db.commit()

            except Exception as e:
                logger.error(f"Translation failed for job {job_id} lang {lang}: {e}")
                all_completed = False
                tr_result = await db.execute(
                    select(TranslationResult).where(
                        TranslationResult.job_id == job.id,
                        TranslationResult.language == lang,
                    )
                )
                tr = tr_result.scalar_one_or_none()
                if tr:
                    tr.status = "failed"
                    await db.commit()

        job.status = "completed" if all_completed else "partial"
        await db.commit()
