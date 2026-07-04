import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.constants.languages import is_supported_language


class ReviewIssue(BaseModel):
    category: str
    severity: Literal["low", "medium", "high"]
    span: Optional[dict] = None
    original: str
    suggestion: str
    explanation: str
    source_reference: Optional[str] = None


class ReviewCategory(BaseModel):
    name: str
    score: int = Field(..., ge=0, le=100)
    issue_count: int
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    mode: Literal["dual", "single"]
    source_text: Optional[str] = Field(None, max_length=10000)
    translated_text: str = Field(..., max_length=10000)
    target_language: str
    genre: Optional[str] = None
    cultural_sphere: Optional[str] = None
    audience_type: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)

    @field_validator("target_language")
    @classmethod
    def _check_target_language(cls, v: str) -> str:
        if not is_supported_language(v):
            raise ValueError(f"unsupported target language code: {v}")
        return v


class ReviewResult(BaseModel):
    review_id: uuid.UUID
    mode: Literal["dual", "single"]
    overall_score: int = Field(..., ge=0, le=100)
    translated_text: str
    target_language: str
    audience_baseline: str
    categories: list[ReviewCategory]
    summary: str
    created_at: datetime
