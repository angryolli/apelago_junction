"""The six companies the MVP researches from public sources."""

from app.assess import DIMENSION_NAMES
from app.schemas import Dimension, Profile, Readiness, Startup

PORTFOLIO_VERSION = "3"


class Target:
    def __init__(
        self,
        startup_id: str,
        name: str,
        website: str,
        sector: str,
        tagline: str,
        queries: list[str],
        rename_from_site: bool = False,
    ) -> None:
        self.id = startup_id
        self.name = name
        self.website = website
        self.sector = sector
        self.tagline = tagline
        self.queries = queries
        self.rename_from_site = rename_from_site


TARGETS: list[Target] = [
    Target(
        startup_id="npharvest",
        name="NPHarvest",
        website="https://www.npharvest.fi/",
        sector="Water",
        tagline="Nutrient recovery from wastewater",
        queries=["NPHarvest Oy", "NPHarvest"],
    ),
    Target(
        startup_id="weeefiner",
        name="Weeefiner",
        website="https://www.weeefiner.fi/",
        sector="Water",
        tagline="Industrial water treatment and dissolved-metal recovery",
        queries=["Weeefiner Oy", "Weeefiner"],
    ),
    Target(
        startup_id="origin-by-ocean",
        name="Origin by Ocean",
        website="https://originbyocean.com/",
        sector="Biomaterials",
        tagline="Turns algae biomass into everyday materials",
        queries=["Ocean Orchard Oy", "Origin by Ocean"],
    ),
    Target(
        startup_id="awake-ai",
        name="Awake.AI",
        website="https://www.awake.ai/",
        sector="Shipping",
        tagline="AI for port calls and maritime logistics",
        queries=["Awake.AI Oy", "Awake AI Oy", "Awake.AI"],
    ),
    Target(
        startup_id="norsepower",
        name="Norsepower",
        website="https://www.norsepower.com/",
        sector="Shipping",
        tagline="Rotor sails that add wind propulsion to ships",
        queries=["Norsepower Oy", "Norsepower"],
    ),
    Target(
        startup_id="wesi",
        name="WESI Solutions",
        website="https://wesi.fi/",
        sector="Aquaculture",
        tagline="AI automation for fish farming",
        queries=["Arctic Fry Oy", "WESI Solutions Oy", "WESI Solutions"],
    ),
]


def startup_from_target(target: Target) -> Startup:
    """Build an unassessed startup row from a research target."""
    country = "Finland" if target.sector != "Unclassified" else "—"

    return Startup(
        id=target.id,
        name=target.name,
        tagline=target.tagline,
        sector=target.sector,
        country=country,
        stage="—",
        founded=0,
        raised="—",
        team=0,
        thesis_fit=0,
        readiness=Readiness(
            impact=1,
            business=1,
            tech=1,
            investment=1,
        ),
        dimensions=[Dimension(name=name, score=0) for name in DIMENSION_NAMES],
        signals=[],
        risks=[],
        matches=[],
        next_steps=[
            "Run source research",
            "Score the evidence",
            "Review the judge's notes",
        ],
        profile=Profile(
            website=target.website.removeprefix("https://").removeprefix("http://").strip("/"),
            description=target.tagline,
            keywords=[target.sector, "Blue economy"],
        ),
        assessed=False,
    )


def portfolio_startups() -> list[Startup]:
    """Build the six companies before any source has been scored."""
    return [startup_from_target(target) for target in TARGETS]


def select_targets(names: list[str]) -> tuple[list[Target], list[str]]:
    """Match requested names to the portfolio and list the ones that do not match."""
    if not names:
        return list(TARGETS), []

    chosen = []
    missing = []
    for name in names:
        folded = name.strip().lower()
        match = next(
            (
                target
                for target in TARGETS
                if folded in {target.name.lower(), target.id}
            ),
            None,
        )
        if match is None:
            missing.append(name)
        elif match not in chosen:
            chosen.append(match)

    return chosen, missing
