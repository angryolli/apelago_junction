import re
import time
from datetime import date

from app.schemas import Dimension, Profile, Readiness, Startup

DIMENSION_NAMES = (
    "Market",
    "Product",
    "Team",
    "Business Model",
    "Competition",
    "Marketing & Distribution",
    "Financials",
    "Tech",
    "Deal Dynamics",
    "Impact",
)


def placeholder_assessment(
    name: str,
    stage: str,
    profile: Profile,
) -> Startup:
    """Score a newly added startup with a neutral placeholder assessment."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "startup"
    sector = profile.keywords[0] if profile.keywords else "Other"
    country = profile.hq.split(",")[-1].strip() or "—"

    return Startup(
        id=f"{slug}-{format(time.time_ns(), 'x')[-8:]}",
        name=name,
        tagline=profile.description,
        sector=sector,
        country=country,
        stage=stage,
        founded=date.today().year,
        raised="—",
        team=0,
        thesis_fit=0,
        readiness=Readiness(
            impact=1,
            business=1,
            tech=1,
            investment=1,
        ),
        dimensions=[Dimension(name=label, score=5) for label in DIMENSION_NAMES],
        signals=[profile.traction] if profile.traction else [],
        risks=[],
        matches=[],
        next_steps=[
            "Complete readiness assessment",
            "Request pitch deck",
            "Run investor & grant matching",
        ],
        profile=profile,
    )
