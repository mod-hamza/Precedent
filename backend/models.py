"""Pydantic v2 schemas for every LLM output (PRD §7). Field names match the PRD JSON exactly."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceRole = Literal["proposal", "discussion", "objection", "approval", "confirmation", "reversal", "recap"]


# ---------- Stage 0: identity adjudication (FAST) ----------
class IdentityVerdict(BaseModel):
    same_person: bool
    reason: str = Field(description="one short sentence")


class RoleGuess(BaseModel):
    role: str | None = Field(description="short job title, or null if the emails do not show it")
    basis: str = Field(description="one short sentence")


# ---------- Stage 1: triage (FAST) ----------
Signal = Literal["none", "discussion", "proposal", "approval", "decision", "reversal", "commitment", "question"]


class TriageMessage(BaseModel):
    message_id: str
    signal: Signal
    note: str = Field(description="15 words or fewer")


class TriageResult(BaseModel):
    thread_id: str
    has_candidate: bool
    messages: list[TriageMessage]


# ---------- Stage 2: extraction (CORE) ----------
class Evidence(BaseModel):
    message_id: str
    quote: str = Field(description="verbatim from the message's new or forwarded text, 40 words or fewer")
    role: EvidenceRole


class DecisionRecord(BaseModel):
    topic_label: str
    decision_text: str
    stance: Literal["final", "tentative", "proposed", "conditional", "retracted"]
    decision_type: Literal["explicit", "implicit"]
    decided_by: list[str]
    decision_date: str = Field(description="YYYY-MM-DD")
    rationale: str | None
    alternatives: list[str]
    conditions: str | None
    overrides_hint: str | None
    authority_note: str | None
    evidence: list[Evidence]
    confidence: float


class ExtractionResult(BaseModel):
    records: list[DecisionRecord]


# ---------- Stage 4: reconcile (REASON) ----------
class ReconciledDecision(BaseModel):
    decision_id_temp: str
    canonical_text: str
    decided_by: list[str]
    decided_at: str = Field(description="YYYY-MM-DD")
    rationale: str | None
    alternatives: list[str]
    decision_type: Literal["explicit", "implicit"]
    status: Literal["active", "superseded", "amended", "contested"]
    authority_flag: bool
    authority_note: str | None
    merged_record_ids: list[str]
    confidence: float
    evidence: list[Evidence]


class Edge(BaseModel):
    src: str = Field(description="the NEWER decision")
    dst: str
    kind: Literal["supersedes", "amends", "refines"]
    scope: Literal["full", "partial"]
    aspect: str | None
    rationale: str | None


class ConflictSide(BaseModel):
    claimant: str
    claim: str
    evidence: list[Evidence]


class Conflict(BaseModel):
    topic: str
    summary: str
    sides: list[ConflictSide]


class NonDecision(BaseModel):
    record_ids: list[str]
    reason: str


class ReconcileResult(BaseModel):
    cluster_topic: str
    decisions: list[ReconciledDecision]
    edges: list[Edge]
    conflicts: list[Conflict]
    current_state: str
    non_decisions: list[NonDecision]


# ---------- Stage 6: ask ----------
class QuestionClass(BaseModel):
    type: Literal["current_state", "why", "history", "who", "existence", "as_of", "other"]
    entities: list[str]
    as_of_date: str | None = Field(description="YYYY-MM-DD or null")


class Citation(BaseModel):
    n: int
    message_id: str
    quote: str


class Closest(BaseModel):
    message_id: str
    why: str


class Answer(BaseModel):
    status: Literal["found", "contested", "no_decision", "partial"]
    answer_md: str
    citations: list[Citation]
    decision_ids: list[str]
    confidence: Literal["high", "medium", "low"]
    caveats: list[str]
    closest: list[Closest]


# ---------- Stage 3: clustering (REASON) ----------
class TopicGroup(BaseModel):
    label: str = Field(description="short topic name, e.g. 'Payment provider'")
    record_ids: list[str]


class ClusterResult(BaseModel):
    groups: list[TopicGroup]
