import pytest

from app.research.explore import Candidate, already_listed, find_one, page_mentions


def test_already_listed_rejects_a_stored_name() -> None:
    existing = ["NPHarvest", "Norsepower", "Origin by Ocean"]

    assert already_listed("NPHarvest Oy", existing)
    assert already_listed("norsepower", existing)
    assert not already_listed("Foam Tide", existing)


def test_page_mentions_reads_the_company_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.research.explore.get_text",
        lambda url: "<html><title>Foam Tide</title><body>Foam Tide recovers harbour foam.</body></html>",
    )

    assert page_mentions("Foam Tide", "https://foamtide.example")
    assert not page_mentions("Kelp Other", "https://foamtide.example")


def test_find_one_skips_a_listed_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    answers = [
        Candidate(
            name="NPHarvest",
            country="Finland",
            website="https://www.npharvest.fi/",
            why="This company is already in the review table and should be skipped entirely.",
        ),
        Candidate(
            name="Foam Tide",
            country="Finland",
            website="https://foamtide.example",
            why="Foam Tide recovers nutrients from coastal water in Finland. That fits an early-stage European blue-economy search.",
        ),
    ]
    monkeypatch.setattr("app.research.explore._ask", lambda excluded: answers.pop(0))
    monkeypatch.setattr("app.research.explore.page_mentions", lambda name, website: name == "Foam Tide")

    result = find_one([])

    assert result.name == "Foam Tide"
    assert result.country == "Finland"
    assert "coastal water" in result.why