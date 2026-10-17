import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.assess import placeholder_assessment
from app.research.targets import PORTFOLIO_VERSION
from app.schemas import Profile, Startup
from app.seed import load_seed


def search_text(startup: Startup) -> str:
    """Build the lowercase text used by name and profile search."""
    profile = startup.profile
    parts = [
        startup.name,
        startup.tagline,
        startup.sector,
        startup.country,
        startup.stage,
        profile.website,
        profile.hq,
        profile.founders,
        profile.email,
        profile.description,
        " ".join(profile.keywords),
        " ".join(hit.title for hit in startup.sources),
        profile.problem,
        profile.solution,
        profile.business_model,
        profile.customers,
        profile.traction,
        profile.funding,
        profile.advantage,
        profile.competitors,
        profile.thesis,
    ]

    return " ".join(parts).lower()


def like_pattern(query: str) -> str:
    """Escape a user query for a SQLite LIKE match."""
    escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    return f"%{escaped}%"


class Repository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def init(self) -> None:
        """Create the database and load sample startups when it is empty."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS startups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    thesis_fit INTEGER NOT NULL,
                    search_text TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

        if self._meta("portfolio_version") != PORTFOLIO_VERSION:
            self._install_portfolio()

    def count(self) -> int:
        """Return how many startups are stored."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM startups").fetchone()

        return int(row["total"])

    def list_startups(
        self,
        query: str | None = None,
        sector: str | None = None,
    ) -> list[Startup]:
        """Return startups ranked by thesis fit."""
        sql = "SELECT payload FROM startups WHERE 1 = 1"
        params: list[str] = []

        if sector:
            sql += " AND sector = ?"
            params.append(sector)

        if query:
            sql += " AND search_text LIKE ? ESCAPE '\\'"
            params.append(like_pattern(query))

        sql += " ORDER BY thesis_fit DESC, name COLLATE NOCASE"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [Startup.model_validate_json(row["payload"]) for row in rows]

    def sectors(self) -> list[str]:
        """Return the distinct sectors in alphabetical order."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT sector FROM startups ORDER BY sector COLLATE NOCASE"
            ).fetchall()

        return [row["sector"] for row in rows]

    def get(self, startup_id: str) -> Startup | None:
        """Return one startup, or None when the id is unknown."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM startups WHERE id = ?",
                (startup_id,),
            ).fetchone()

        if row is None:
            return None

        return Startup.model_validate_json(row["payload"])

    def create(
        self,
        name: str,
        stage: str,
        profile: Profile,
    ) -> Startup:
        """Store a startup with a placeholder assessment."""
        startup = placeholder_assessment(
            name=name,
            stage=stage,
            profile=profile,
        )
        self.save(startup)

        return startup

    def save(self, startup: Startup) -> None:
        """Insert or replace one startup."""
        payload = startup.model_dump_json(by_alias=True)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO startups (id, name, sector, thesis_fit, search_text, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    sector = excluded.sector,
                    thesis_fit = excluded.thesis_fit,
                    search_text = excluded.search_text,
                    payload = excluded.payload
                """,
                (
                    startup.id,
                    startup.name,
                    startup.sector,
                    startup.thesis_fit,
                    search_text(startup),
                    payload,
                ),
            )

    def _install_portfolio(self) -> None:
        """Replace stored startups with the current real-company portfolio."""
        with self._connect() as conn:
            conn.execute("DELETE FROM startups")
            for startup in load_seed():
                payload = startup.model_dump_json(by_alias=True)
                conn.execute(
                    """
                    INSERT INTO startups (id, name, sector, thesis_fit, search_text, payload)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        startup.id,
                        startup.name,
                        startup.sector,
                        startup.thesis_fit,
                        search_text(startup),
                        payload,
                    ),
                )
            conn.execute(
                """
                INSERT INTO meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                ("portfolio_version", PORTFOLIO_VERSION),
            )

    def _meta(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()

        if row is None:
            return ""

        return str(row["value"])

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection that commits on success and always closes."""
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
