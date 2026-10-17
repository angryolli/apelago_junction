"""Turn a company website into a research target."""

import re
import time
from urllib.parse import urlparse

from app.repository import Repository
from app.research.targets import Target, startup_from_target
from app.schemas import Startup

QUEUED_TAGLINE = "Research queued from the company website."


def normalize_url(value: str) -> str:
    """Accept an http(s) link, adding https when the scheme was left off."""
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    if "://" not in text:
        text = "https://" + text

    parsed = urlparse(text)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not host or " " in text:
        raise ValueError("must be an http or https link")
    if "." not in host and host != "localhost":
        raise ValueError("must be an http or https link")

    return text


def website_key(url: str) -> str:
    """Compare sites by host and path, ignoring scheme and a leading www."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/")

    return f"{host}{path}"


def find_by_website(repository: Repository, url: str) -> Startup | None:
    """Return a stored startup that already uses this website."""
    key = website_key(url)
    for startup in repository.list_startups():
        site = startup.profile.website
        if site and website_key(site) == key:
            return startup

    return None


def target_from_link(
    url: str,
    name: str,
    existing: Startup | None,
) -> Target:
    """Build the research target for a link, reusing a stored company when the site matches."""
    chosen = name or (existing.name if existing else name_from_host(url))
    startup_id = existing.id if existing else new_id(chosen)
    sector = "Unclassified"
    if existing and existing.sector != "Unclassified":
        sector = existing.sector

    return Target(
        startup_id=startup_id,
        name=chosen,
        website=url,
        sector=sector,
        tagline=QUEUED_TAGLINE,
        queries=search_queries(chosen, url),
        rename_from_site=not name and existing is None,
    )


def target_from_startup(startup: Startup) -> Target:
    """Research a company that is already stored."""
    website = startup.profile.website
    if website and "://" not in website:
        website = "https://" + website

    return Target(
        startup_id=startup.id,
        name=startup.name,
        website=website,
        sector=startup.sector or "Unclassified",
        tagline=startup.tagline,
        queries=search_queries(startup.name, website or ""),
    )


def queued_startup(target: Target) -> Startup:
    """Return the table row shown while link research is still running."""
    return startup_from_target(target)


def name_from_host(url: str) -> str:
    """Use the site label until the page title is known."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    label = re.sub(r"[-_]+", " ", host.split(".")[0]).strip()

    return label.title() if label else "New startup"


def new_id(name: str) -> str:
    """Build a stable-enough id that will not collide with an existing row."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "startup"

    return f"{slug}-{format(time.time_ns(), 'x')[-6:]}"


def search_queries(name: str, url: str) -> list[str]:
    """Search the trade register with the name and a Finnish suffix on .fi sites."""
    queries = [name]
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".fi") and " oy" not in name.lower():
        queries.insert(0, f"{name} Oy")

    return queries
