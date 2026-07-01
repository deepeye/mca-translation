import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DecisionLogResponse(BaseModel):
    """决策日志响应 schema — 对应 DecisionLog 模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    result_id: uuid.UUID
    stage: str  # preprocess / glossary / translate / risk / suggestion
    decision_type: str
    source_phrase: str | None = None
    target_phrase: str | None = None
    decision: str
    reasoning: str
    confidence: str | None = None  # high / medium / low / None
    metadata: dict | None = None
    created_at: datetime