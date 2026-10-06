"""LLM judges for the eval harness (JUDGE role: a different model family from the extractor; different prompts)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from backend.llm import LLM


class SameDecision(BaseModel):
    verdict: Literal["yes", "partial", "no"]
    reason: str


class AssertsDecided(BaseModel):
    asserts_decided: bool
    reason: str


class Supports(BaseModel):
    supports: bool
    reason: str


class QAJudgement(BaseModel):
    facts_present: bool
    unsupported_claims: bool
    reason: str


SAME_PROMPT = """You compare two statements of a business decision from a company's records.
Answer "yes" if they describe the same decision (same subject and the same choice; wording, detail level and minor
details may differ), "partial" if they describe the same decision but one gets a material element wrong or covers only
part of it (e.g. right vendor, wrong date; or only one of two choices), and "no" otherwise. A decision and a different
step in the same topic's history (an earlier plan it replaced, a later change) is "no"."""

NEAR_PROMPT = """A topic was discussed at a company but NEVER actually decided. Judge whether the given ledger entry
claims that this topic WAS decided (approved, settled, committed to). An entry that records it as deferred, rejected,
only proposed or still open does not assert it was decided."""

SUPPORT_PROMPT = """Judge whether a quoted sentence from an email supports (is direct evidence for) the stated decision,
its rationale, or an objection or proposal that led to it. Generic or unrelated quotes do not support it."""

QA_PROMPT = """You grade an answer from a decision-tracking assistant against a reference answer.
facts_present: the answer contains the facts in the reference (names, numbers, dates, the chosen option); extra correct
detail is fine; wording may differ. For a reference saying no decision exists, the answer must clearly say no decision
was made.
unsupported_claims: the answer states something material that the cited quotes do not support and that contradicts or
goes beyond the reference."""


async def same_decision(llm: LLM, predicted: str, pred_date: str, gt: str, gt_date: str) -> SameDecision:
    user = f"A ({pred_date}): {predicted}\nB ({gt_date}): {gt}"
    return await llm.structured("JUDGE", SAME_PROMPT, user, SameDecision, stage="eval_match")


async def asserts_decided(llm: LLM, topic: str, outcome: str, entry: str) -> AssertsDecided:
    user = f"Topic that was never decided: {topic}\nWhat actually happened: {outcome}\n\nLedger entry: {entry}"
    return await llm.structured("JUDGE", NEAR_PROMPT, user, AssertsDecided, stage="eval_near")


async def supports(llm: LLM, decision: str, quote: str) -> Supports:
    user = f"Decision: {decision}\nQuote: \"{quote}\""
    return await llm.structured("JUDGE", SUPPORT_PROMPT, user, Supports, stage="eval_support")


async def grade_answer(llm: LLM, question: str, reference: str, answer_md: str, quotes: list[str]) -> QAJudgement:
    cited = "\n".join(f"- \"{q}\"" for q in quotes) or "(no citations)"
    user = f"Question: {question}\nReference answer: {reference}\n\nAnswer to grade:\n{answer_md}\n\nCited quotes:\n{cited}"
    return await llm.structured("JUDGE", QA_PROMPT, user, QAJudgement, stage="eval_qa")
