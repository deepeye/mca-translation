import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DecisionLogResponse(BaseModel):
    """决策日志响应 schema — 对应 DecisionLog 模型。"""

    # populate_by_name=True: 允许用字段名 metadata 赋值；
    # from_attributes 模式下会用 alias "metadata_" 去 getattr ORM 实例，
    # 从而避开 SQLAlchemy 保留的 metadata (MetaData) 属性。
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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
    # ORM 模型上属性名为 metadata_（metadata 是 SQLAlchemy 保留属性），
    # 用 alias 读取 ORM 实例的 metadata_，但对外 JSON key 仍为 metadata。
    metadata: dict | None = Field(default=None, alias="metadata_")
    created_at: datetime