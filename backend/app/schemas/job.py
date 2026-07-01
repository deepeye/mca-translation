import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CulturalLoadedTerm(BaseModel):
    term: str
    culture_gap: Literal["low", "medium", "high"]
    adaptation_strategy: Literal["literal", "explanatory", "analogical", "reconstruction"]
    suggested_rendering: str
    reason: str


class CulturalPreprocessResult(BaseModel):
    culture_loaded_terms: list[CulturalLoadedTerm] = Field(default_factory=list)
    cultural_notes: list[str] = Field(default_factory=list)
    taboo_warnings: list[str] = Field(default_factory=list)


class CreateJobRequest(BaseModel):
    source_text: str
    genre: str  # political | news | policy | brand
    strategy: str = "semantic_equivalence"
    target_languages: list[str]  # BCP-47 codes
    cultural_sphere: Optional[str] = None
    audience_type: Optional[str] = None


class TranslationResultResponse(BaseModel):
    id: uuid.UUID
    language: str
    status: str
    translated_text: str | None
    acceptance_score: int
    risk_annotations: list | None
    cultural_adaptation: Optional[CulturalPreprocessResult] = None
    created_at: datetime


class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    source_text: str
    genre: str
    strategy: str
    target_languages: list[str]
    results: list[TranslationResultResponse]
    created_at: datetime


class JobListItem(BaseModel):
    id: uuid.UUID
    status: str
    genre: str
    target_languages: list[str]
    source_text: str | None = None       # 新增：列表页原文摘要
    created_at: datetime


class Suggestion(BaseModel):
    text: str
    reason: str


class SuggestionResponse(BaseModel):
    suggestions: list[Suggestion]


class AcceptRiskRequest(BaseModel):
    suggestion: str
    lang: str


class DismissRiskRequest(BaseModel):
    lang: str


class RevertRiskRequest(BaseModel):
    lang: str


class AcceptAllRequest(BaseModel):
    lang: str


# ---- 接受度评分（acceptance scoring）请求/响应 ----
from app.schemas.acceptance import AcceptanceResult  # noqa: E402


class AcceptanceScoreRequest(BaseModel):
    """首次接受度评分请求体。"""
    lang: str
    audience_baseline: Literal["policy_media", "academic", "social_media"] = "policy_media"


class AcceptanceScoreDeltaRequest(BaseModel):
    """单句改写后 delta 重算请求体。"""
    lang: str
    sentence_id: str
    new_text: str


class AcceptanceScoreResponse(BaseModel):
    """接受度评分响应 — 镜像 AcceptanceResult 公开字段。"""
    total_score: int
    dimensions: dict
    confidence: float
    top3_risk_indices: list[int] = Field(default_factory=list)
    audience_baseline: str
