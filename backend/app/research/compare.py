"""Compare stored assessments against one investor thesis."""

import os

from pydantic import BaseModel, Field

from app.research.llm import complete
from app.schemas import Startup


COMPARE_SYSTEM = """You compare two to four blue-economy startups for one investor thesis.
Use only the stored assessment. Do not invent funding, customers, dates, or traction.
preferred_id must be one of the given ids.
explanation is three or four sentences: which startup is the better match for the thesis, which stored scores and evidence support that, and the main risk or missing evidence that could change the choice."""


class CompareJudgement(BaseModel):
    preferred_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


def explain_match(
    thesis: str,
    startups: list[Startup],
) -> CompareJudgement:
    """Pick the closer thesis match from stored scores."""
    if not os.environ.get("OPENAI_API_KEY"):
        return from_scores(thesis, startups)

    model = os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4.1")
    try:
        judged = complete(
            model=model,
            system=COMPARE_SYSTEM,
            user=_packet(thesis, startups),
            schema=CompareJudgement,
        )
    except Exception as exc:
        scored = from_scores(thesis, startups)
        scored.explanation = f"The thesis explanation failed ({exc}). {scored.explanation}"
        return scored

    known = {startup.id for startup in startups}
    if judged.preferred_id not in known:
        return from_scores(thesis, startups)

    return judged


def from_scores(
    thesis: str,
    startups: list[Startup],
) -> CompareJudgement:
    """Rank the set by the scores already stored."""
    best = max(
        startups,
        key=lambda startup: (
            startup.assessed,
            startup.thesis_fit,
            startup.readiness.investment,
            startup.readiness.impact,
            startup.readiness.tech,
        ),
    )
    explanation = (
        f"{best.name} is the closer stored match for “{thesis}”, "
        f"with thesis fit {best.thesis_fit}/100, ocean impact {best.readiness.impact}/9, "
        f"BRL {best.readiness.business}/9, TRL {best.readiness.tech}/9, "
        f"and investment readiness {best.readiness.investment}/9. "
        "Set OPENAI_API_KEY for a judged explanation of this comparison."
    )

    return CompareJudgement(
        preferred_id=best.id,
        explanation=explanation,
    )


def _packet(
    thesis: str,
    startups: list[Startup],
) -> str:
    blocks = [f"Investor thesis: {thesis}", ""]
    for startup in startups:
        risks = "; ".join(startup.risks) or "None recorded"
        signals = "; ".join(startup.signals) or "None recorded"
        funding = startup.profile.funding or startup.raised or "Not recorded"
        growth = startup.profile.traction or "Not recorded"
        blocks.append(
            "\n".join(
                [
                    f"id: {startup.id}",
                    f"name: {startup.name}",
                    f"assessed: {startup.assessed}",
                    f"thesis_fit: {startup.thesis_fit}/100",
                    f"ocean_impact: {startup.readiness.impact}/9",
                    f"brl: {startup.readiness.business}/9",
                    f"trl: {startup.readiness.tech}/9",
                    f"investment_readiness: {startup.readiness.investment}/9",
                    f"growth: {growth}",
                    f"funding: {funding}",
                    f"risks: {risks}",
                    f"signals: {signals}",
                ]
            )
        )
        blocks.append("")

    return "\n".join(blocks).strip()
