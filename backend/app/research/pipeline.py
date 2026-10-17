"""Turn source evidence into a stored startup assessment."""

import os

from app.assess import DIMENSION_NAMES
from app.research.contact import find_published_contact
from app.research.links import QUEUED_TAGLINE, search_queries
from app.research.llm import JudgedAssessment, score_evidence
from app.research.sources import collect_sources
from app.research.targets import Target, startup_from_target
from app.schemas import Dimension, Profile, SourceHit, Startup


def research_company(target: Target) -> Startup:
    """Collect public evidence and, when a key is set, score and judge it."""
    startup = _stub(target)
    startup.sources = _collect(target)
    startup.name = target.name
    enrich_from_sources(startup)
    if not os.environ.get("OPENAI_API_KEY"):
        startup.judge_notes = "Set OPENAI_API_KEY to score this evidence."
        startup.assessed = False

        return startup

    try:
        judged = score_evidence(
            startup.name,
            startup.sources,
        )
    except Exception as exc:
        startup.judge_notes = f"Scoring failed: {exc}"
        startup.assessed = False

        return startup

    return apply_judgement(startup, judged)


def apply_judgement(startup: Startup, judged: JudgedAssessment) -> Startup:
    """Copy a judged assessment onto the company, keeping its id and sources."""
    startup.tagline = judged.tagline or startup.tagline
    startup.sector = judged.sector or startup.sector
    startup.country = judged.country or startup.country
    startup.stage = judged.stage or startup.stage
    startup.founded = judged.founded or startup.founded
    startup.raised = judged.raised or startup.raised
    startup.team = max(judged.team, 0)
    startup.thesis_fit = judged.thesis_fit
    startup.predicted_fit = judged.predicted_fit
    startup.ai_thoughts = judged.ai_thoughts.strip()
    startup.score_explanation = judged.score_explanation.strip()
    startup.readiness = judged.readiness
    startup.dimensions = normalize_dimensions(judged.dimensions)
    startup.signals = judged.signals[:5]
    startup.risks = judged.risks[:4]
    startup.matches = [match for match in judged.matches if match.name][:6]
    startup.next_steps = _three_steps(judged.next_steps)
    startup.profile = _merge_profile(startup.profile, judged.profile)
    if not startup.profile.website:
        startup.profile.website = _website(startup)
    startup.assessed = judged.judge_verdict != "insufficient"
    startup.judge_verdict = judged.judge_verdict
    startup.judge_notes = judged.judge_notes

    return startup


def normalize_dimensions(items: list[Dimension]) -> list[Dimension]:
    """Force the ten investment areas into the brief's order."""
    by_name = {item.name.lower(): item for item in items}
    normalized = []
    for name in DIMENSION_NAMES:
        found = by_name.get(name.lower())
        if found is None:
            normalized.append(Dimension(name=name, score=0, note="Not supported by the evidence."))
        else:
            normalized.append(Dimension(name=name, score=found.score, note=found.note))

    return normalized


def enrich_from_sources(startup: Startup) -> None:
    """Copy facts the sources state into the row before any model score."""
    website = next((hit for hit in startup.sources if hit.source == "website" and hit.found), None)
    register = next((hit for hit in startup.sources if hit.source == "prh" and hit.found), None)
    if website and website.excerpt and startup.tagline == QUEUED_TAGLINE:
        sentence = website.excerpt.split(". ")[0].strip()
        if sentence:
            startup.tagline = sentence[:180]
            startup.profile.description = startup.tagline

    if not startup.profile.email and startup.profile.website:
        email, label = find_published_contact(
            startup.profile.website,
            startup.profile.founders,
        )
        if email:
            startup.profile.email = email
        if label and not startup.profile.founders.strip():
            startup.profile.founders = label

    if register is None:
        return

    address = _labeled(register.excerpt, "Address")
    registered = _labeled(register.excerpt, "Registered")
    if address and address != "—":
        startup.profile.hq = address
        startup.country = "Finland"
    if len(registered) >= 4 and registered[:4].isdigit():
        startup.founded = int(registered[:4])


def _collect(target: Target) -> list[SourceHit]:
    """Read the site first when the name should come from its title."""
    from app.research.sources import fetch_website

    prefetched = None
    if target.rename_from_site:
        prefetched = fetch_website(target)
        if prefetched.found and prefetched.title and not prefetched.title.endswith(" website"):
            target.name = prefetched.title
            target.queries = search_queries(prefetched.title, target.website)

    return collect_sources(target, prefetched)


def _merge_profile(base: Profile, judged: Profile) -> Profile:
    """Keep source-backed profile fields when the judge leaves them empty."""
    data = base.model_dump()
    for key, value in judged.model_dump().items():
        if value not in ("", [], None):
            data[key] = value

    return type(base).model_validate(data)


def _labeled(excerpt: str, label: str) -> str:
    """Read one labelled field from a source excerpt."""
    marker = f"{label}: "
    start = excerpt.find(marker)
    if start < 0:
        return ""

    rest = excerpt[start + len(marker) :]
    end = rest.find(". ")

    return (rest if end < 0 else rest[:end]).strip()


def _stub(target: Target) -> Startup:
    """Start from an empty row so research can fill it."""
    return startup_from_target(target)


def _three_steps(steps: list[str]) -> list[str]:
    cleaned = [step for step in steps if step.strip()][:3]
    while len(cleaned) < 3:
        cleaned.append("Collect more primary evidence before a decision.")

    return cleaned


def _website(startup: Startup) -> str:
    for hit in startup.sources:
        if hit.source == "website" and hit.url:
            return hit.url.removeprefix("https://").removeprefix("http://").strip("/")

    return ""
