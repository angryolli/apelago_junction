"""Find one EU startup that is not already in the review table."""

import os
import re

from pydantic import BaseModel, Field

from app.research.links import normalize_url, website_key
from app.research.llm import complete
from app.research.sources import get_text
from app.research.text import html_title, visible_text
from app.schemas import ExploreResult, Startup


EXPLORE_SYSTEM = """You name one real company for an early-stage Baltic and European blue-economy fund.
The headquarters must be in the European Union.
Do not choose a company whose name or website is in the excluded list.
Return the public brand name, the EU country, an https website, and why in two sentences.
The why names the ocean, water, or maritime activity and why that fits the fund.
Do not invent funding amounts, customers, headcount, or dates."""

EU_COUNTRIES = {
    "Austria",
    "Belgium",
    "Bulgaria",
    "Croatia",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Ireland",
    "Italy",
    "Latvia",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Netherlands",
    "Poland",
    "Portugal",
    "Romania",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
}

COUNTRY_ALIASES = {
    "czech republic": "Czechia",
    "the netherlands": "Netherlands",
    "holland": "Netherlands",
}

GENERIC_TOKENS = {
    "ocean",
    "blue",
    "marine",
    "tech",
    "solutions",
    "group",
    "energy",
    "water",
    "green",
    "nordic",
    "baltic",
    "europe",
    "european",
    "company",
    "gmbh",
    "limited",
}


class ExploreError(Exception):
    """The explore request could not name a new EU startup."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Candidate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    country: str = Field(min_length=2, max_length=40)
    website: str = Field(min_length=4, max_length=200)
    why: str = Field(min_length=20, max_length=600)


def find_one(startups: list[Startup]) -> ExploreResult:
    """Name one EU startup whose website is outside the stored table."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ExploreError("Set OPENAI_API_KEY to explore a new startup.")

    excluded = [startup.name for startup in startups]
    sites = {website_key(startup.profile.website) for startup in startups if startup.profile.website}
    note = "No new EU startup could be confirmed."
    for _ in range(2):
        candidate = _ask(excluded)
        country = canonical_country(candidate.country)
        if country not in EU_COUNTRIES or already_listed(candidate.name, excluded):
            excluded.append(candidate.name)
            note = f"{candidate.name} is already listed or is outside the EU."
            continue

        try:
            website = normalize_url(candidate.website)
        except ValueError:
            excluded.append(candidate.name)
            note = f"{candidate.name} did not include a public website."
            continue

        if website_key(website) in sites or not page_mentions(candidate.name, website):
            excluded.append(candidate.name)
            note = f"{candidate.name} could not be confirmed on its website."
            continue

        return ExploreResult(
            name=candidate.name.strip(),
            why=two_sentences(candidate.why),
            country=country,
            website=website,
        )

    raise ExploreError(note)


def already_listed(name: str, existing: list[str]) -> bool:
    """Return whether this name matches a startup already stored."""
    key = name_key(name)
    if len(key) < 4:
        return True

    for item in existing:
        other = name_key(item)
        if other and (key == other or key in other or other in key):
            return True

    return False


def page_mentions(name: str, website: str) -> bool:
    """Return whether the public page shows this company name."""
    try:
        html = get_text(website)
    except Exception:
        return False

    page = f"{html_title(html)}\n{visible_text(html)}".lower()
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]{4,}", name)
        if token.lower() not in GENERIC_TOKENS
    ]
    if not tokens:
        return name_key(name) in name_key(page)

    return any(token in page for token in tokens)


def canonical_country(value: str) -> str:
    """Map a country label onto the EU member-state name."""
    cleaned = " ".join(value.split())
    alias = COUNTRY_ALIASES.get(cleaned.lower())
    if alias:
        return alias

    for country in EU_COUNTRIES:
        if country.lower() == cleaned.lower():
            return country

    return cleaned


def name_key(value: str) -> str:
    """Compare names without case, spaces, or punctuation."""
    return "".join(char.lower() for char in value if char.isalnum())


def two_sentences(text: str) -> str:
    """Keep the first two sentences of an explanation."""
    parts = re.findall(r"[^.!?]+[.!?]+", text)
    if not parts:
        return " ".join(text.split())

    return " ".join(part.strip() for part in parts[:2])


def _ask(excluded: list[str]) -> Candidate:
    names = "\n".join(f"- {name}" for name in excluded) or "- none"
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    return complete(
        model=model,
        system=EXPLORE_SYSTEM,
        user=f"Excluded companies:\n{names}",
        schema=Candidate,
    )
