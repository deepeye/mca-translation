"""管理员 API — 用户列表、调整信用分、查看任意用户交易。"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.credit import CreditTransaction
from app.models.user import User
from app.schemas.admin import AdminUserDetail, CreateUserRequest, UpdateUserRequest, ToggleStatusRequest
from app.schemas.credit import AdminAdjustRequest, CreditTransactionOut
from app.services.credits import credits_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserDetail])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(
        select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    )).scalars().all()
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
        out.append(AdminUserDetail(
            id=str(u.id),
            username=u.username,
            is_admin=u.is_admin,
            is_active=u.is_active,
            credit_balance=u.credit_balance,
            last_active=last_tx.isoformat() if last_tx else None,
            created_at=u.created_at.isoformat() if u.created_at else "",
        ))
    return out


@router.post("/users", response_model=AdminUserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员创建新用户。"""
    existing = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(
        username=body.username,
        hashed_password=get_password_hash(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserDetail(
        id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        credit_balance=user.credit_balance,
        last_active=None,
        created_at=user.created_at.isoformat(),
    )


@router.put("/users/{user_id}", response_model=AdminUserDetail)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员更新用户信息。不允许自己降级非管理员。"""
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    # 不允许自降权限
    if user.id == admin.id and body.is_admin is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能移除自己的管理员权限")

    if body.username is not None:
        existing = (await db.execute(
            select(User).where(User.username == body.username, User.id != user_id)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
        user.username = body.username
    if body.password is not None and body.password != "":
        user.hashed_password = get_password_hash(body.password)
    if body.is_admin is not None:
        user.is_admin = body.is_admin

    await db.commit()
    await db.refresh(user)
    # compute last_active same as list_users
    last_tx = (
        await db.execute(
            select(CreditTransaction.created_at)
            .where(CreditTransaction.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return AdminUserDetail(
        id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        credit_balance=user.credit_balance,
        last_active=last_tx.isoformat() if last_tx else None,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """逻辑删除用户。不允许删除自己。"""
    if admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能删除当前登录的管理员")
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.patch("/users/{user_id}/status", response_model=AdminUserDetail)
async def toggle_user_status(
    user_id: uuid.UUID,
    body: ToggleStatusRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """禁用或启用用户。不允许禁用自己。"""
    if not body.is_active and admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能禁用当前登录的管理员")
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    last_tx = (
        await db.execute(
            select(CreditTransaction.created_at)
            .where(CreditTransaction.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return AdminUserDetail(
        id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        credit_balance=user.credit_balance,
        last_active=last_tx.isoformat() if last_tx else None,
        created_at=user.created_at.isoformat(),
    )


@router.post("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: uuid.UUID,
    body: AdminAdjustRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if target is None or target.deleted_at is not None:
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
