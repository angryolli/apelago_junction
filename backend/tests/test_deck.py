import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.research.deck import deck_text, example_deck_bytes, summarize_pitch
from app.research.targets import startup_from_target
from app.schemas import PitchSummary


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "radar.db"))

    with TestClient(app) as test_client:
        yield test_client


def test_example_deck_keeps_the_sample_slides() -> None:
    data = example_deck_bytes()
    text = deck_text(data)

    assert "Harborline Sensors" in text
    assert "This company is fictional" in text
    assert "400,000 euro" in text
    assert "Slide 1:" in text
    assert "Slide 6:" in text
    with zipfile.ZipFile(BytesIO(data)) as archive:
        slide = archive.read("ppt/slides/slide1.xml")

    assert b"<a:off " in slide
    assert b'cx="' in slide


def test_summary_without_a_key_keeps_the_slide_text(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    summary = summarize_pitch("Harborline Sensors", "sample.pptx", "Slide 1: Buoy Window")

    assert summary.filename == "sample.pptx"
    assert "Buoy Window" in summary.overview
    assert summary.gaps == ["Set OPENAI_API_KEY to write the deck summary."]


def test_add_with_deck_summarises_after_research(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_research(target):
        startup = startup_from_target(target)
        startup.name = "Harborline Sensors"
        from app.research.deck import attach_pitch

        return attach_pitch(startup)

    def fake_summary(company: str, filename: str, text: str) -> PitchSummary:
        assert company == "Harborline Sensors"
        assert "Buoy Window" in text

        return PitchSummary(
            filename=filename,
            overview="Sample deck about a harbour sensor.",
            problem="Missed berth windows.",
        )

    monkeypatch.setattr("app.research.jobs.research_company", fake_research)
    monkeypatch.setattr("app.research.deck.summarize_pitch", fake_summary)
    created = client.post(
        "/api/startups/with-deck",
        data={"url": "https://harborline.example", "name": "Harborline Sensors"},
        files={"deck": ("Harborline-sample-deck.pptx", example_deck_bytes(), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )

    assert created.status_code == 201
    status = created.json()["research"]
    for _ in range(50):
        if status["status"] != "running":
            break
        status = client.get("/api/research").json()

    stored = client.get(f"/api/startups/{created.json()['startup']['id']}").json()
    assert stored["pitch"]["overview"] == "Sample deck about a harbour sensor."
    assert stored["pitch"]["problem"] == "Missed berth windows."
    downloaded = client.get(f"/api/startups/{stored['id']}/deck")
    assert downloaded.status_code == 200
    assert "Harborline Sensors" in deck_text(downloaded.content)


def test_example_deck_downloads(client: TestClient) -> None:
    response = client.get("/api/example-deck")

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('filename="Harborline-sample-deck.pptx"')
    assert "Harborline Sensors" in deck_text(response.content)


def test_with_deck_rejects_a_text_file(client: TestClient) -> None:
    response = client.post(
        "/api/startups/with-deck",
        data={"url": "https://harborline.example", "name": "Harborline Sensors"},
        files={"deck": ("notes.txt", b"not a deck", "text/plain")},
    )

    assert response.status_code == 422
