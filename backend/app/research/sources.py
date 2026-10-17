"""Fetch public evidence for one company from the six MVP sources."""

from typing import Literal

import httpx

from app.research.targets import Target
from app.research.text import clip, html_title, readable_copy, visible_text
from app.schemas import SourceHit

USER_AGENT = "OceanOpportunityRadar/0.1 (public-source research)"
BLUEINVEST_SEARCH = "https://blueinvest-community.converve.io/pipeline_front.html"
BUSINESS_FINLAND_REPORT = (
    "https://tietopankki.businessfinland.fi/anonymous/extensions/"
    "projectfunding/projectfunding.html"
)
CORDIS_SEARCH = "https://cordis.europa.eu/search/en"
DEALROOM_LOOKUP = "https://dealroom.co/api/lookup-slug"
PRH_SEARCH = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies"


def get_text(url: str, *, params: dict[str, str] | None = None) -> str:
    """Fetch one public URL and return the response body."""
    with httpx.Client(
        timeout=25.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = client.get(url, params=params)
        response.raise_for_status()

    return response.text[:1_000_000]


def get_json(url: str, *, params: dict[str, str] | None = None) -> dict:
    """Fetch one public JSON URL."""
    with httpx.Client(
        timeout=25.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = client.get(url, params=params)
        response.raise_for_status()

    payload = response.json()

    return payload if isinstance(payload, dict) else {"data": payload}


def collect_sources(target: Target, website: SourceHit | None = None) -> list[SourceHit]:
    """Collect evidence from each source, keeping a miss when a source has nothing."""
    register, business_id = fetch_prh(target)

    return [
        website if website is not None else fetch_website(target),
        fetch_dealroom(target),
        fetch_blueinvest(target),
        fetch_business_finland(business_id),
        register,
        fetch_cordis(target),
    ]


def fetch_website(target: Target) -> SourceHit:
    """Read the company site and one about page when it is linked."""
    try:
        home = get_text(target.website)
    except Exception as exc:
        return _miss(
            "website",
            "Company website",
            target.website,
            public_error(exc),
        )

    text = visible_text(home)
    about = _same_site_link(home, target.website, ("about", "our-story", "company"))
    if about:
        try:
            text = f"{text}\n{visible_text(get_text(about))}"
        except Exception:
            about = ""

    return SourceHit(
        source="website",
        title=html_title(home) or f"{target.name} website",
        url=about or target.website,
        excerpt=clip(readable_copy(text), 3500),
        found=bool(text.strip()),
    )


def fetch_dealroom(target: Target) -> SourceHit:
    """Look the company up in Dealroom's public company index."""
    try:
        payload = get_json(
            DEALROOM_LOOKUP,
            params={"name": target.name, "type": "company", "limit": "3"},
        )
    except Exception as exc:
        return _miss(
            "dealroom",
            "Dealroom",
            DEALROOM_LOOKUP,
            public_error(exc),
        )

    matches = payload.get("matches") or []
    if not matches:
        hint = str(payload.get("hint") or "No match in the public Dealroom index.")

        return _miss(
            "dealroom",
            "Dealroom",
            DEALROOM_LOOKUP,
            hint,
        )

    match = matches[0]
    profile_url = str(match.get("profileUrl") or match.get("markdownUrl") or DEALROOM_LOOKUP)
    excerpt = _dealroom_excerpt(match)

    return SourceHit(
        source="dealroom",
        title=str(match.get("name") or target.name),
        url=profile_url,
        excerpt=excerpt,
        found=True,
    )


def fetch_blueinvest(target: Target) -> SourceHit:
    """Search the BlueInvest project pipeline and read the first matching profile."""
    search_url = BLUEINVEST_SEARCH
    try:
        html = get_text(
            search_url,
            params={
                "params[q]": target.name,
                "params[show]": "comp",
                "params[page]": "1",
                "params[_filtered]": "1",
                "params[event_id]": "1",
            },
        )
    except Exception as exc:
        return _miss(
            "blueinvest",
            "BlueInvest",
            search_url,
            public_error(exc),
        )

    detail_url = blueinvest_detail_url(html)
    if not detail_url:
        return _miss(
            "blueinvest",
            "BlueInvest",
            search_url,
            "No BlueInvest pipeline profile.",
        )

    try:
        detail = get_text(detail_url)
    except Exception as exc:
        return _miss(
            "blueinvest",
            "BlueInvest",
            detail_url,
            public_error(exc),
        )

    excerpt = blueinvest_excerpt(detail)
    if not excerpt:
        return _miss(
            "blueinvest",
            "BlueInvest",
            detail_url,
            "The profile page had no project text.",
        )

    return SourceHit(
        source="blueinvest",
        title=f"{target.name} on BlueInvest",
        url=detail_url,
        excerpt=excerpt,
        found=True,
    )


def fetch_business_finland(business_id: str) -> SourceHit:
    """Point at the public Business Finland funding report for a business ID."""
    if not business_id:
        return _miss(
            "business_finland",
            "Business Finland",
            BUSINESS_FINLAND_REPORT,
            "No Finnish business ID was found, so the funding report could not be filtered.",
        )

    url = f"{BUSINESS_FINLAND_REPORT}?Businessid={business_id}"
    excerpt = (
        "Business Finland publishes every funding decision in its open project-funding report. "
        f"This link filters that report by business ID {business_id}. "
        "Euro amounts are shown in the interactive report rather than in a public JSON API. "
        "The link alone does not confirm that this company received funding."
    )

    return SourceHit(
        source="business_finland",
        title=f"Business Finland funding report {business_id}",
        url=url,
        excerpt=excerpt,
        found=True,
    )


def fetch_prh(target: Target) -> tuple[SourceHit, str]:
    """Search the Finnish trade register and return the best company plus its business ID."""
    for query in target.queries:
        try:
            payload = get_json(PRH_SEARCH, params={"name": query})
        except Exception as exc:
            return (
                _miss(
                    "prh",
                    "PRH trade register",
                    PRH_SEARCH,
                    public_error(exc),
                ),
                "",
            )

        company = best_prh_company(payload.get("companies") or [], target.queries)
        if company is None:
            continue

        business_id = str((company.get("businessId") or {}).get("value") or "")
        excerpt = format_prh(company)

        return (
            SourceHit(
                source="prh",
                title=current_prh_name(company) or target.name,
                url=f"https://www.ytj.fi/en/index/companysearch.html?businessId={business_id}",
                excerpt=excerpt,
                found=True,
            ),
            business_id,
        )

    return (
        _miss(
            "prh",
            "PRH trade register",
            PRH_SEARCH,
            "No matching trade-register company.",
        ),
        "",
    )


def fetch_cordis(target: Target) -> SourceHit:
    """Search CORDIS projects that name the company."""
    terms = [target.name, *[query.removesuffix(" Oy") for query in target.queries]]
    seen = []
    last_error = "No CORDIS project mentions this company."
    for term in terms:
        if term.lower() in seen:
            continue
        seen.append(term.lower())
        try:
            payload = get_json(
                CORDIS_SEARCH,
                params={
                    "q": f"contenttype='project' AND '{term.replace(chr(39), '')}'",
                    "format": "json",
                    "num": "3",
                },
            )
        except Exception as exc:
            return _miss(
                "cordis",
                "CORDIS",
                CORDIS_SEARCH,
                public_error(exc),
            )

        projects = cordis_projects(payload)
        if projects:
            return SourceHit(
                source="cordis",
                title="CORDIS projects",
                url=f"https://cordis.europa.eu/search?q={term.replace(' ', '%20')}",
                excerpt=clip("\n".join(projects), 2500),
                found=True,
            )

    return _miss(
        "cordis",
        "CORDIS",
        CORDIS_SEARCH,
        last_error,
    )


def best_prh_company(companies: list[dict], queries: list[str]) -> dict | None:
    """Pick the trade-register row whose name best matches the queries."""
    best: dict | None = None
    best_score = 1
    for company in companies:
        score = max(name_score(current_prh_name(company), queries), 0)
        for record in company.get("names") or []:
            score = max(score, name_score(str(record.get("name") or ""), queries))
        if score > best_score:
            best = company
            best_score = score

    return best


def name_score(company_name: str, queries: list[str]) -> int:
    """Score how closely a registered name matches the search queries."""
    folded = company_name.lower()
    score = 0
    for query in queries:
        needle = query.lower()
        if folded == needle:
            score = max(score, 3)
        elif needle in folded:
            score = max(score, 2)

    return score


def current_prh_name(company: dict) -> str:
    """Return the registered name that has no end date."""
    for record in company.get("names") or []:
        if not record.get("endDate"):
            return str(record.get("name") or "")

    return ""


def format_prh(company: dict) -> str:
    """Turn a trade-register record into a short evidence note."""
    business_id = (company.get("businessId") or {}).get("value") or "—"
    registered = (company.get("businessId") or {}).get("registrationDate") or "—"
    form = _english((company.get("companyForms") or [{}])[0].get("descriptions") or [])
    line = _english((company.get("mainBusinessLine") or {}).get("descriptions") or [])
    address = _address(company)
    website = (company.get("website") or {}).get("url") or ""
    status = company.get("tradeRegisterStatus") or company.get("status") or ""

    return clip(
        " ".join(
            [
                f"Name: {current_prh_name(company)}.",
                f"Business ID: {business_id}.",
                f"Registered: {registered}.",
                f"Form: {form}.",
                f"Business line: {line}.",
                f"Address: {address}.",
                f"Website: {website}.",
                f"Status: {status}.",
            ]
        ),
        1500,
    )


def blueinvest_detail_url(html: str) -> str:
    """Find the first pipeline profile link in a BlueInvest search page."""
    marker = "action=detail"
    start = html.find(marker)
    if start < 0:
        return ""

    href_start = html.rfind("href=", 0, start)
    if href_start < 0:
        return ""

    quote = html[href_start + 5]
    end = html.find(quote, href_start + 6)
    if end < 0:
        return ""

    href = html[href_start + 6 : end]
    href = href.replace("&amp;", "&")
    if href.startswith("./"):
        href = href[2:]

    href = href.replace("/./", "/")
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return "https://blueinvest-community.converve.io" + href

    return "https://blueinvest-community.converve.io/" + href


def blueinvest_excerpt(html: str) -> str:
    """Keep the project text and drop the repeated pipeline boilerplate."""
    text = visible_text(html)
    lead = "Click here to learn more"
    if lead in text:
        text = text.split(lead, 1)[1]

    marker = "The BlueInvest Project Pipeline is a database"
    if marker in text:
        text = text.split(marker)[0]

    return clip(text, 2000)


def cordis_projects(payload: dict) -> list[str]:
    """Flatten a CORDIS search response into short project notes."""
    result = payload.get("result") or {}
    hits = payload.get("hits")
    if hits is None:
        hits = result.get("hits")

    if isinstance(hits, dict):
        hit = hits.get("hit")
    else:
        hit = hits

    if hit is None:
        return []
    if isinstance(hit, dict):
        hit = [hit]

    notes = []
    for item in hit:
        project = item.get("project") or {}
        project_id = project.get("id") or ""
        acronym = project.get("acronym") or ""
        teaser = project.get("teaser") or project.get("objective") or ""
        link = f"https://cordis.europa.eu/project/id/{project_id}" if project_id else ""
        notes.append(clip(f"{acronym} ({link}). {teaser}", 700))

    return notes


def _english(descriptions: list[dict]) -> str:
    for description in descriptions:
        if str(description.get("languageCode")) == "3":
            return str(description.get("description") or "")

    if not descriptions:
        return "—"

    return str(descriptions[0].get("description") or "—")


def _address(company: dict) -> str:
    addresses = company.get("addresses") or []
    if not addresses:
        return "—"

    address = addresses[0]
    street = " ".join(
        part
        for part in [address.get("street"), address.get("buildingNumber")]
        if part
    )
    city = ""
    offices = address.get("postOffices") or []
    if offices:
        city = str(offices[0].get("city") or "")

    return ", ".join(part for part in [street, address.get("postCode"), city] if part) or "—"


def _dealroom_excerpt(match: dict) -> str:
    fields = [
        f"Name: {match.get('name') or ''}.",
        f"Slug: {match.get('slug') or ''}.",
        f"Type: {match.get('type') or ''}.",
        f"Profile: {match.get('profileUrl') or ''}.",
        f"News: {match.get('newsUrl') or ''}.",
    ]

    return clip(" ".join(fields), 1000)


def _same_site_link(html: str, website: str, needles: tuple[str, ...]) -> str:
    host = website.split("/")[2] if "://" in website else ""
    lowered = html.lower()
    for needle in needles:
        index = lowered.find(needle)
        if index < 0:
            continue
        href_start = lowered.rfind("href=", 0, index)
        if href_start < 0:
            continue
        quote = html[href_start + 5]
        end = html.find(quote, href_start + 6)
        href = html[href_start + 6 : end]
        if href.startswith("/"):
            return f"https://{host}{href}"
        if host and host in href:
            return href

    return ""


def public_error(exc: Exception) -> str:
    """Turn a failed public request into a short note."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"The source returned HTTP {exc.response.status_code}."

    return "The source could not be reached."


def _miss(
    source: Literal["website", "dealroom", "blueinvest", "business_finland", "prh", "cordis"],
    title: str,
    url: str,
    excerpt: str,
) -> SourceHit:
    """Build a source record that explains a miss or a failed request."""
    return SourceHit(
        source=source,
        title=title,
        url=url,
        excerpt=clip(excerpt, 500),
        found=False,
    )
