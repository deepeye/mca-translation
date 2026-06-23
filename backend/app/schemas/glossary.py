import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.constants.glossary_categories import SYSTEM_GLOSSARY_TERM_TYPES, USER_GLOSSARY_TERM_TYPES

SystemGlossaryTermType = Literal[*SYSTEM_GLOSSARY_TERM_TYPES]
UserGlossaryTermType = Literal[*USER_GLOSSARY_TERM_TYPES]


class TranslationEntry(BaseModel):
    preferred: str
    alternatives: list[str] = Field(default_factory=list)
    notes: str = ""


class GlossaryEntryCreate(BaseModel):
    source_term: str
    term_type: SystemGlossaryTermType = "political_discourse"
    translations: dict[str, TranslationEntry] = Field(default_factory=dict)
    risk_notes: str = ""
    applicable_genres: list[str] = Field(default_factory=list)


class GlossaryEntryUpdate(BaseModel):
    source_term: Optional[str] = None
    term_type: Optional[SystemGlossaryTermType] = None
    translations: Optional[dict[str, TranslationEntry]] = None
    risk_notes: Optional[str] = None
    applicable_genres: Optional[list[str]] = None
    freshness_date: Optional[datetime] = None


class GlossaryEntryResponse(BaseModel):
    id: uuid.UUID
    source_term: str
    term_type: str
    translations: dict
    risk_notes: Optional[str] = None
    applicable_genres: Optional[list[str]] = None
    freshness_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserGlossaryEntryCreate(BaseModel):
    source_term: str
    term_type: UserGlossaryTermType = "user_defined"
    translations: dict[str, TranslationEntry] = Field(default_factory=dict)
    risk_notes: str = ""
    applicable_genres: list[str] = Field(default_factory=list)


class UserGlossaryEntryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_term: str
    term_type: str
    translations: dict
    risk_notes: Optional[str] = None
    applicable_genres: Optional[list[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GlossarySearchRequest(BaseModel):
    text: str
    language: str = "en-GB"
    genre: Optional[str] = None
    strategy: str = "semantic_equivalence"
    top_k: int = 5


class GlossarySearchResultItem(BaseModel):
    id: uuid.UUID
    source_term: str
    term_type: str
    translations: dict
    risk_notes: Optional[str] = None
    score: float
    source: Literal["system_kb", "user_glossary"]


class GlossarySearchResponse(BaseModel):
    terms: list[GlossarySearchResultItem]
