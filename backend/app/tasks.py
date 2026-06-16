import asyncio
import logging
import uuid

from app.celery_app import celery_app
from app.core.config import settings
from app.llm.bailian import bailian_client
from app.models.job import TranslationJob, TranslationResult
from app.services.cultural import cultural_preprocess
from app.services.translation import pipeline

logger = logging.getLogger(__name__)


def _get_async_session():
    """Create a fresh async session for use inside Celery workers.

    Celery forks worker processes, which invalidates the shared engine's
    connection pool.  We create a new engine + session per task invocation
    so that asyncpg connections belong to the current event loop.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return session_factory, engine


@celery_app.task(bind=True)
def run_translation(self, job_id: str):
    """Celery task: run translation for all target languages in a job."""
    asyncio.run(_run_translation(job_id))


async def _run_translation(job_id: str):
    session_factory, engine = _get_async_session()
    try:
        async with session_factory() as db:
            from sqlalchemy import select

            result = await db.execute(select(TranslationJob).where(TranslationJob.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()
            if job is None:
                logger.error(f"Job {job_id} not found")
                return

            job.status = "processing"
            await db.commit()

            all_completed = True

            # Cultural preprocessing is language-agnostic (the preprocess prompt
            # takes sphere+audience+genre, no target language), so run it once per
            # job and reuse the result across all target languages.
            cultural_constraints = None
            if job.cultural_sphere:
                cultural_constraints = await cultural_preprocess(
                    text=job.source_text,
                    cultural_sphere=job.cultural_sphere,
                    audience_type=job.audience_type or "general_public",
                    genre=job.genre,
                    llm_client=bailian_client,
                )

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
                        cultural_sphere=job.cultural_sphere,
                        audience_type=job.audience_type,
                        cultural_constraints=cultural_constraints,
                    )
                    tr.translated_text = output["translated_text"]
                    tr.risk_annotations = output["risk_annotations"]
                    tr.cultural_adaptation = output["cultural_adaptation"]
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
    finally:
        await engine.dispose()
