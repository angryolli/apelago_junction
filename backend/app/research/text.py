"""Small helpers for public HTML pages."""

import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return

        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def html_title(html: str) -> str:
    """Return the short company name from a page title."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match is None:
        return ""

    raw = " ".join(match.group(1).split())
    for separator in (" | ", " – ", " — ", " - "):
        if separator not in raw:
            continue

        left = raw.split(separator, 1)[0].strip()
        if 1 < len(left) <= 48:
            return left

    return raw[:80]


def visible_text(html: str) -> str:
    """Return the readable text of an HTML document."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()

    return "\n".join(parser.parts)


def readable_copy(text: str) -> str:
    """Drop short navigation labels and keep the page's sentences."""
    seen = set()
    kept = []
    for part in text.split("\n"):
        cleaned = " ".join(part.split())
        if not cleaned or cleaned in seen or len(cleaned) < 24:
            continue

        seen.add(cleaned)
        kept.append(cleaned)

    return " ".join(kept)


def clip(text: str, limit: int) -> str:
    """Trim text to a maximum length on a word boundary."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact

    trimmed = compact[:limit].rsplit(" ", 1)[0]

    return f"{trimmed}…"
