"""管理员 API — 用户列表、调整信用分、查看任意用户交易。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.credit import CreditTransaction
from app.models.user import User
from app.schemas.credit import AdminAdjustRequest, AdminUserItem, CreditTransactionOut
from app.services.credits import credits_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserItem])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    # last_active = 该用户最近一笔交易时间
    out = []
    for u in users:
        last_tx = (
            await db.execute(
                select(CreditTransaction.created_at)
                .where(CreditTransaction.user_id == u.id)
                .order_by(CreditTransaction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(AdminUserItem(
            id=str(u.id),
            username=u.username,
            is_admin=u.is_admin,
            credit_balance=u.credit_balance,
            last_active=last_tx.isoformat() if last_tx else None,
        ))
    return out


@router.post("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: uuid.UUID,
    body: AdminAdjustRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    new_balance = await credits_service.admin_adjust(
        db, target.id, body.delta, admin.id, body.reason
    )
    return {"balance": new_balance}


@router.get("/transactions", response_model=list[CreditTransactionOut])
async def list_user_transactions(
    user_id: uuid.UUID = Query(...),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    txs = await credits_service.get_transactions(db, user_id, limit)
    return [
        CreditTransactionOut(
            id=str(t.id), delta=t.delta, tx_type=t.tx_type.value,
            reason=t.reason,
            job_id=str(t.job_id) if t.job_id else None,
            review_id=str(t.review_id) if t.review_id else None,
            created_at=t.created_at.isoformat(),
        )
        for t in txs
    ]
