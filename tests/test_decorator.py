import asyncio
import uuid
from typing import Any, ClassVar

import pytest

import still200_sdk._decorator as decorator_module
from still200_sdk import NoActiveRunError, get_current_run, get_current_run_id, monitor
from still200_sdk._config import PING_TOKEN_ENV_VAR, Config
from still200_sdk._run import CurrentRun


class FakeClient:
    events: ClassVar[list[tuple[str, Any]]] = []
    config: Config
    failures: ClassVar[set[str]] = set()
    run_ids: ClassVar[list[uuid.UUID]] = []

    def __init__(self, config: Config) -> None:
        type(self).config = config

    def start(self) -> CurrentRun:
        run = CurrentRun(id=uuid.uuid4())
        type(self).run_ids.append(run.id)
        self._record("start", run.id)
        return run

    def finish(self, run_id: uuid.UUID) -> None:
        self._record("finish", run_id)

    def fail(
        self,
        run_id: uuid.UUID,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._record("fail", (run_id, error_message))

    def close(self) -> None:
        self._record("close")

    def _record(self, event: str, value: Any = None) -> None:
        type(self).events.append((event, value))
        if event in type(self).failures:
            raise RuntimeError(f"{event} ping failed")


class FakeAsyncClient(FakeClient):
    async def start(self) -> CurrentRun:
        return super().start()

    async def finish(self, run_id: uuid.UUID) -> None:
        super().finish(run_id)

    async def fail(
        self,
        run_id: uuid.UUID,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().fail(run_id, error_message=error_message, payload=payload)

    async def close(self) -> None:
        super().close()


@pytest.fixture(autouse=True)
def fake_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.events = []
    FakeClient.failures = set()
    FakeClient.run_ids = []
    FakeAsyncClient.events = []
    FakeAsyncClient.failures = set()
    FakeAsyncClient.run_ids = []
    monkeypatch.setattr(decorator_module, "Client", FakeClient)
    monkeypatch.setattr(decorator_module, "AsyncClient", FakeAsyncClient)


def test_monitor_wraps_successful_sync_job() -> None:
    @monitor(ping_token="sync-secret")
    def job(value: int) -> int:
        return value * 2

    assert job(3) == 6
    assert FakeClient.config.ping_token == "sync-secret"
    run_id = FakeClient.run_ids[0]
    assert FakeClient.events == [
        ("start", run_id),
        ("finish", run_id),
        ("close", None),
    ]


def test_monitor_wraps_successful_async_job() -> None:
    @monitor(ping_token="async-secret")
    async def job(value: int) -> int:
        return value * 2

    assert asyncio.run(job(3)) == 6
    assert FakeAsyncClient.config.ping_token == "async-secret"
    run_id = FakeAsyncClient.run_ids[0]
    assert FakeAsyncClient.events == [
        ("start", run_id),
        ("finish", run_id),
        ("close", None),
    ]


def test_monitor_reports_sync_failure_and_preserves_exception() -> None:
    error = RuntimeError("job broke")

    @monitor(ping_token="secret")
    def job() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        job()

    assert caught.value is error
    run_id = FakeClient.run_ids[0]
    assert FakeClient.events == [
        ("start", run_id),
        ("fail", (run_id, "job broke")),
        ("close", None),
    ]


def test_monitor_reports_async_failure_and_preserves_exception() -> None:
    error = RuntimeError("job broke")

    @monitor(ping_token="secret")
    async def job() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(job())

    assert caught.value is error
    run_id = FakeAsyncClient.run_ids[0]
    assert FakeAsyncClient.events == [
        ("start", run_id),
        ("fail", (run_id, "job broke")),
        ("close", None),
    ]


def test_monitor_uses_environment_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PING_TOKEN_ENV_VAR, "environment-secret")

    @monitor()
    def job() -> None:
        pass

    job()

    assert FakeClient.config.ping_token == "environment-secret"


@pytest.mark.parametrize("failed_event", ["start", "finish", "close"])
def test_monitoring_failure_does_not_break_successful_job(failed_event: str) -> None:
    FakeClient.failures = {failed_event}

    @monitor(ping_token="secret")
    def job() -> str:
        return "done"

    assert job() == "done"


def test_failure_ping_error_does_not_replace_job_error() -> None:
    FakeClient.failures = {"fail"}
    error = RuntimeError("job broke")

    @monitor(ping_token="secret")
    def job() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        job()

    assert caught.value is error


def test_monitor_limits_error_message_length() -> None:
    @monitor(ping_token="secret")
    def job() -> None:
        raise RuntimeError("x" * 3_000)

    with pytest.raises(RuntimeError):
        job()

    run_id = FakeClient.run_ids[0]
    assert FakeClient.events[1] == ("fail", (run_id, "x" * 2_000))


def test_monitor_preserves_function_metadata() -> None:
    @monitor(ping_token="secret")
    def scheduled_job() -> None:
        """Run the scheduled job."""

    assert scheduled_job.__name__ == "scheduled_job"
    assert scheduled_job.__doc__ == "Run the scheduled job."


def test_current_run_is_available_inside_sync_job() -> None:
    captured_run = None

    @monitor(ping_token="secret")
    def job() -> uuid.UUID:
        nonlocal captured_run
        captured_run = get_current_run()
        assert get_current_run_id() == captured_run.id
        return captured_run.id

    run_id = job()

    assert captured_run is not None
    assert run_id == FakeClient.run_ids[0]
    with pytest.raises(NoActiveRunError):
        get_current_run()


def test_concurrent_async_jobs_have_isolated_run_context() -> None:
    async def run_jobs() -> list[uuid.UUID]:
        @monitor(ping_token="secret")
        async def job() -> uuid.UUID:
            before = get_current_run_id()
            await asyncio.sleep(0)
            assert get_current_run_id() == before
            return before

        return list(await asyncio.gather(job(), job()))

    run_ids = asyncio.run(run_jobs())

    assert len(set(run_ids)) == 2
    assert set(run_ids) == set(FakeAsyncClient.run_ids)


def test_current_run_is_unavailable_outside_monitored_job() -> None:
    with pytest.raises(NoActiveRunError):
        get_current_run()
