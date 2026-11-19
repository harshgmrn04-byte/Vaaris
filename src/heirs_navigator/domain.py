from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CaseFacts(BaseModel):
    bank: str | None = None
    product: Literal["savings", "current", "fd", "rd", "locker", "safe_custody"] | None = None
    nominee_exists: bool | None = None
    nominee_count: int | None = None
    mode_of_operation: str | None = None
    will: Literal["none", "undisputed", "disputed"] | None = None
    dispute: bool | None = None
    amount_band: str | None = None
    claimant_role: str | None = None
    notes: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    title: str
    issuer: str
    doc_type: str
    url: str
    effective_date: date
    status: Literal["final", "draft", "superseded"]
    bank: str = ""
    redistribution: Literal["public_ok", "fetch_only", "unclear"] = "unclear"


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    section: str
    page: int
    text: str
    token_count: int
    issuer: str
    doc_type: str
    bank: str
    effective_date: date
    status: Literal["final", "draft", "superseded"]


class Evidence(BaseModel):
    chunk: Chunk
    rrf_score: float = 0
    rerank_score: float | None = None


class ChecklistItem(BaseModel):
    document: str
    why_needed: str
    citation_ids: list[str] = Field(min_length=1)
    condition: str | None = None


class Checklist(BaseModel):
    items: list[ChecklistItem]
    next_steps: list[str]
    citation_ids: list[str] = Field(default_factory=list)


class CaseState(BaseModel):
    case_id: str
    facts: CaseFacts = Field(default_factory=CaseFacts)
    docs_have: list[str] = Field(default_factory=list)
    docs_missing: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    checklist: Checklist | None = None
    flags: list[str] = Field(default_factory=list)
    escalation: str | None = None
    corpus_version: str = ""
