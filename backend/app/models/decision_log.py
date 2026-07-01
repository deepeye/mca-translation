import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DecisionLog(Base):
    """转译决策日志 — 记录翻译管线各节点的关键决策及其推理依据。"""

    __tablename__ = "decision_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_jobs.id"), index=True
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_results.id"), index=True
    )
    # 决策阶段：preprocess / cultural_detect / glossary / translate / risk / suggestion / acceptance
    stage: Mapped[str] = mapped_column(String(16), index=True)
    # 决策类型标签，如 culture_term_adaptation / risk_identified
    decision_type: Mapped[str] = mapped_column(String(48))
    source_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    # high / medium / low / None
    confidence: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # metadata 是 SQLAlchemy 保留属性，用 metadata_ 映射到 metadata 列
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
