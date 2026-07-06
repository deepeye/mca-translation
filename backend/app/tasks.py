import asyncio
import logging
import uuid

from app.celery_app import celery_app
from app.core.config import settings
from app.llm.bailian import bailian_client
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.services.cultural import cultural_preprocess
from app.services.decision_log import save_decision_logs
from app.services.translation import pipeline
from app.services.credits import credits_service, DeductResult

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
            # 余额预检:不足以覆盖总成本(len(source) × 语言数)时跳过 cultural_preprocess(LLM),
            # 避免余额不足仍消耗 LLM 调用。逐语言预检(下方 line 91)仍会标记各语言 failed。
            user_row = (await db.execute(select(User).where(User.id == job.user_id))).scalar_one()
            total_cost = len(job.source_text) * len(job.target_languages)
            cultural_constraints = None
            if job.cultural_sphere and user_row.credit_balance >= total_cost:
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

                    # 余额预检：在调用 LLM 前检查是否足够
                    cost = len(job.source_text)
                    user_row = (
                        await db.execute(select(User).where(User.id == job.user_id))
                    ).scalar_one()
                    if user_row.credit_balance < cost:
                        tr.status = "failed"
                        all_completed = False
                        await db.commit()
                        continue

                    output = await pipeline.translate(
                        source_text=job.source_text,
                        genre=job.genre,
                        strategy=job.strategy,
                        target_language=lang,
                        cultural_sphere=job.cultural_sphere,
                        audience_type=job.audience_type,
                        cultural_constraints=cultural_constraints,
                        db=db,
                        user_id=job.user_id,
                    )
                    tr.translated_text = output["translated_text"]
                    tr.risk_annotations = output["risk_annotations"]
                    tr.cultural_adaptation = output["cultural_adaptation"]
                    tr.acceptance_score = output["acceptance_score"]
                    tr.status = "completed"

                    # 持久化决策日志 — 尽力而为，失败不阻断翻译流程
                    decision_entries = output.get("decision_entries") or []
                    if decision_entries:
                        try:
                            log_ids = await save_decision_logs(
                                db, job_id=job.id, result_id=tr.id, entries=decision_entries
                            )
                            tr.decision_log_ids = log_ids
                        except Exception as e:
                            logger.warning(f"Decision log save failed for job {job.id} lang {lang}: {e}")

                    # 翻译成功：扣除信用分（1 字符 = 1 信用分）
                    deduct_res, _ = await credits_service.deduct_for_translation(
                        db, job.user_id, job.source_text, lang, job.id
                    )
                    if deduct_res is DeductResult.INSUFFICIENT:
                        # 余额不足：标记失败，不扣款，并确保最终 job 状态为 partial
                        tr.status = "failed"
                        tr.translated_text = None
                        all_completed = False
                        await db.commit()
                        continue

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
                        # 翻译失败：退还该语言已扣的信用分（幂等，无扣款时为 no-op）
                        try:
                            await credits_service.refund_for_translation(
                                db, job.user_id, job.source_text, lang, job.id
                            )
                        except Exception as refund_err:
                            logger.warning(f"Refund failed for job {job.id} lang {lang}: {refund_err}")

            job.status = "completed" if all_completed else "partial"
            await db.commit()
    finally:
        await engine.dispose()
