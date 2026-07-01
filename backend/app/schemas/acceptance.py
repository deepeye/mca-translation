"""接受度评分的 Pydantic schema 契约。"""

from typing import Literal
from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    """四维评分，各 0-25，合计 0-100。"""
    audience: float = Field(..., ge=0, le=25)       # 受众匹配度
    cultural: float = Field(..., ge=0, le=25)      # 文化敏感度
    naturalness: float = Field(..., ge=0, le=25)   # 表达自然度
    risk: float = Field(..., ge=0, le=25)          # 风险词密度分（越高=风险越少）


class SentenceScore(BaseModel):
    """单句评分。score 为四维之和（0-100），失败时 -1。"""
    sentence_id: str
    dimensions: DimensionScores
    confidence: float = Field(..., ge=0, le=1)
    risk_phrase_offsets: list[tuple[int, int]] = Field(default_factory=list)
    affects_neighbors: bool = False
    rationale: str = ""
    failed: bool = False

    @property
    def score(self) -> int:
        if self.failed:
            return -1
        return int(round(self.dimensions.audience + self.dimensions.cultural
                         + self.dimensions.naturalness + self.dimensions.risk))


class AcceptanceResult(BaseModel):
    """全文接受度评分结果。"""
    total_score: int = Field(..., ge=-1, le=100)
    dimensions: DimensionScores
    confidence: float = Field(..., ge=0, le=1)
    top3_risk_indices: list[int] = Field(default_factory=list)
    sentence_scores: list[SentenceScore] = Field(default_factory=list)
    audience_baseline: Literal["policy_media", "academic", "social_media"]
