from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Readiness(BaseModel):
    impact: int = Field(ge=1, le=9)
    business: int = Field(ge=1, le=9)
    tech: int = Field(ge=1, le=9)
    investment: int = Field(ge=1, le=9)


class Dimension(BaseModel):
    name: str
    score: int = Field(ge=0, le=10)
    note: str = ""


class Match(BaseModel):
    name: str
    type: Literal["Investor", "Grant", "Partner", "Client"]
    fit: int = Field(ge=0, le=100)
    why: str
    region: str


class SourceHit(BaseModel):
    source: Literal["website", "dealroom", "blueinvest", "business_finland", "prh", "cordis"]
    title: str
    url: str
    excerpt: str
    found: bool = True


class Profile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    website: str = ""
    hq: str = ""
    founders: str = ""
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    problem: str = ""
    solution: str = ""
    business_model: str = Field(default="", alias="businessModel")
    customers: str = ""
    traction: str = ""
    funding: str = ""
    advantage: str = ""
    competitors: str = ""
    thesis: str = ""


class Startup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    tagline: str
    sector: str
    country: str
    stage: str
    founded: int
    raised: str
    team: int = Field(ge=0)
    thesis_fit: int = Field(
        ge=0,
        le=100,
        alias="thesisFit",
    )
    predicted_fit: int = Field(
        default=0,
        ge=0,
        le=100,
        alias="predictedFit",
    )
    ai_thoughts: str = Field(
        default="",
        alias="aiThoughts",
    )
    score_explanation: str = Field(
        default="",
        alias="scoreExplanation",
    )
    readiness: Readiness
    dimensions: list[Dimension]
    signals: list[str]
    risks: list[str]
    matches: list[Match]
    next_steps: list[str] = Field(alias="nextSteps")
    profile: Profile
    sources: list[SourceHit] = Field(default_factory=list)
    assessed: bool = False
    judge_verdict: str = Field(default="", alias="judgeVerdict")
    judge_notes: str = Field(default="", alias="judgeNotes")


class ResearchRequest(BaseModel):
    names: list[str] = Field(default_factory=list)
    ids: list[str] = Field(default_factory=list)


class ResearchStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["idle", "running", "done", "error"]
    message: str = ""
    current: str = ""
    completed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    finished_at: str = Field(default="", alias="finishedAt")


class CreateFromLink(BaseModel):
    url: str
    name: str = ""

    @field_validator("url")
    @classmethod
    def normalize_link(cls, value: str) -> str:
        """Require an http or https website."""
        from app.research.links import normalize_url

        return normalize_url(value)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Keep an optional display name trimmed."""
        return value.strip()


class LinkCreated(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    startup: Startup
    research: ResearchStatus


class CompareRequest(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=4)
    thesis: str = Field(min_length=1, max_length=240)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        """Keep two to four distinct startup ids."""
        cleaned: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped and stripped not in cleaned:
                cleaned.append(stripped)
        if len(cleaned) < 2:
            raise ValueError("choose at least two startups")

        return cleaned

    @field_validator("thesis")
    @classmethod
    def strip_thesis(cls, value: str) -> str:
        """Reject a blank investor thesis."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")

        return stripped


class CompareResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    preferred_id: str = Field(alias="preferredId")
    preferred_name: str = Field(alias="preferredName")
    explanation: str


class Inquiry(BaseModel):
    questions: list[str]
    risks: list[str]
    introductions: list[str]
    opportunities: list[str]


class ExploreResult(BaseModel):
    name: str
    why: str
    country: str
    website: str


class CreateStartup(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    stage: str = "Pre-seed"
    profile: Profile = Field(default_factory=Profile)

    @field_validator("name", "stage")
    @classmethod
    def strip_text(cls, value: str) -> str:
        """Reject blank names and stages after trimming."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")

        return stripped
