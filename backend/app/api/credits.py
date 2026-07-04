"""信用分用户端 API — 余额、交易明细、消费趋势。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.credits import credits_service

router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.get("/balance")
async def get_balance(user: User = Depends(get_current_user)):
    return {"balance": user.credit_balance, "is_admin": user.is_admin}


@router.get("/transactions")
async def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    txs = await credits_service.get_transactions(db, user.id, limit)
    return [
        {
            "id": str(t.id),
            "delta": t.delta,
            "tx_type": t.tx_type.value,
            "reason": t.reason,
            "job_id": str(t.job_id) if t.job_id else None,
            "review_id": str(t.review_id) if t.review_id else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in txs
    ]


@router.get("/trend")
async def get_trend(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await credits_service.get_trend(db, user.id, days)
