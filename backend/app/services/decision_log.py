"""决策日志服务 — 批量保存与查询转译决策记录。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_log import DecisionLog

# 阶段排序优先级 — preprocess → glossary → translate → risk → suggestion
_STAGE_ORDER = {
    "preprocess": 0,
    "glossary": 1,
    "translate": 2,
    "risk": 3,
    "suggestion": 4,
}


async def save_decision_logs(
    db: AsyncSession,
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    entries: list[dict],
) -> list[uuid.UUID]:
    """批量创建 DecisionLog 记录，返回 ID 列表。

    尽力而为：单个条目构造失败时跳过，不阻断整体保存。
    """
    if not entries:
        return []

    log_ids: list[uuid.UUID] = []
    for entry in entries:
        try:
            log = DecisionLog(
                job_id=job_id,
                result_id=result_id,
                stage=entry["stage"],
                decision_type=entry["decision_type"],
                source_phrase=entry.get("source_phrase"),
                target_phrase=entry.get("target_phrase"),
                decision=entry["decision"],
                reasoning=entry["reasoning"],
                confidence=entry.get("confidence"),
                metadata_=entry.get("metadata"),
            )
            db.add(log)
            await db.flush()
            log_ids.append(log.id)
        except Exception:
            # 单条失败不阻断其余 — 决策日志是附属数据
            continue
    await db.commit()
    return log_ids


async def get_decision_logs_by_result(
    db: AsyncSession,
    result_id: uuid.UUID,
) -> list[DecisionLog]:
    """按 result_id 查询决策日志，按 stage 优先级和 created_at 排序。"""
    stmt = select(DecisionLog).where(DecisionLog.result_id == result_id)
    rows = (await db.execute(stmt)).scalars().all()
    return sorted(rows, key=lambda r: (_STAGE_ORDER.get(r.stage, 99), r.created_at))


async def get_decision_logs_by_job(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> list[DecisionLog]:
    """按 job_id 查询所有语言的决策日志。"""
    stmt = select(DecisionLog).where(DecisionLog.job_id == job_id)
    rows = (await db.execute(stmt)).scalars().all()
    return sorted(rows, key=lambda r: (_STAGE_ORDER.get(r.stage, 99), r.created_at))
