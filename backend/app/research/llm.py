"""Score collected evidence, then have a second model judge the draft."""

import os
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import Dimension, Match, Profile, Readiness, SourceHit

RESEARCH_SYSTEM = """You assess a blue-economy company for Redstone Blue and A'Pelago.
Use only the evidence. Do not invent funding amounts, customers, partners, headcount, or dates.
If a fact is missing, leave the text field empty and use a low score.
Readiness levels are 1-9: ocean impact, business (BRL), technology (TRL), and investment readiness.
Score the ten investment areas from 0 to 10: Market, Product, Team, Business Model, Competition, Marketing & Distribution, Financials, Tech, Deal Dynamics, Impact.
thesis_fit is 0-100 for fit with an early-stage Baltic and European blue-economy fund.
Matches may be recorded relationships or clearly relevant next programmes. Say which in why.
Return exactly three concrete next steps."""

JUDGE_SYSTEM = """You are the judge of a venture assessment.
Compare the draft with the evidence. Lower any score, delete any match, and rewrite any sentence that the evidence does not support.
Keep recorded facts that the evidence does support.
Set judge_verdict to supported, revised, or insufficient.
judge_notes must say what you changed and which sources were missing.
predicted_fit is a second score from 0 to 100: the anticipated fit if the company continues only on the path the evidence already supports. It may differ from thesis_fit. Do not assume customers, funding, or dates that are not in the evidence.
ai_thoughts is two sentences explaining that anticipated ranking: what in the evidence supports it, and what is still missing.
score_explanation is two or three sentences: "{Company} scores N/100 because ... ." Name the areas that carried the most weight, the evidence those weights rest on, the strengths, the weaknesses, and the missing data.
Do not add facts that are not in the evidence."""


class DraftAssessment(BaseModel):
    tagline: str = ""
    sector: str = ""
    country: str = ""
    stage: str = ""
    founded: int = 0
    raised: str = "—"
    team: int = 0
    thesis_fit: int = Field(ge=0, le=100)
    readiness: Readiness
    dimensions: list[Dimension]
    signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    matches: list[Match] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    profile: Profile = Field(default_factory=Profile)


class JudgedAssessment(DraftAssessment):
    judge_verdict: Literal["supported", "revised", "insufficient"]
    judge_notes: str
    predicted_fit: int = Field(ge=0, le=100)
    ai_thoughts: str
    score_explanation: str


def research_model() -> str:
    """Return the model that writes the first assessment."""
    return os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")


def judge_model() -> str:
    """Return the model that checks the draft against the evidence."""
    return os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4.1")


def score_evidence(company_name: str, hits: list[SourceHit]) -> JudgedAssessment:
    """Draft an assessment from the evidence, then judge that draft."""
    evidence = format_evidence(hits)
    draft = complete(
        model=research_model(),
        system=RESEARCH_SYSTEM,
        user=f"Company: {company_name}\n\nEvidence:\n{evidence}",
        schema=DraftAssessment,
    )
    judged = complete(
        model=judge_model(),
        system=JUDGE_SYSTEM,
        user=(
            f"Company: {company_name}\n\nEvidence:\n{evidence}\n\n"
            f"Draft:\n{draft.model_dump_json()}"
        ),
        schema=JudgedAssessment,
    )

    return judged


def format_evidence(hits: list[SourceHit]) -> str:
    """Render source hits as plain text for the model."""
    blocks = []
    for hit in hits:
        state = "FOUND" if hit.found else "NOT FOUND"
        blocks.append(
            f"[{hit.source}] {state}\nTitle: {hit.title}\nURL: {hit.url}\n{hit.excerpt}"
        )

    return "\n\n".join(blocks)


def complete[SchemaT: BaseModel](
    *,
    model: str,
    system: str,
    user: str,
    schema: type[SchemaT],
) -> SchemaT:
    """Ask OpenAI for one structured assessment."""
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=schema,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("The model returned no structured assessment.")

    return parsed
