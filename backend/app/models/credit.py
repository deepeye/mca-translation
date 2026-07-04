"""信用分交易记录模型 — 所有余额变动的审计追踪。"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TxType(str, enum.Enum):
    """交易类型：消费 / 退还 / 管理员充值 / 管理员扣减 / 注册赠送。"""
    consume = "consume"
    refund = "refund"
    admin_topup = "admin_topup"
    admin_revoke = "admin_revoke"
    signup_bonus = "signup_bonus"


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_type: Mapped[TxType] = mapped_column(Enum(TxType, name="tx_type"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # 幂等键：防止同一笔扣款/退还被重复记录
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
