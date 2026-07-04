"""信用分服务 — 所有余额变动的唯一入口。

每次扣款/退还/管理员调整都在单个数据库事务内完成：
SELECT FOR UPDATE 锁定用户行 → 校验余额 → 更新余额 → 写审计行 → 提交。
退款通过 idempotency_key 保证幂等，避免失败重试导致重复退还。
"""
import enum
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditTransaction, TxType
from app.models.user import User


class DeductResult(enum.Enum):
    OK = "ok"
    INSUFFICIENT = "insufficient"
    ALREADY_APPLIED = "already_applied"


class CreditsService:
    async def _apply(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        delta: int,
        tx_type: TxType,
        reason: str,
        job_id: uuid.UUID | None = None,
        review_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        allow_negative: bool = False,
    ) -> tuple[DeductResult, int]:
        """原子地应用一次余额变动。返回 (结果, 新余额)。

        - 若 idempotency_key 已存在 → ALREADY_APPLIED，不重复写入。
        - 若 delta<0 且会令余额 <0 且不允许负数 → INSUFFICIENT。
        """
        # 幂等检查：同 key 的交易已存在则直接返回当前余额
        if idempotency_key is not None:
            existing = await db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.idempotency_key == idempotency_key
                )
            )
            if existing.scalar_one_or_none() is not None:
                user_row = await db.get(User, user_id)
                return DeductResult.ALREADY_APPLIED, user_row.credit_balance

        # 行锁，串行化同用户的并发扣款
        user = (
            await db.execute(select(User).where(User.id == user_id).with_for_update())
        ).scalar_one()

        actual_delta = delta
        if delta < 0 and not allow_negative:
            if user.credit_balance + delta < 0:
                return DeductResult.INSUFFICIENT, user.credit_balance
        elif delta < 0 and allow_negative:
            # 管理员扣减：钳制到 0，不产生负数
            actual_delta = max(delta, -user.credit_balance)

        user.credit_balance += actual_delta
        tx = CreditTransaction(
            user_id=user_id,
            delta=actual_delta,
            tx_type=tx_type,
            reason=reason,
            job_id=job_id,
            review_id=review_id,
            idempotency_key=idempotency_key,
        )
        db.add(tx)
        try:
            await db.commit()
        except IntegrityError:
            # 并发重试时唯一约束冲突：同 idempotency_key 已提交，回滚后返回当前余额
            await db.rollback()
            user_row = await db.get(User, user_id)
            return DeductResult.ALREADY_APPLIED, user_row.credit_balance
        await db.refresh(user)
        return DeductResult.OK, user.credit_balance

    async def deduct_for_translation(
        self, db, user_id, source_text: str, language: str, job_id: uuid.UUID
    ) -> tuple[DeductResult, int]:
        cost = len(source_text)
        key = f"consume:{job_id}:{language}"
        return await self._apply(
            db, user_id, -cost, TxType.consume,
            reason=f"翻译消耗: {language}", job_id=job_id, idempotency_key=key,
        )

    async def refund_for_translation(
        self, db, user_id, source_text: str, language: str, job_id: uuid.UUID
    ) -> tuple[DeductResult, int]:
        key = f"refund:{job_id}:{language}"
        # 退款必须先有对应扣款，否则视为已应用（无需退还）
        consume_key = f"consume:{job_id}:{language}"
        prior = await db.execute(
            select(CreditTransaction).where(
                CreditTransaction.idempotency_key == consume_key
            )
        )
        prior_tx = prior.scalar_one_or_none()
        if prior_tx is None:
            user_row = await db.get(User, user_id)
            return DeductResult.ALREADY_APPLIED, user_row.credit_balance
        refund_amount = abs(prior_tx.delta)
        return await self._apply(
            db, user_id, refund_amount, TxType.refund,
            reason=f"翻译失败退还: {language}", job_id=job_id, idempotency_key=key,
            allow_negative=False,
        )

    async def deduct_for_review(
        self, db, user_id, text_length: int, review_id: uuid.UUID, mode: str
    ) -> tuple[DeductResult, int]:
        key = f"consume_review:{review_id}"
        return await self._apply(
            db, user_id, -text_length, TxType.consume,
            reason=f"审校消耗: {mode}", review_id=review_id, idempotency_key=key,
        )

    async def refund_for_review(
        self, db, user_id, text_length: int, review_id: uuid.UUID, mode: str
    ) -> tuple[DeductResult, int]:
        key = f"refund_review:{review_id}"
        consume_key = f"consume_review:{review_id}"
        prior = await db.execute(
            select(CreditTransaction).where(
                CreditTransaction.idempotency_key == consume_key
            )
        )
        prior_tx = prior.scalar_one_or_none()
        if prior_tx is None:
            user_row = await db.get(User, user_id)
            return DeductResult.ALREADY_APPLIED, user_row.credit_balance
        refund_amount = abs(prior_tx.delta)
        return await self._apply(
            db, user_id, refund_amount, TxType.refund,
            reason=f"审校失败退还: {mode}", review_id=review_id, idempotency_key=key,
            allow_negative=False,
        )

    async def admin_adjust(
        self, db, user_id, delta: int, admin_id: uuid.UUID, reason: str
    ) -> int:
        tx_type = TxType.admin_topup if delta >= 0 else TxType.admin_revoke
        full_reason = f"{reason} (管理员 {admin_id})"
        _, new_balance = await self._apply(
            db, user_id, delta, tx_type, reason=full_reason,
            allow_negative=(delta < 0),
        )
        return new_balance

    async def get_balance(self, db, user_id: uuid.UUID) -> int:
        user = await db.get(User, user_id)
        return user.credit_balance if user else 0

    async def get_trend(self, db, user_id: uuid.UUID, days: int) -> list[dict]:
        """返回最近 days 天每日消耗（只统计 consume 类型的负 delta 绝对值）。"""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        rows = await db.execute(
            select(
                func.date(CreditTransaction.created_at).label("d"),
                func.sum(CreditTransaction.delta).label("delta"),
            )
            .where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.created_at >= start,
                CreditTransaction.tx_type == TxType.consume,
            )
            .group_by("d")
            .order_by("d")
        )
        by_date = {str(r.d): abs(int(r.delta)) for r in rows}
        # 补齐空白天，便于前端画图
        out = []
        for i in range(days):
            day = (now - timedelta(days=days - 1 - i)).date().isoformat()
            out.append({"date": day, "consumed": by_date.get(day, 0)})
        return out

    async def get_transactions(
        self, db, user_id: uuid.UUID, limit: int = 50
    ) -> list[CreditTransaction]:
        rows = await db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
        )
        return list(rows.scalars().all())


credits_service = CreditsService()
