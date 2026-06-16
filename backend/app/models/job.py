import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    source_text: Mapped[str] = mapped_column(Text)
    genre: Mapped[str] = mapped_column(String(16))
    genre_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_terms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    strategy: Mapped[str] = mapped_column(String(24), default="semantic_equivalence")
    target_languages: Mapped[list] = mapped_column(ARRAY(String), default=list)
    glossary_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    cultural_sphere: Mapped[str | None] = mapped_column(String(32), nullable=True)
    audience_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranslationResult(Base):
    __tablename__ = "translation_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("translation_jobs.id"), index=True)
    language: Mapped[str] = mapped_column(String(8), index=True)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_score: Mapped[int] = mapped_column(Integer, default=-1)
    audience_baseline: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_annotations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_log_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    cultural_adaptation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
