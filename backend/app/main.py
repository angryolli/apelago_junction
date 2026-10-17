import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.repository import Repository
from app.research.compare import explain_match
from app.research.deck import (
    MAX_DECK_BYTES,
    deck_text,
    example_deck_bytes,
    load_deck,
    safe_filename,
    store_deck,
)
from app.research.explore import ExploreError, find_one
from app.research.inquire import investor_inquiry
from app.research.jobs import enqueue, get_status, start_research
from app.research.links import find_by_website, queued_startup, target_from_link
from app.schemas import (
    CompareRequest,
    CompareResult,
    ExploreResult,
    Inquiry,
    CreateFromLink,
    CreateStartup,
    LinkCreated,
    PitchSummary,
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


def _queue_website(
    repo: Repository,
    url: str,
    name: str,
    deck: tuple[str, bytes] | None = None,
) -> LinkCreated:
    """Store a new company when needed and research the website."""
    existing = find_by_website(repo, url)
    target = target_from_link(
        url,
        name,
        existing,
    )
    startup = existing if existing is not None else queued_startup(target)
    if deck is not None:
        filename, data = deck
        store_deck(target.id, filename, data)
        startup.pitch = PitchSummary(
            filename=filename,
            gaps=["The deck summary is written when research finishes."],
        )
        repo.save(startup)
    elif existing is None:
        repo.save(startup)

    return LinkCreated(
        startup=startup,
        research=enqueue(
            repo,
            [target],
            [],
        ),
    )


def _read_deck(deck: UploadFile | None) -> tuple[str, bytes] | None:
    """Accept one pptx, or nothing when the upload was left empty."""
    if deck is None or not deck.filename:
        return None

    filename = safe_filename(deck.filename)
    data = deck.file.read(MAX_DECK_BYTES + 1)
    if not data:
        return None
    if len(data) > MAX_DECK_BYTES:
        raise HTTPException(status_code=413, detail="The pitch deck must be 8 MB or smaller.")
    if not deck.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=422, detail="Upload a .pptx pitch deck.")

    try:
        deck_text(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return filename, data


def _deck_response(data: bytes, filename: str) -> Response:
    """Send a pptx as a download."""
    safe = safe_filename(filename)

    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


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


@app.get("/api/example-deck")
def download_example_deck() -> Response:
    """Download the fictional sample pitch deck."""
    return _deck_response(example_deck_bytes(), "Harborline-sample-deck.pptx")


@app.get("/api/startups/{startup_id}/deck")
def download_startup_deck(startup_id: str, repo: Repo) -> Response:
    """Download the pitch deck uploaded for one startup."""
    if repo.get(startup_id) is None:
        raise HTTPException(status_code=404, detail="Startup not found")

    stored = load_deck(startup_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="No pitch deck is stored for this startup")

    filename, data = stored

    return _deck_response(data, filename)


@app.post("/api/startups/from-link", status_code=201)
def create_from_link(body: CreateFromLink, repo: Repo) -> LinkCreated:
    """Add a company from its website and research it in the background."""
    return _queue_website(repo, body.url, body.name)


@app.post("/api/startups/with-deck", status_code=201)
def create_with_deck(
    repo: Repo,
    url: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    deck: Annotated[UploadFile | None, File()] = None,
) -> LinkCreated:
    """Add a company from its website and, when attached, summarise a pitch deck."""
    try:
        parsed = CreateFromLink(url=url, name=name)
    except ValidationError as exc:
        message = exc.errors()[0]["msg"] if exc.errors() else "Enter a website link."
        raise HTTPException(status_code=422, detail=message) from exc

    return _queue_website(
        repo,
        parsed.url,
        parsed.name,
        _read_deck(deck),
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


@app.post("/api/startups/{startup_id}/inquiry")
def startup_inquiry(startup_id: str, repo: Repo) -> Inquiry:
    """Write investor questions from one stored assessment."""
    startup = repo.get(startup_id)
    if startup is None:
        raise HTTPException(status_code=404, detail="Startup not found")

    return investor_inquiry(startup)


@app.post("/api/explore")
def explore_startup(repo: Repo) -> ExploreResult:
    """Name one EU startup that is not already in the table."""
    try:
        return find_one(repo.list_startups())
    except ExploreError as exc:
        status = 503 if "OPENAI_API_KEY" in exc.message else 422
        raise HTTPException(status_code=status, detail=exc.message) from exc


@app.post("/api/startups", status_code=201)
def create_startup(body: CreateStartup, repo: Repo) -> Startup:
    """Add a startup and attach a placeholder assessment."""
    return repo.create(
        name=body.name,
        stage=body.stage,
        profile=body.profile,
    )
