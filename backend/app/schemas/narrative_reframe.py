from typing import Literal

from pydantic import BaseModel, Field


NarrativeReasonLabel = Literal["audience_habit", "cultural_context", "communication"]
NarrativePreviewMode = Literal["light_cohesion"]


class NarrativeOutlineItem(BaseModel):
    id: str
    order: int
    summary: str
    text_span: str


class NarrativeRecommendedItem(BaseModel):
    id: str
    target_order: int
    source_ref_ids: list[str] = Field(default_factory=list)
    summary: str
    reason_label: NarrativeReasonLabel
    reason: str
    expected_effect: str


class NarrativeReframeAnalysis(BaseModel):
    source_outline: list[NarrativeOutlineItem] = Field(default_factory=list)
    current_translation_outline: list[NarrativeOutlineItem] = Field(default_factory=list)
    recommended_outline: list[NarrativeRecommendedItem] = Field(default_factory=list)
    overall_rationale: str
    confidence: float = Field(ge=0, le=1)


class NarrativeAnalyzeRequest(BaseModel):
    lang: str


class NarrativeAnalyzeResponse(BaseModel):
    analysis: NarrativeReframeAnalysis
    text_hash: str


class NarrativePreviewRequest(BaseModel):
    lang: str
    analysis: NarrativeReframeAnalysis
    text_hash: str
    mode: NarrativePreviewMode = "light_cohesion"


class NarrativePreviewResponse(BaseModel):
    preview_text: str
    text_hash: str


class NarrativeApplyRequest(BaseModel):
    lang: str
    preview_text: str
    analysis: NarrativeReframeAnalysis
    text_hash: str


class NarrativeApplyResponse(BaseModel):
    result: dict
    text_hash: str
