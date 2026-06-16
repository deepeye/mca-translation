import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    source_text: str
    genre: str  # political | news | policy | brand
    strategy: str = "semantic_equivalence"
    target_languages: list[str]  # BCP-47 codes


class TranslationResultResponse(BaseModel):
    id: uuid.UUID
    language: str
    status: str
    translated_text: str | None
    acceptance_score: int
    risk_annotations: list | None
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
