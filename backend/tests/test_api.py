import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "radar.db"))

    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startups_are_ranked_by_thesis_fit(client: TestClient) -> None:
    response = client.get("/api/startups")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [
        "awake-ai",
        "norsepower",
        "npharvest",
        "origin-by-ocean",
        "weeefiner",
        "wesi",
    ]
    npharvest = next(item for item in body if item["id"] == "npharvest")
    assert npharvest["assessed"] is False
    assert npharvest["thesisFit"] == 0
    assert len(npharvest["dimensions"]) == 10
    assert npharvest["profile"]["website"] == "www.npharvest.fi"
    assert "thesis_fit" not in npharvest


def test_filter_by_sector_and_search(client: TestClient) -> None:
    sector = client.get("/api/startups", params={"sector": "Shipping"})
    search = client.get("/api/startups", params={"q": "Norse"})
    missing = client.get("/api/startups", params={"sector": "Nope"})

    assert [item["id"] for item in sector.json()] == ["awake-ai", "norsepower"]
    assert [item["id"] for item in search.json()] == ["norsepower"]
    assert missing.json() == []


def test_sectors(client: TestClient) -> None:
    response = client.get("/api/sectors")

    assert response.status_code == 200
    assert response.json() == [
        "Aquaculture",
        "Biomaterials",
        "Shipping",
        "Water",
    ]


def test_get_startup_and_missing(client: TestClient) -> None:
    found = client.get("/api/startups/npharvest")
    missing = client.get("/api/startups/missing")

    assert found.status_code == 200
    assert found.json()["name"] == "NPHarvest"
    assert missing.status_code == 404


def test_create_startup_uses_placeholder_assessment(client: TestClient) -> None:
    response = client.post(
        "/api/startups",
        json={
            "name": "  Foam Tide  ",
            "stage": "Pre-seed",
            "profile": {
                "description": "Foam capture for harbours",
                "keywords": ["Robotics"],
                "hq": "Turku, Finland",
                "traction": "Lab prototype",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Foam Tide"
    assert body["sector"] == "Robotics"
    assert body["country"] == "Finland"
    assert body["thesisFit"] == 0
    assert body["assessed"] is False
    assert body["tagline"] == "Foam capture for harbours"
    assert body["readiness"] == {"impact": 1, "business": 1, "tech": 1, "investment": 1}
    assert len(body["dimensions"]) == 10
    assert body["signals"] == ["Lab prototype"]
    assert len(body["nextSteps"]) == 3

    listed = client.get("/api/startups", params={"q": "Foam Tide"})
    assert listed.json()[0]["id"] == body["id"]
    assert "Robotics" in client.get("/api/sectors").json()


def test_research_collects_sources_without_a_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_research(target):
        from app.research.pipeline import _stub

        startup = _stub(target)
        startup.judge_notes = "Set OPENAI_API_KEY to score this evidence."
        startup.sources = []

        return startup

    monkeypatch.setattr("app.research.jobs.research_company", fake_research)
    started = client.post("/api/research", json={"names": ["NPHarvest"]})

    assert started.status_code == 200
    assert started.json()["status"] in {"running", "done"}

    status = started.json()
    for _ in range(50):
        if status["status"] != "running":
            break
        time.sleep(0.05)
        status = client.get("/api/research").json()

    assert status["status"] == "done"
    assert status["completed"] == ["NPHarvest"]
    stored = client.get("/api/startups/npharvest").json()
    assert stored["assessed"] is False
    assert "OPENAI_API_KEY" in stored["judgeNotes"]


def test_add_from_link_researches_in_the_background(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_research(target):
        from app.research.targets import startup_from_target

        startup = startup_from_target(target)
        startup.name = "Foam Tide"
        startup.tagline = "Harbour foam capture"
        startup.profile.description = "Harbour foam capture"
        startup.judge_notes = "Set OPENAI_API_KEY to score this evidence."

        return startup

    monkeypatch.setattr("app.research.jobs.research_company", fake_research)
    created = client.post("/api/startups/from-link", json={"url": "foamtide.example"})

    assert created.status_code == 201
    body = created.json()
    assert body["startup"]["profile"]["website"] == "foamtide.example"
    assert body["startup"]["assessed"] is False
    assert body["research"]["status"] in {"running", "done"}

    status = body["research"]
    for _ in range(50):
        if status["status"] != "running":
            break
        time.sleep(0.05)
        status = client.get("/api/research").json()

    assert status["status"] == "done"
    assert status["completed"] == ["Foam Tide"]
    listed = client.get("/api/startups", params={"q": "Foam Tide"}).json()
    assert listed[0]["profile"]["description"] == "Harbour foam capture"

    again = client.post(
        "/api/startups/from-link",
        json={"url": "https://www.foamtide.example/"},
    )
    assert again.status_code == 201
    assert again.json()["startup"]["id"] == body["startup"]["id"]
    assert len(client.get("/api/startups", params={"q": "Foam"}).json()) == 1


def test_add_from_link_rejects_a_non_web_link(client: TestClient) -> None:
    response = client.post("/api/startups/from-link", json={"url": "javascript:alert(1)"})

    assert response.status_code == 422


def test_create_rejects_blank_name(client: TestClient) -> None:
    response = client.post("/api/startups", json={"name": "   ", "profile": {}})

    assert response.status_code == 422


def test_compare_two_startups_without_a_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/compare",
        json={
            "ids": ["npharvest", "norsepower"],
            "thesis": "Early-stage Baltic and European blue economy",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preferredId"] == "npharvest"
    assert body["preferredName"] == "NPHarvest"
    assert "OPENAI_API_KEY" in body["explanation"]


def test_compare_rejects_one_startup(client: TestClient) -> None:
    response = client.post(
        "/api/compare",
        json={"ids": ["npharvest"], "thesis": "Ocean impact"},
    )

    assert response.status_code == 422


def test_compare_unknown_startup(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/compare",
        json={"ids": ["npharvest", "missing-co"], "thesis": "Ocean impact"},
    )

    assert response.status_code == 404
