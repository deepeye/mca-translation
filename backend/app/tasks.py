import asyncio
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

# 流式部分译文落库节流间隔（秒）；前端 2s 轮询，每周期约 1-2 次更新
STREAM_WRITE_INTERVAL = 1.0


def make_chunk_writer(tr: TranslationResult, db: AsyncSession, interval: float = STREAM_WRITE_INTERVAL):
    """构造节流回调：每 interval 秒把部分译文写库，状态保持 streaming。

    首个 chunk 立即写（last 初值 0.0，now-0 恒 >= interval）。
    """
    last = {"t": 0.0}

    async def on_chunk(accumulated: str):
        now = time.monotonic()
        if now - last["t"] >= interval:
            tr.translated_text = accumulated
            await db.commit()
            last["t"] = now

    return on_chunk


def _get_async_session():
    """Create a fresh async session for use inside Celery workers.

    Celery forks worker processes, which invalidates the shared engine's
    connection pool.  We create a new engine + session per task invocation
    so that asyncpg connections belong to the current event loop.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=settings.MAX_CONCURRENT_LANGS + 2,
        max_overflow=4,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return session_factory, engine


@celery_app.task(bind=True)
def run_translation(self, job_id: str):
    """Celery task: run translation for all target languages in a job."""
    asyncio.run(_run_translation(job_id))


async def _run_translation(job_id: str):
    session_factory, engine = _get_async_session()
    # semaphore 必须在事件循环内创建（避免模块级跨 loop 绑定）
    sem = asyncio.Semaphore(settings.MAX_CONCURRENT_LANGS)
    try:
        # ---- preamble：取 job / 置 processing / preprocess（共享）----
        async with session_factory() as db:
            job = (await db.execute(
                select(TranslationJob).where(TranslationJob.id == uuid.UUID(job_id))
            )).scalar_one_or_none()
            if job is None:
                logger.error(f"Job {job_id} not found")
                return
            job.status = "processing"
            await db.commit()

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
            # 捕获原语（job 对象 session 关闭后 detach）
            source_text = job.source_text
            target_languages = list(job.target_languages)
            user_id = job.user_id
            genre = job.genre
            strategy = job.strategy
            cultural_sphere = job.cultural_sphere
            audience_type = job.audience_type

        # ---- 每语言协程 ----
        async def run_one_lang(lang: str) -> bool:
            async with sem:
                async with session_factory() as db:
                    try:
                        tr = (await db.execute(
                            select(TranslationResult).where(
                                TranslationResult.job_id == uuid.UUID(job_id),
                                TranslationResult.language == lang,
                            )
                        )).scalar_one_or_none()
                        if tr is None:
                            tr = TranslationResult(job_id=uuid.UUID(job_id), language=lang, status="streaming")
                            db.add(tr)
                            await db.commit()
                            await db.refresh(tr)
                        else:
                            tr.status = "streaming"
                            await db.commit()

                        # 余额预检
                        user_row = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
                        cost = len(source_text)
                        if user_row.credit_balance < cost:
                            tr.status = "failed"
                            await db.commit()
                            return False

                        on_chunk = make_chunk_writer(tr, db)
                        output = await pipeline.translate(
                            source_text=source_text,
                            genre=genre,
                            strategy=strategy,
                            target_language=lang,
                            cultural_sphere=cultural_sphere,
                            audience_type=audience_type,
                            cultural_constraints=cultural_constraints,
                            db=db,
                            user_id=user_id,
                            on_chunk=on_chunk,
                        )
                        tr.translated_text = output["translated_text"]
                        tr.risk_annotations = output["risk_annotations"]
                        tr.cultural_adaptation = output["cultural_adaptation"]
                        tr.acceptance_score = output["acceptance_score"]
                        tr.status = "completed"

                        # 决策日志 — 尽力而为，失败不阻断
                        decision_entries = output.get("decision_entries") or []
                        if decision_entries:
                            try:
                                log_ids = await save_decision_logs(
                                    db, job_id=uuid.UUID(job_id), result_id=tr.id, entries=decision_entries,
                                )
                                tr.decision_log_ids = log_ids
                            except Exception as e:
                                logger.warning(f"Decision log save failed for job {job_id} lang {lang}: {e}")

                        # 扣分（FOR UPDATE 原子）
                        deduct_res, _ = await credits_service.deduct_for_translation(
                            db, user_id, source_text, lang, uuid.UUID(job_id),
                        )
                        if deduct_res is DeductResult.INSUFFICIENT:
                            tr.status = "failed"
                            tr.translated_text = None
                            await db.commit()
                            return False

                        await db.commit()
                        return True

                    except Exception as e:
                        logger.error(f"Translation failed for job {job_id} lang {lang}: {e}")
                        tr = (await db.execute(
                            select(TranslationResult).where(
                                TranslationResult.job_id == uuid.UUID(job_id),
                                TranslationResult.language == lang,
                            )
                        )).scalar_one_or_none()
                        if tr:
                            tr.translated_text = None
                            tr.status = "failed"
                            await db.commit()
                            try:
                                await credits_service.refund_for_translation(
                                    db, user_id, source_text, lang, uuid.UUID(job_id),
                                )
                            except Exception as refund_err:
                                logger.warning(f"Refund failed for job {job_id} lang {lang}: {refund_err}")
                        return False

        # ---- gather 并发 ----
        results = await asyncio.gather(
            *(run_one_lang(lang) for lang in target_languages),
            return_exceptions=True,
        )
        all_success = all(r is True for r in results)

        # ---- 收尾：聚合 job.status ----
        async with session_factory() as db:
            job = (await db.execute(
                select(TranslationJob).where(TranslationJob.id == uuid.UUID(job_id))
            )).scalar_one_or_none()
            if job:
                job.status = "completed" if all_success else "partial"
                await db.commit()
    finally:
        await engine.dispose()
