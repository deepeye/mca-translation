"""信用分相关 Pydantic schema。"""
from pydantic import BaseModel, Field


class AdminAdjustRequest(BaseModel):
    delta: int = Field(..., description="正数=充值，负数=扣减")
    reason: str = Field(..., min_length=1, max_length=200)


class CreditTransactionOut(BaseModel):
    id: str
    delta: int
    tx_type: str
    reason: str | None
    job_id: str | None
    review_id: str | None
    created_at: str
