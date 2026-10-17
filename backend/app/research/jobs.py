"""Run portfolio research without blocking the request that started it."""

import os
import threading
from datetime import datetime, timezone

from app.repository import Repository
from app.research.pipeline import research_company
from app.research.targets import Target, select_targets
from app.schemas import ResearchStatus

_lock = threading.Lock()
_status = ResearchStatus(status="idle")
_queue: list[Target] = []
_errors: list[str] = []


def get_status() -> ResearchStatus:
    """Return a copy of the current research job."""
    with _lock:
        return _status.model_copy(deep=True)


def start_research(
    repository: Repository,
    names: list[str],
    ids: list[str] | None = None,
) -> ResearchStatus:
    """Queue portfolio companies, stored companies, or both."""
    selected_ids = ids or []
    if selected_ids:
        targets, missing = _targets_from_ids(repository, selected_ids)
        if names:
            more, more_missing = select_targets(names)
            targets.extend(more)
            missing.extend(more_missing)
    else:
        targets, missing = select_targets(names)

    return enqueue(
        repository,
        targets,
        [f"Unknown company: {name}" for name in missing],
    )


def enqueue(
    repository: Repository,
    targets: list[Target],
    errors: list[str],
) -> ResearchStatus:
    """Add companies to the research queue and start it when it is idle."""
    global _status
    with _lock:
        running = _status.status == "running"
        if running:
            _errors.extend(errors)
        else:
            _errors.clear()
            _errors.extend(errors)

        queued = {item.id for item in _queue}
        for target in targets:
            if target.id in queued:
                continue
            _queue.append(target)
            queued.add(target.id)

        if not running:
            current = _queue[0].name if _queue else ""
            _status = ResearchStatus(
                status="running",
                message="Collecting public sources.",
                current=current,
                errors=list(_errors),
            )

    if not running:
        threading.Thread(
            target=_drain,
            args=(repository,),
            name="startup-research",
            daemon=True,
        ).start()

    return get_status()


def _targets_from_ids(
    repository: Repository,
    ids: list[str],
) -> tuple[list[Target], list[str]]:
    """Load stored companies and list ids that are not in the database."""
    from app.research.links import target_from_startup

    targets = []
    missing = []
    for startup_id in ids:
        startup = repository.get(startup_id)
        if startup is None:
            missing.append(startup_id)
        else:
            targets.append(target_from_startup(startup))

    return targets, missing


def _drain(repository: Repository) -> None:
    """Research each queued company, including any added while this run is going."""
    global _status
    completed: list[str] = []
    any_scored = False
    while True:
        with _lock:
            if not _queue:
                _status = _completed_status(completed, any_scored)
                return
            target = _queue.pop(0)

        _update(current=target.name)
        try:
            startup = research_company(target)
            repository.save(startup)
            completed.append(startup.name)
            any_scored = any_scored or startup.assessed
        except Exception as exc:
            with _lock:
                _errors.append(f"{target.name}: {exc}")


def _completed_status(completed: list[str], any_scored: bool) -> ResearchStatus:
    """Build the finished status. Caller must hold the job lock."""
    errors = list(_errors)
    if not completed and not errors:
        message = "No companies selected."
    elif not any_scored and not os.environ.get("OPENAI_API_KEY"):
        message = "Sources were collected. Set OPENAI_API_KEY to score them."
    elif errors and not completed:
        message = "Research failed."
    else:
        message = "Research finished."

    return ResearchStatus(
        status="error" if errors and not completed else "done",
        message=message,
        current="",
        completed=completed,
        errors=errors,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )


def _update(**changes: object) -> None:
    """Replace the shared job status under the lock."""
    global _status
    with _lock:
        _status = _status.model_copy(update=changes)
