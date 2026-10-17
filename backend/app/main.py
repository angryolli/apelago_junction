import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.repository import Repository
from app.research.compare import explain_match
from app.research.jobs import enqueue, get_status, start_research
from app.research.links import find_by_website, queued_startup, target_from_link
from app.schemas import (
    CompareRequest,
    CompareResult,
    CreateFromLink,
    CreateStartup,
    LinkCreated,
    ResearchRequest,
    ResearchStatus,
    Startup,
)


def database_path() -> Path:
    """Resolve the SQLite file from the environment."""
    return Path(os.environ.get("DATABASE_PATH", "data/radar.db"))


def cors_origins() -> list[str]:
    """Read allowed browser origins, defaulting to the local frontend."""
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )

    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def blank_to_none(value: str | None) -> str | None:
    """Treat missing and whitespace-only filters as unset."""
    if value is None:
        return None

    stripped = value.strip()

    return stripped or None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database before the API starts serving."""
    repository = Repository(database_path())
    repository.init()
    app.state.repository = repository
    yield


app = FastAPI(
    title="Ocean Opportunity Radar",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_repository(request: Request) -> Repository:
    """Return the repository created for this process."""
    return request.app.state.repository


Repo = Annotated[Repository, Depends(get_repository)]


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report that the API process is serving requests."""
    return {"status": "ok"}


@app.get("/api/sectors")
def list_sectors(repo: Repo) -> list[str]:
    """Return sectors available for the review filter."""
    return repo.sectors()


@app.get("/api/startups")
def list_startups(
    repo: Repo,
    q: str | None = None,
    sector: str | None = None,
) -> list[Startup]:
    """Return startups ranked by fit with the fund thesis."""
    return repo.list_startups(
        query=blank_to_none(q),
        sector=blank_to_none(sector),
    )


@app.get("/api/startups/{startup_id}")
def get_startup(startup_id: str, repo: Repo) -> Startup:
    """Return the full assessment for one startup."""
    startup = repo.get(startup_id)
    if startup is None:
        raise HTTPException(status_code=404, detail="Startup not found")

    return startup


@app.get("/api/research")
def read_research() -> ResearchStatus:
    """Return the current source-research job."""
    return get_status()


@app.post("/api/research")
def begin_research(body: ResearchRequest, repo: Repo) -> ResearchStatus:
    """Collect public sources and score them when an OpenAI key is set."""
    return start_research(
        repo,
        body.names,
        body.ids,
    )


@app.post("/api/startups/from-link", status_code=201)
def create_from_link(body: CreateFromLink, repo: Repo) -> LinkCreated:
    """Add a company from its website and research it in the background."""
    existing = find_by_website(repo, body.url)
    target = target_from_link(
        body.url,
        body.name,
        existing,
    )
    startup = existing if existing is not None else queued_startup(target)
    if existing is None:
        repo.save(startup)

    return LinkCreated(
        startup=startup,
        research=enqueue(
            repo,
            [target],
            [],
        ),
    )


@app.post("/api/compare")
def compare_startups(body: CompareRequest, repo: Repo) -> CompareResult:
    """Explain which stored startups fit a selected investor thesis."""
    startups = []
    for startup_id in body.ids:
        startup = repo.get(startup_id)
        if startup is None:
            raise HTTPException(status_code=404, detail=f"Startup not found: {startup_id}")

        startups.append(startup)

    judgement = explain_match(
        body.thesis,
        startups,
    )
    preferred = next(item for item in startups if item.id == judgement.preferred_id)
    return CompareResult(
        preferred_id=preferred.id,
        preferred_name=preferred.name,
        explanation=judgement.explanation,
    )


@app.post("/api/startups", status_code=201)
def create_startup(body: CreateStartup, repo: Repo) -> Startup:
    """Add a startup and attach a placeholder assessment."""
    return repo.create(
        name=body.name,
        stage=body.stage,
        profile=body.profile,
    )
