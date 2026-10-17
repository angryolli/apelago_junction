"""Write investor questions from a stored startup assessment."""

import os

from pydantic import BaseModel, Field

from app.research.llm import complete
from app.schemas import Inquiry, Startup


INQUIRE_SYSTEM = """You prepare an investor inquiry for one blue-economy startup.
Use only the stored assessment. Do not invent customers, contracts, funding amounts, headcount, or dates.
questions must be exactly five. Each one is a single sentence an investor should still confirm, in the shape "Confirm whether ...".
If the record does not establish a customer, amount, or date, do not refer to it as a fact.
risks lists up to four outstanding risks already supported by the stored record.
introductions lists up to four organisations worth an introduction, only when a stored match supports them. Each item names the organisation and the reason.
opportunities lists up to four funding or partnership openings grounded in the stored matches. Each item names the opening and the reason."""


class InquiryDraft(BaseModel):
    questions: list[str] = Field(min_length=5, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=4)
    introductions: list[str] = Field(default_factory=list, max_length=4)
    opportunities: list[str] = Field(default_factory=list, max_length=4)


def investor_inquiry(startup: Startup) -> Inquiry:
    """Build five questions plus risks, introductions, and openings."""
    if not os.environ.get("OPENAI_API_KEY"):
        return from_record(startup)

    model = os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4.1")
    try:
        drafted = complete(
            model=model,
            system=INQUIRE_SYSTEM,
            user=_packet(startup),
            schema=InquiryDraft,
        )
    except Exception:
        return from_record(startup)

    return _filled(drafted, startup)


def from_record(startup: Startup) -> Inquiry:
    """Derive the inquiry from scores, risks, and matches already stored."""
    questions = [f"Confirm whether this is still open: {risk.strip()}" for risk in startup.risks if risk.strip()]
    for gap in _gaps():
        if len(questions) >= 5:
            break
        if gap not in questions:
            questions.append(gap)

    risks = [risk.strip() for risk in startup.risks if risk.strip()][:4]
    introductions = [
        f"{match.name}: {match.why}".strip()
        for match in startup.matches
        if match.type in {"Investor", "Partner", "Client"} and match.name.strip()
    ][:4]
    opportunities = [
        f"{match.name} ({match.type}): {match.why}".strip()
        for match in startup.matches
        if match.type in {"Grant", "Investor", "Partner"} and match.name.strip()
    ][:4]

    return Inquiry(
        questions=questions[:5],
        risks=risks or ["No outstanding risk is recorded on this assessment yet."],
        introductions=introductions or ["No introduction is supported by the stored matches yet."],
        opportunities=opportunities or ["No funding or partnership opening is recorded yet."],
    )


def _filled(drafted: InquiryDraft, startup: Startup) -> Inquiry:
    stored = from_record(startup)
    questions = [item.strip() for item in drafted.questions if item.strip()]
    for extra in stored.questions:
        if len(questions) >= 5:
            break
        if extra not in questions:
            questions.append(extra)

    return Inquiry(
        questions=questions[:5],
        risks=_or_stored(drafted.risks, stored.risks),
        introductions=_or_stored(drafted.introductions, stored.introductions),
        opportunities=_or_stored(drafted.opportunities, stored.opportunities),
    )


def _or_stored(drafted: list[str], stored: list[str]) -> list[str]:
    cleaned = [item.strip() for item in drafted if item.strip()]

    return (cleaned or stored)[:4]


def _gaps() -> list[str]:
    return [
        "Confirm whether any pilot has converted into a paid annual contract.",
        "Confirm what funding has been received, and whether any named grant was actually awarded.",
        "Confirm who the paying customers are, and the length of those contracts.",
        "Confirm the technology readiness with evidence beyond company-reported results.",
        "Confirm which investor, grant, or partner is the strongest next introduction.",
    ]


def _packet(startup: Startup) -> str:
    risks = "; ".join(startup.risks) or "None recorded"
    signals = "; ".join(startup.signals) or "None recorded"
    matches = "; ".join(f"{match.type}: {match.name} — {match.why}" for match in startup.matches) or "None recorded"
    funding = startup.profile.funding or startup.raised or "Not recorded"
    traction = startup.profile.traction or "Not recorded"

    return "\n".join(
        [
            f"name: {startup.name}",
            f"sector: {startup.sector}",
            f"country: {startup.country}",
            f"assessed: {startup.assessed}",
            f"ocean_impact: {startup.readiness.impact}/9",
            f"brl: {startup.readiness.business}/9",
            f"trl: {startup.readiness.tech}/9",
            f"investment_readiness: {startup.readiness.investment}/9",
            f"traction: {traction}",
            f"funding: {funding}",
            f"risks: {risks}",
            f"signals: {signals}",
            f"matches: {matches}",
        ]
    )
