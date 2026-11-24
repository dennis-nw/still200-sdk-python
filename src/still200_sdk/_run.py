"""Context for the currently monitored scheduled-job execution."""

import contextvars
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrentRun:
    """A scheduled-job execution created by Still200."""

    id: uuid.UUID


class NoActiveRunError(RuntimeError):
    """Raised when run context is requested outside a monitored execution."""


_current_run: contextvars.ContextVar[CurrentRun | None] = contextvars.ContextVar(
    "still200_current_run",
    default=None,
)


def get_current_run() -> CurrentRun:
    """Return the run associated with the current monitored invocation."""
    run = _current_run.get()
    if run is None:
        raise NoActiveRunError("No Still200 run is active in the current context.")
    return run


def get_current_run_id() -> uuid.UUID:
    """Return the ID of the current monitored invocation."""
    return get_current_run().id


def _set_current_run(run: CurrentRun) -> contextvars.Token[CurrentRun | None]:
    return _current_run.set(run)


def _reset_current_run(token: contextvars.Token[CurrentRun | None]) -> None:
    _current_run.reset(token)
