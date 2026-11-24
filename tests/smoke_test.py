"""Verify that an installed distribution exposes the public SDK API."""

from still200_sdk import get_current_run_id, monitor


@monitor(ping_token="smoke-test-token")
def scheduled_job() -> None:
    """A job used to verify decorator construction and metadata."""
    assert get_current_run_id()


assert scheduled_job.__name__ == "scheduled_job"
assert (
    scheduled_job.__doc__ == "A job used to verify decorator construction and metadata."
)
