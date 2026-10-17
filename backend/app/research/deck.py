"""Read a pitch deck and summarise the slides."""

import os
import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field

from app.research.llm import complete, judge_model
from app.schemas import PitchSummary, Startup

MAX_DECK_BYTES = 8_000_000
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
_DECK_SYSTEM = """You summarise a startup pitch deck for an investor scout.
Use only the slide text. Do not add customers, funding, dates, or people the slides do not state.
If a section is missing, leave that field empty and add one short gap.
overview is two sentences. problem, solution, traction, team, and ask are one or two sentences each.
gaps has at most four items. Describe numbers as what the deck states."""


class PitchDraft(BaseModel):
    overview: str = ""
    problem: str = ""
    solution: str = ""
    traction: str = ""
    team: str = ""
    ask: str = ""
    gaps: list[str] = Field(default_factory=list)


def deck_directory() -> Path:
    """Return the folder that holds uploaded pitch decks."""
    database = Path(os.environ.get("DATABASE_PATH", "data/radar.db"))

    return database.parent / "decks"


def store_deck(startup_id: str, filename: str, data: bytes) -> None:
    """Save one uploaded deck next to the database."""
    folder = deck_directory()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{startup_id}.pptx").write_bytes(data)
    (folder / f"{startup_id}.filename").write_text(filename, encoding="utf-8")


def load_deck(startup_id: str) -> tuple[str, bytes] | None:
    """Return the stored filename and bytes, when a deck was uploaded."""
    path = deck_directory() / f"{startup_id}.pptx"
    if not path.is_file():
        return None

    name_path = deck_directory() / f"{startup_id}.filename"
    filename = name_path.read_text(encoding="utf-8").strip() if name_path.is_file() else "pitch.pptx"

    return filename or "pitch.pptx", path.read_bytes()


def safe_filename(name: str) -> str:
    """Keep a download name that is a single pptx file."""
    base = Path(name).name.replace('"', "").replace("\n", "").strip()
    if not base.lower().endswith(".pptx"):
        return "pitch.pptx"

    return base or "pitch.pptx"


def deck_text(data: bytes) -> str:
    """Return the readable text of each slide."""
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Upload a .pptx pitch deck.") from exc

    names = sorted(
        (name for name in archive.namelist() if _SLIDE.search(name)),
        key=lambda name: int(_SLIDE.search(name).group(1)),
    )
    if not names:
        raise ValueError("Upload a .pptx pitch deck.")

    slides = []
    for name in names:
        number = int(_SLIDE.search(name).group(1))
        root = ElementTree.fromstring(archive.read(name))
        parts = []
        for node in root.iter():
            if node.tag.endswith("}t") and node.text and node.text.strip():
                parts.append(node.text.strip())
        if parts:
            slides.append(f"Slide {number}: " + " ".join(parts))

    return "\n".join(slides)


def summarize_pitch(company: str, filename: str, text: str) -> PitchSummary:
    """Write slide summaries from the deck, or note that the key is missing."""
    if not text.strip():
        return PitchSummary(
            filename=filename,
            gaps=["The pitch deck has no readable text."],
        )

    if not os.environ.get("OPENAI_API_KEY"):
        return PitchSummary(
            filename=filename,
            overview=text[:600],
            gaps=["Set OPENAI_API_KEY to write the deck summary."],
        )

    draft = complete(
        model=judge_model(),
        system=_DECK_SYSTEM,
        user=f"Company: {company}\n\nSlides:\n{text[:12000]}",
        schema=PitchDraft,
    )

    return PitchSummary(
        filename=filename,
        overview=draft.overview.strip(),
        problem=draft.problem.strip(),
        solution=draft.solution.strip(),
        traction=draft.traction.strip(),
        team=draft.team.strip(),
        ask=draft.ask.strip(),
        gaps=[item.strip() for item in draft.gaps if item.strip()][:4],
    )


def attach_pitch(startup: Startup) -> Startup:
    """Add the stored deck summary when this company has an uploaded deck."""
    stored = load_deck(startup.id)
    if stored is None:
        return startup

    filename, data = stored
    try:
        text = deck_text(data)
    except ValueError as exc:
        startup.pitch = PitchSummary(filename=filename, gaps=[str(exc)])

        return startup

    try:
        startup.pitch = summarize_pitch(startup.name, filename, text)
    except Exception as exc:
        startup.pitch = PitchSummary(
            filename=filename,
            gaps=[f"The deck summary could not be written: {exc}"],
        )

    return startup


def example_slides() -> list[tuple[str, list[str]]]:
    """Return the fictional sample deck used to try the summary."""
    return [
        (
            "Harborline Sensors",
            [
                "Sample pitch deck for Ocean Opportunity Radar.",
                "This company is fictional. Nothing in these slides is a real fundraising claim.",
            ],
        ),
        (
            "Problem",
            [
                "Small harbours lose berth time because arrival windows are guessed from radio calls.",
                "A missed window keeps a fishing vessel burning fuel outside the quay.",
            ],
        ),
        (
            "Solution",
            [
                "Harborline mounts a solar sensor on the outer buoy.",
                "The sample product, Buoy Window, sends a four-hour arrival window to the harbour master.",
            ],
        ),
        (
            "Traction",
            [
                "Sample figures only: three harbour pilots in Finland during 2025 and 120 recorded arrivals.",
                "The deck also states a letter of intent from a municipal port. No revenue is claimed.",
            ],
        ),
        (
            "Team",
            [
                "Sample names: Aino Korhonen, skipper and product lead.",
                "Pekka Laine, embedded engineer. This deck does not include personal emails.",
            ],
        ),
        (
            "The ask",
            [
                "Sample ask: 400,000 euro to build ten buoy units and run one winter season.",
                "This amount exists only inside the sample deck.",
            ],
        ),
    ]


def example_deck_bytes() -> bytes:
    """Build the sample pitch deck as a pptx file."""
    return _pptx(example_slides())


def _pptx(slides: list[tuple[str, list[str]]]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(len(slides)))
        archive.writestr("_rels/.rels", _package_rels())
        archive.writestr("docProps/core.xml", _core_props())
        archive.writestr("docProps/app.xml", _app_props(len(slides)))
        archive.writestr("ppt/presentation.xml", _presentation(len(slides)))
        archive.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels(len(slides)))
        archive.writestr("ppt/presProps.xml", _pres_props())
        archive.writestr("ppt/viewProps.xml", _view_props())
        archive.writestr("ppt/theme/theme1.xml", _theme())
        archive.writestr("ppt/slideMasters/slideMaster1.xml", _master())
        archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _master_rels())
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", _layout())
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _layout_rels())
        for index, (title, lines) in enumerate(slides, start=1):
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                _slide(
                    title,
                    lines,
                    index,
                    len(slides),
                ),
            )
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", _slide_rels())

    return buffer.getvalue()


def _content_types(count: int) -> str:
    overrides = [
        _override("/ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
        _override("/ppt/slideMasters/slideMaster1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"),
        _override("/ppt/slideLayouts/slideLayout1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"),
        _override("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        _override("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
        _override("/docProps/app.xml", "application/vnd.openxmlformats-officedocument.extended-properties+xml"),
        _override("/ppt/presProps.xml", "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"),
        _override("/ppt/viewProps.xml", "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"),
    ]
    for index in range(1, count + 1):
        overrides.append(
            _override(
                f"/ppt/slides/slide{index}.xml",
                "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            )
        )

    body = "".join(overrides)

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{body}</Types>"
    )


def _override(part: str, content_type: str) -> str:
    return f'<Override PartName="{part}" ContentType="{content_type}"/>'


def _package_rels() -> str:
    return _rels(
        [
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "ppt/presentation.xml"),
            ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
            ("rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"),
        ]
    )


def _presentation(count: int) -> str:
    slides = "".join(
        f'<p:sldId id="{256 + index}" r:id="rId{index + 1}"/>'
        for index in range(1, count + 1)
    )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slides}</p:sldIdLst>"
        '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )


def _presentation_rels(count: int) -> str:
    items = [
        ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "slideMasters/slideMaster1.xml"),
    ]
    for index in range(1, count + 1):
        items.append(
            (
                f"rId{index + 1}",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                f"slides/slide{index}.xml",
            )
        )

    items.append(
        (
            "rId20",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps",
            "presProps.xml",
        )
    )
    items.append(
        (
            "rId21",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps",
            "viewProps.xml",
        )
    )

    return _rels(items)


_SLIDE_W = 12_192_000
_SLIDE_H = 6_858_000
_NAVY = "0B3A54"
_TEAL = "0E8A90"
_ICE = "F4FBFA"
_WHITE = "FFFFFF"
_INK = "143242"
_MUTED = "5C7886"
_MIST = "D7F0EE"
_FONT = "Calibri"


def _emu(inches: float) -> int:
    """Convert inches to English Metric Units."""
    return int(round(inches * 914400))


def _slide(
    title: str,
    lines: list[str],
    index: int,
    total: int,
) -> str:
    """Lay out one sample slide with explicit shape geometry."""
    if index == 1:
        return _cover(title, lines)

    if title == "Traction":
        return _traction(title, lines, index, total)

    if title == "Team":
        return _team(title, lines, index, total)

    if title == "The ask":
        return _ask(title, lines, index, total)

    return _bullets(title, lines, index, total)


def _cover(title: str, lines: list[str]) -> str:
    """Build the dark title slide."""
    paragraphs = []
    if lines:
        paragraphs.append(
            {
                "text": lines[0],
                "size": 2000,
                "color": _MIST,
                "after": 800,
            }
        )

    if len(lines) > 1:
        paragraphs.append(
            {
                "text": lines[1],
                "size": 1600,
                "color": "9BD0CB",
            }
        )

    shapes = [
        _shape(
            2,
            "Rail",
            0,
            0,
            _emu(0.16),
            _SLIDE_H,
            fill=_TEAL,
        ),
        _shape(
            3,
            "Kicker",
            _emu(0.78),
            _emu(1.9),
            _emu(10),
            _emu(0.36),
            paragraphs=[
                {
                    "text": "SAMPLE PITCH DECK",
                    "size": 1400,
                    "color": _TEAL,
                    "bold": True,
                    "spc": 220,
                }
            ],
        ),
        _shape(
            4,
            "Title",
            _emu(0.74),
            _emu(2.32),
            _emu(11.4),
            _emu(1.15),
            paragraphs=[
                {
                    "text": title,
                    "size": 5400,
                    "color": _WHITE,
                    "bold": True,
                }
            ],
        ),
        _shape(
            5,
            "Body",
            _emu(0.78),
            _emu(3.7),
            _emu(9.6),
            _emu(1.55),
            paragraphs=paragraphs,
        ),
        _shape(
            6,
            "Footer",
            _emu(0.78),
            _emu(6.5),
            _emu(10),
            _emu(0.36),
            paragraphs=[
                {
                    "text": "Ocean Opportunity Radar    ·    Fictional company",
                    "size": 1200,
                    "color": "7AA8B0",
                }
            ],
        ),
    ]

    return _slide_xml(_NAVY, shapes)


def _bullets(
    title: str,
    lines: list[str],
    index: int,
    total: int,
) -> str:
    """Build a title plus one card for each sentence."""
    shapes = _chrome(index, total, f"{index - 1:02d}    {title.upper()}")
    shapes.append(_title_block(title))
    shapes.extend(_sentence_cards(lines))

    return _slide_xml(_ICE, shapes)


def _traction(
    title: str,
    lines: list[str],
    index: int,
    total: int,
) -> str:
    """Build the sample traction figures as three stat cards."""
    metrics = (
        ("3", "Harbour pilots", "Finland, 2025"),
        ("120", "Recorded arrivals", "Sample figures only"),
        ("1", "Letter of intent", "Municipal port"),
    )
    shapes = _chrome(index, total, f"{index - 1:02d}    {title.upper()}")
    shapes.append(_title_block(title))
    card_w = 3.78
    gap = 0.22

    for offset, (value, label, note) in enumerate(metrics):
        x = 0.7 + offset * (card_w + gap)
        shapes.append(
            _shape(
                10 + offset * 2,
                f"Metric{offset}",
                _emu(x),
                _emu(2.15),
                _emu(card_w),
                _emu(2.35),
                fill=_WHITE,
                geometry="round",
            )
        )
        shapes.append(
            _shape(
                11 + offset * 2,
                f"MetricText{offset}",
                _emu(x),
                _emu(2.15),
                _emu(card_w),
                _emu(2.35),
                paragraphs=[
                    {
                        "text": value,
                        "size": 4000,
                        "color": _TEAL,
                        "bold": True,
                        "after": 600,
                    },
                    {
                        "text": label,
                        "size": 1600,
                        "color": _NAVY,
                        "bold": True,
                        "after": 200,
                    },
                    {
                        "text": note,
                        "size": 1300,
                        "color": _MUTED,
                    },
                ],
                anchor="ctr",
                insets=(
                    _emu(0.28),
                    _emu(0.2),
                    _emu(0.28),
                    _emu(0.2),
                ),
            )
        )

    shapes.append(
        _shape(
            30,
            "Notes",
            _emu(0.7),
            _emu(4.75),
            _emu(11.9),
            _emu(1.9),
            paragraphs=[
                {
                    "text": line,
                    "size": 1500,
                    "color": _MUTED,
                    "after": 600,
                }
                for line in lines
            ],
        )
    )

    return _slide_xml(_ICE, shapes)


def _team(
    title: str,
    lines: list[str],
    index: int,
    total: int,
) -> str:
    """Build two sample profile cards."""
    people = (
        ("AK", "Aino Korhonen", "Skipper and product lead"),
        ("PL", "Pekka Laine", "Embedded engineer"),
    )
    shapes = _chrome(index, total, f"{index - 1:02d}    {title.upper()}")
    shapes.append(_title_block(title))

    for offset, (initials, name, role) in enumerate(people):
        sentence = lines[offset] if offset < len(lines) else ""
        x = 0.7 + offset * 6.15
        y = 2.35
        shapes.extend(
            [
                _shape(
                    10 + offset * 4,
                    f"Person{offset}",
                    _emu(x),
                    _emu(y),
                    _emu(5.9),
                    _emu(2.9),
                    fill=_WHITE,
                    geometry="round",
                ),
                _shape(
                    11 + offset * 4,
                    f"Avatar{offset}",
                    _emu(x + 0.38),
                    _emu(y + 0.36),
                    _emu(0.72),
                    _emu(0.72),
                    paragraphs=[
                        {
                            "text": initials,
                            "size": 1400,
                            "color": _WHITE,
                            "bold": True,
                            "align": "ctr",
                        }
                    ],
                    fill=_TEAL,
                    geometry="round",
                    anchor="ctr",
                    radius=50000,
                ),
                _shape(
                    12 + offset * 4,
                    f"Name{offset}",
                    _emu(x + 1.28),
                    _emu(y + 0.36),
                    _emu(4.2),
                    _emu(0.78),
                    paragraphs=[
                        {
                            "text": name,
                            "size": 2000,
                            "color": _NAVY,
                            "bold": True,
                            "after": 60,
                        },
                        {
                            "text": role,
                            "size": 1400,
                            "color": _TEAL,
                        },
                    ],
                    anchor="ctr",
                ),
                _shape(
                    13 + offset * 4,
                    f"Bio{offset}",
                    _emu(x + 0.38),
                    _emu(y + 1.3),
                    _emu(5.15),
                    _emu(1.3),
                    paragraphs=[
                        {
                            "text": sentence,
                            "size": 1500,
                            "color": _INK,
                        }
                    ],
                ),
            ]
        )

    return _slide_xml(_ICE, shapes)


def _ask(
    title: str,
    lines: list[str],
    index: int,
    total: int,
) -> str:
    """Build the closing ask with the sample amount on a dark panel."""
    shapes = [
        _shape(
            2,
            "Panel",
            0,
            0,
            _emu(6.35),
            _SLIDE_H,
            fill=_NAVY,
        ),
        _shape(
            3,
            "Rail",
            0,
            0,
            _emu(0.16),
            _SLIDE_H,
            fill=_TEAL,
        ),
        _shape(
            4,
            "Kicker",
            _emu(0.58),
            _emu(1.7),
            _emu(5.2),
            _emu(0.34),
            paragraphs=[
                {
                    "text": f"{index - 1:02d}    THE ASK",
                    "size": 1300,
                    "color": _TEAL,
                    "bold": True,
                    "spc": 160,
                }
            ],
        ),
        _shape(
            5,
            "Title",
            _emu(0.55),
            _emu(2.15),
            _emu(5.3),
            _emu(0.7),
            paragraphs=[
                {
                    "text": title,
                    "size": 3600,
                    "color": _WHITE,
                    "bold": True,
                }
            ],
        ),
        _shape(
            6,
            "Amount",
            _emu(0.55),
            _emu(3.05),
            _emu(5.3),
            _emu(0.95),
            paragraphs=[
                {
                    "text": "€400,000",
                    "size": 4800,
                    "color": _WHITE,
                    "bold": True,
                }
            ],
        ),
        _shape(
            7,
            "Use",
            _emu(0.58),
            _emu(4.15),
            _emu(5.1),
            _emu(1.1),
            paragraphs=[
                {
                    "text": "Ten buoy units and one winter season.",
                    "size": 1600,
                    "color": _MIST,
                }
            ],
        ),
        _shape(
            8,
            "Sentences",
            _emu(6.8),
            _emu(1.9),
            _emu(5.8),
            _emu(3.4),
            paragraphs=[
                {
                    "text": line,
                    "size": 1800,
                    "color": _INK,
                    "after": 1400,
                }
                for line in lines
            ],
        ),
        _shape(
            9,
            "Footer",
            _emu(6.8),
            _emu(6.85),
            _emu(5.8),
            _emu(0.32),
            paragraphs=[
                {
                    "text": f"Harborline Sensors    ·    {index}  /  {total}",
                    "size": 1200,
                    "color": _MUTED,
                }
            ],
        ),
    ]

    return _slide_xml(_ICE, shapes)


def _chrome(
    index: int,
    total: int,
    kicker: str,
) -> list[str]:
    """Return the bar, section label, and footer shared by content slides."""
    return [
        _shape(
            2,
            "Bar",
            0,
            0,
            _SLIDE_W,
            _emu(0.08),
            fill=_TEAL,
        ),
        _shape(
            3,
            "Kicker",
            _emu(0.7),
            _emu(0.38),
            _emu(7.5),
            _emu(0.32),
            paragraphs=[
                {
                    "text": kicker,
                    "size": 1200,
                    "color": _TEAL,
                    "bold": True,
                    "spc": 140,
                }
            ],
        ),
        _shape(
            4,
            "Wordmark",
            _emu(8.6),
            _emu(0.38),
            _emu(4.0),
            _emu(0.32),
            paragraphs=[
                {
                    "text": "HARBORLINE",
                    "size": 1200,
                    "color": _NAVY,
                    "bold": True,
                    "align": "r",
                    "spc": 160,
                }
            ],
        ),
        _shape(
            20,
            "Footer",
            _emu(0.7),
            _emu(6.9),
            _emu(8.2),
            _emu(0.32),
            paragraphs=[
                {
                    "text": "Harborline Sensors    ·    Fictional sample",
                    "size": 1100,
                    "color": _MUTED,
                }
            ],
        ),
        _shape(
            21,
            "Number",
            _emu(10.2),
            _emu(6.9),
            _emu(2.4),
            _emu(0.32),
            paragraphs=[
                {
                    "text": f"{index}  /  {total}",
                    "size": 1100,
                    "color": _MUTED,
                    "align": "r",
                }
            ],
        ),
    ]


def _title_block(title: str) -> str:
    """Return the slide heading under the section kicker."""
    return _shape(
        5,
        "Title",
        _emu(0.68),
        _emu(0.78),
        _emu(11.5),
        _emu(0.85),
        paragraphs=[
            {
                "text": title,
                "size": 3600,
                "color": _NAVY,
                "bold": True,
            }
        ],
    )


def _sentence_cards(lines: list[str]) -> list[str]:
    """Return one wide card for each body sentence."""
    shapes = []
    count = max(len(lines), 1)
    gap = 0.2
    height = min(1.9, (4.5 - gap * (count - 1)) / count)

    for offset, line in enumerate(lines):
        y = 2.15 + offset * (height + gap)
        shapes.append(
            _shape(
                6 + offset * 3,
                f"Card{offset}",
                _emu(0.7),
                _emu(y),
                _emu(11.9),
                _emu(height),
                fill=_WHITE,
                geometry="round",
            )
        )
        shapes.append(
            _shape(
                7 + offset * 3,
                f"Accent{offset}",
                _emu(1.02),
                _emu(y + 0.38),
                _emu(0.07),
                _emu(max(height - 0.76, 0.4)),
                fill=_TEAL,
                geometry="round",
                radius=50000,
            )
        )
        shapes.append(
            _shape(
                8 + offset * 3,
                f"CardText{offset}",
                _emu(1.25),
                _emu(y),
                _emu(11.05),
                _emu(height),
                paragraphs=[
                    {
                        "text": line,
                        "size": 2000,
                        "color": _INK,
                    }
                ],
                anchor="ctr",
                insets=(
                    _emu(0.1),
                    _emu(0.12),
                    _emu(0.35),
                    _emu(0.12),
                ),
            )
        )

    return shapes


def _slide_xml(background: str, shapes: list[str]) -> str:
    """Wrap positioned shapes in one slide."""
    body = "".join(shapes)

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:cSld><p:bg><p:bgPr>"
        f'<a:solidFill><a:srgbClr val="{background}"/></a:solidFill>'
        "<a:effectLst/></p:bgPr></p:bg><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name="Slide"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f"{body}</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def _shape(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: list[dict] | None = None,
    fill: str | None = None,
    geometry: str = "rect",
    anchor: str = "t",
    insets: tuple[int, int, int, int] = (0, 0, 0, 0),
    radius: int = 8000,
) -> str:
    """Return one shape with a real position, size, and optional text."""
    text_box = ' txBox="1"' if paragraphs else ""
    left, top, right, bottom = insets
    if paragraphs:
        text = _paragraphs(paragraphs)
    else:
        text = "<a:p/>"

    return (
        "<p:sp><p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        f"<p:cNvSpPr{text_box}/><p:nvPr/></p:nvSpPr><p:spPr>"
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f"{_geometry(geometry, radius)}{_fill(fill)}</p:spPr><p:txBody>"
        f'<a:bodyPr wrap="square" lIns="{left}" tIns="{top}" rIns="{right}" bIns="{bottom}" '
        f'rtlCol="0" anchor="{anchor}"/><a:lstStyle/>{text}</p:txBody></p:sp>'
    )


def _paragraphs(paragraphs: list[dict]) -> str:
    """Return drawingML paragraphs for one text body."""
    chunks = []

    for spec in paragraphs:
        spacing = spec.get("spc")
        spacing_attr = f' spc="{spacing}"' if spacing else ""
        chunks.append(
            "<a:p>"
            f'<a:pPr algn="{spec.get("align", "l")}">'
            f'<a:spcBef><a:spcPts val="{spec.get("before", 0)}"/></a:spcBef>'
            f'<a:spcAft><a:spcPts val="{spec.get("after", 0)}"/></a:spcAft>'
            "</a:pPr><a:r>"
            f'<a:rPr lang="en-US" sz="{spec["size"]}" b="{1 if spec.get("bold") else 0}" dirty="0"{spacing_attr}>'
            f'<a:solidFill><a:srgbClr val="{spec.get("color", _INK)}"/></a:solidFill>'
            f'<a:latin typeface="{_FONT}"/><a:ea typeface="{_FONT}"/><a:cs typeface="{_FONT}"/>'
            "</a:rPr>"
            f"<a:t>{escape(spec['text'])}</a:t></a:r></a:p>"
        )

    return "".join(chunks)


def _geometry(kind: str, radius: int) -> str:
    """Return a preset geometry for rectangles, rounded cards, or avatars."""
    if kind == "ellipse":
        return '<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>'

    if kind == "round":
        return (
            '<a:prstGeom prst="roundRect"><a:avLst>'
            f'<a:gd name="adj" fmla="val {radius}"/>'
            "</a:avLst></a:prstGeom>"
        )

    return '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'


def _fill(color: str | None) -> str:
    """Return a solid fill, or no fill for a text-only box."""
    if color is None:
        return "<a:noFill/><a:ln><a:noFill/></a:ln>"

    return f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:ln><a:noFill/></a:ln>'


def _slide_rels() -> str:
    return _rels(
        [
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"),
        ]
    )


def _master() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        "</p:spTree></p:cSld>"
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
        'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        "</p:sldMaster>"
    )


def _master_rels() -> str:
    return _rels(
        [
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme", "../theme/theme1.xml"),
        ]
    )


def _layout() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="titleAndBody">'
        '<p:cSld name="Title and Content"><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )


def _layout_rels() -> str:
    return _rels(
        [
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "../slideMasters/slideMaster1.xml"),
        ]
    )


def _theme() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Harborline">'
        "<a:themeElements><a:clrScheme name=\"Harborline\">"
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="0E3A4D"/></a:dk2><a:lt2><a:srgbClr val="E6F4F4"/></a:lt2>'
        '<a:accent1><a:srgbClr val="0E8A86"/></a:accent1><a:accent2><a:srgbClr val="1F6F8B"/></a:accent2>'
        '<a:accent3><a:srgbClr val="F2C14E"/></a:accent3><a:accent4><a:srgbClr val="5C6B73"/></a:accent4>'
        '<a:accent5><a:srgbClr val="9BD0CB"/></a:accent5><a:accent6><a:srgbClr val="D8E2DC"/></a:accent6>'
        '<a:hlink><a:srgbClr val="0E8A86"/></a:hlink><a:folHlink><a:srgbClr val="5C6B73"/></a:folHlink>'
        "</a:clrScheme><a:fontScheme name=\"Harborline\">"
        '<a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        "</a:fontScheme><a:fmtScheme name=\"Harborline\">"
        "<a:fillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:fillStyleLst>"
        "<a:lnStyleLst><a:ln w=\"6350\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
        "<a:ln w=\"12700\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
        "<a:ln w=\"19050\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln></a:lnStyleLst>"
        "<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>"
        "<a:bgFillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:bgFillStyleLst>"
        "</a:fmtScheme></a:themeElements></a:theme>"
    )


def _core_props() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Harborline Sensors sample pitch deck</dc:title>"
        "<dc:creator>Ocean Opportunity Radar</dc:creator>"
        "</cp:coreProperties>"
    )


def _pres_props() -> str:
    """Return the presentation properties part Office expects."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentationPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:showPr/></p:presentationPr>"
    )


def _view_props() -> str:
    """Return a 16:9 slide view so previewers open on the first slide."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:viewPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" lastView="sldView">'
        '<p:normalViewPr><p:restoredLeft sz="15620"/><p:restoredTop sz="94660"/></p:normalViewPr>'
        "<p:slideViewPr><p:cSldViewPr><p:cViewPr varScale=\"1\"><p:scale>"
        '<a:sx n="100" d="100"/><a:sy n="100" d="100"/></p:scale><p:origin x="0" y="0"/>'
        "</p:cViewPr><p:guideLst/></p:cSldViewPr></p:slideViewPr>"
        "<p:notesTextViewPr><p:cViewPr><p:scale>"
        '<a:sx n="100" d="100"/><a:sy n="100" d="100"/></p:scale><p:origin x="0" y="0"/>'
        "</p:cViewPr></p:notesTextViewPr>"
        '<p:gridSpacing cx="78028800" cy="78028800"/>'
        "</p:viewPr>"
    )


def _app_props(count: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        f"<Slides>{count}</Slides><PresentationFormat>On-screen Show (16:9)</PresentationFormat>"
        "</Properties>"
    )


def _rels(items: list[tuple[str, str, str]]) -> str:
    body = "".join(
        f'<Relationship Id="{item_id}" Type="{rel_type}" Target="{target}"/>'
        for item_id, rel_type, target in items
    )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{body}</Relationships>"
    )
