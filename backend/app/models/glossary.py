import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GlossaryEntry(Base):
    """System-wide political glossary knowledge base (admin-managed)."""

    __tablename__ = "glossary_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_term: Mapped[str] = mapped_column(Text, index=True)
    term_type: Mapped[str] = mapped_column(String(24), default="political_discourse")
    translations: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_genres: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    freshness_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_glossary_entries_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_l2_ops"}),
    )


class UserGlossaryEntry(Base):
    """User-defined glossary entries (personal or organization-level)."""

    __tablename__ = "user_glossary_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    source_term: Mapped[str] = mapped_column(Text, index=True)
    term_type: Mapped[str] = mapped_column(String(24), default="user_defined")
    translations: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_genres: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_user_glossary_entries_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_l2_ops"}),
    )
