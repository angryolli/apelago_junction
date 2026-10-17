"""Read a published address from a company website."""

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

from app.research.links import normalize_url
from app.research.sources import get_text
from app.research.text import visible_text

_MAILTO = re.compile(
    r"mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+\-])([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
_ROLE = re.compile(r"\s+(CEO|Founder|Co-founder|Chair|Advisor)\s*$", re.IGNORECASE)
_NAME = re.compile(
    r"([A-ZÀ-Ý][a-zà-ÿ'’-]{1,}(?:\s+[A-ZÀ-Ý][a-zà-ÿ'’-]{1,}){1,2})\s*$",
)
_FILE_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "woff", "woff2"}
_SKIP_HOSTS = (
    "sentry",
    "wixpress",
    "procountor",
    "netvisor",
    "administer",
    "example.com",
    "schema.org",
    "cloudflare",
)
_GENERIC = ("contact", "hello", "info", "office", "press", "media")
_PAGE_WORDS = ("contact", "about", "team", "people")
_LEADER_ROLES = {"ceo", "founder", "co-founder", "chair"}


@dataclass
class PublishedAddress:
    email: str = ""
    name: str = ""
    role: str = ""


def find_published_contact(website: str, person: str) -> tuple[str, str]:
    """Return a published email and the person named beside it."""
    if not website.strip():
        return "", ""

    try:
        home_url = normalize_url(website)
        pages = [get_text(home_url)]
    except Exception:
        return "", ""

    addresses = addresses_in(pages[0])
    for url in _linked_pages(pages[0], home_url):
        try:
            addresses.extend(addresses_in(get_text(url)))
        except Exception:
            continue

    chosen = choose_contact(addresses, home_url, person)
    if not chosen.email:
        return "", ""

    label = ""
    if chosen.name and not person.strip():
        label = f"{chosen.name}, {chosen.role}" if chosen.role else chosen.name

    return chosen.email, label


def addresses_in(html: str) -> list[PublishedAddress]:
    """Return addresses from mailto links and visible page text."""
    text = visible_text(html)
    found: list[PublishedAddress] = []
    seen: set[str] = set()
    for raw in _MAILTO.findall(html) + _EMAIL.findall(html):
        email = _clean(raw)
        if not email or email in seen or not _usable(email):
            continue

        seen.add(email)
        name, role = _beside(text, email)
        found.append(PublishedAddress(email=email, name=name, role=role))

    return found


def choose_contact(
    addresses: list[PublishedAddress],
    website: str,
    person: str,
) -> PublishedAddress:
    """Pick one same-site address, preferring the named person."""
    host = _mail_host(website)
    same: list[PublishedAddress] = []
    seen: set[str] = set()
    for item in addresses:
        if not _on_site(item.email, host) or item.email in seen:
            continue
        seen.add(item.email)
        same.append(item)

    tokens = _person_tokens(person)
    personal = [item for item in same if _hits(item.email, tokens)]
    if personal:
        return max(personal, key=lambda item: _hits(item.email, tokens))

    generic = [item for item in same if _is_generic(item.email)]
    if generic:
        return min(generic, key=lambda item: _GENERIC.index(_local_root(item.email)))

    leaders = [item for item in same if item.role.lower() in _LEADER_ROLES]
    if leaders:
        return leaders[0]

    if len(same) == 1:
        return same[0]

    return PublishedAddress()


def _beside(text: str, email: str) -> tuple[str, str]:
    index = text.lower().find(email.lower())
    if index < 0:
        return "", ""

    window = " ".join(text[max(0, index - 80) : index].split())
    role_match = _ROLE.search(window)
    role = role_match.group(1) if role_match else ""
    if role_match:
        window = window[: role_match.start()]

    name_match = _NAME.search(window)
    if name_match is None:
        return "", role

    return name_match.group(1).strip(), role


def _linked_pages(html: str, website: str) -> list[str]:
    host = urlparse(website).hostname or ""
    scheme = urlparse(website).scheme or "https"
    pages: list[str] = []
    for href in _HREF.findall(html):
        lowered = href.lower()
        if not any(word in lowered for word in _PAGE_WORDS):
            continue
        if href.startswith("/"):
            url = f"{scheme}://{host}{href}"
        elif host and host.removeprefix("www.") in href:
            url = href
        else:
            continue

        url = url.split("#", 1)[0]
        if url not in pages:
            pages.append(url)
        if len(pages) == 3:
            break

    return pages


def _clean(raw: str) -> str:
    email = raw.split("?", 1)[0].strip().lower()
    if email.startswith("u003e"):
        email = email[4:]

    return email.strip(".,;:<>")


def _usable(email: str) -> bool:
    if email.count("@") != 1:
        return False

    local, host = email.split("@", 1)
    tld = host.rsplit(".", 1)[-1]
    if tld in _FILE_TLDS or not re.search(r"[a-z]", local):
        return False
    if any(part in host for part in _SKIP_HOSTS):
        return False
    if any(word in local for word in ("firstname", "lastname", "yourname", "example")):
        return False

    return True


def _mail_host(website: str) -> str:
    try:
        host = urlparse(normalize_url(website)).hostname or ""
    except ValueError:
        return ""

    return host.removeprefix("www.")


def _on_site(email: str, host: str) -> bool:
    if not host or "@" not in email:
        return False

    domain = email.split("@", 1)[1]

    return domain == host or domain.endswith(f".{host}")


def _person_tokens(person: str) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]{2,}", person)

    return [_fold(word) for word in words]


def _hits(email: str, tokens: list[str]) -> int:
    local = _fold(email.split("@", 1)[0])

    return sum(1 for token in tokens if token in local)


def _is_generic(email: str) -> bool:
    return _local_root(email) in _GENERIC


def _local_root(email: str) -> str:
    return _fold(email.split("@", 1)[0].split(".", 1)[0])


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)

    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
