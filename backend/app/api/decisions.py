"""决策日志 API — 查询翻译任务的决策链路。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.schemas.decision_log import DecisionLogResponse
from app.services.decision_log import (
    get_decision_logs_by_job,
    get_decision_logs_by_result,
)

router = APIRouter(tags=["decisions"])


async def _get_user_job(
    job_id: uuid.UUID, user: User, db: AsyncSession
) -> TranslationJob:
    """获取当前用户的翻译任务（权限隔离）。"""
    stmt = select(TranslationJob).where(
        TranslationJob.id == job_id, TranslationJob.user_id == user.id
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def _get_user_result(
    result_id: uuid.UUID, user: User, db: AsyncSession
) -> TranslationResult:
    """获取当前用户的译文结果（权限隔离）。"""
    stmt = (
        select(TranslationResult)
        .join(TranslationJob, TranslationResult.job_id == TranslationJob.id)
        .where(TranslationResult.id == result_id, TranslationJob.user_id == user.id)
    )
    result = (await db.execute(stmt)).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return result


@router.get(
    "/api/jobs/{job_id}/decisions", response_model=list[DecisionLogResponse]
)
async def list_job_decisions(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某个翻译任务的所有决策日志（全部语言）。"""
    await _get_user_job(job_id, user, db)
    logs = await get_decision_logs_by_job(db, job_id)
    return logs


@router.get(
    "/api/results/{result_id}/decisions", response_model=list[DecisionLogResponse]
)
async def list_result_decisions(
    result_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某个语言译文结果的所有决策日志（按语言查看）。"""
    await _get_user_result(result_id, user, db)
    logs = await get_decision_logs_by_result(db, result_id)
    return logs
