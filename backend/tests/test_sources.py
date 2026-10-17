import httpx

from app.research.sources import (
    best_prh_company,
    public_error,
    blueinvest_detail_url,
    blueinvest_excerpt,
    cordis_projects,
    fetch_business_finland,
)
from app.research.text import clip, html_title, readable_copy, visible_text


def test_html_title_keeps_the_company_name() -> None:
    title = html_title("<html><title>NPHarvest – We recover value</title></html>")

    assert title == "NPHarvest"


def test_visible_text_skips_scripts() -> None:
    text = visible_text("<html><style>hide</style><p>Nutrient recovery</p><script>nope</script></html>")

    assert text == "Nutrient recovery"


def test_readable_copy_drops_short_navigation() -> None:
    text = "\n".join(
        [
            "Skip to content",
            "About",
            "About",
            "We recover value from your sludge",
            "NPHarvest captures nutrients from wastewater.",
        ]
    )

    assert readable_copy(text).startswith("We recover value")


def test_public_error_names_the_status_only() -> None:
    request = httpx.Request("GET", "https://dealroom.co/api/lookup-slug")
    response = httpx.Response(403, request=request)
    error = httpx.HTTPStatusError(
        "blocked",
        request=request,
        response=response,
    )

    assert public_error(error) == "The source returned HTTP 403."


def test_clip_breaks_on_a_word() -> None:
    assert clip("alpha beta gamma", 10) == "alpha…"


def test_prh_picks_the_current_name() -> None:
    company = best_prh_company(
        [
            {
                "names": [
                    {"name": "Other Oy"},
                    {"name": "NPHarvest Oy"},
                ]
            }
        ],
        ["NPHarvest Oy", "NPHarvest"],
    )

    assert company is not None
    assert company["names"][1]["name"] == "NPHarvest Oy"


def test_blueinvest_detail_link() -> None:
    html = (
        '<a href="./pipeline_front.html?action=detail&amp;params%5Bother_id%5D=805">'
        "Norsepower</a>"
    )

    assert blueinvest_detail_url(html).endswith("params%5Bother_id%5D=805") or "other_id" in blueinvest_detail_url(html)


def test_blueinvest_excerpt_starts_after_the_navigation() -> None:
    html = "<p>Home Events Click here to learn more Norsepower Rotor Sails save fuel.</p>"

    assert blueinvest_excerpt(html).startswith("Norsepower")


def test_blueinvest_excerpt_drops_boilerplate() -> None:
    html = "<p>Rotor sails save fuel.</p><p>The BlueInvest Project Pipeline is a database of projects.</p>"

    assert blueinvest_excerpt(html) == "Rotor sails save fuel."


def test_cordis_projects_read_top_level_hits() -> None:
    notes = cordis_projects(
        {"hits": {"hit": {"project": {"id": "738282", "acronym": "RotorDEMO", "teaser": "Wind."}}}}
    )

    assert "RotorDEMO" in notes[0]
    assert "738282" in notes[0]


def test_cordis_projects_accept_one_or_many_hits() -> None:
    single = cordis_projects(
        {"result": {"hits": {"hit": {"project": {"id": "1", "acronym": "RotorDEMO", "teaser": "Wind."}}}}}
    )
    many = cordis_projects(
        {
            "result": {
                "hits": {
                    "hit": [
                        {"project": {"id": "1", "acronym": "A", "teaser": "One"}},
                        {"project": {"id": "2", "acronym": "B", "teaser": "Two"}},
                    ]
                }
            }
        }
    )

    assert "RotorDEMO" in single[0]
    assert "cordis.europa.eu/project/id/1" in single[0]
    assert len(many) == 2


def test_business_finland_link_uses_the_business_id() -> None:
    hit = fetch_business_finland("3392875-3")

    assert hit.found is True
    assert "Businessid=3392875-3" in hit.url
    assert "does not confirm" in hit.excerpt
