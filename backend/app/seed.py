from app.research.targets import portfolio_startups
from app.schemas import Startup


def load_seed() -> list[Startup]:
    """Return the unassessed real-company portfolio."""
    return portfolio_startups()
