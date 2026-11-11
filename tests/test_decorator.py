import asyncio
from typing import Any, ClassVar

import pytest

import still200_sdk._decorator as decorator_module
from still200_sdk import monitor
from still200_sdk._config import PING_TOKEN_ENV_VAR, Config


class FakeClient:
    events: ClassVar[list[tuple[str, Any]]] = []
    config: Config
    failures: ClassVar[set[str]] = set()

    def __init__(self, config: Config) -> None:
        type(self).config = config

    def start(self) -> None:
        self._record("start")

    def finish(self) -> None:
        self._record("finish")

    def fail(
        self,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._record("fail", error_message)

    def close(self) -> None:
        self._record("close")

    def _record(self, event: str, value: Any = None) -> None:
        type(self).events.append((event, value))
        if event in type(self).failures:
            raise RuntimeError(f"{event} ping failed")


class FakeAsyncClient(FakeClient):
    async def start(self) -> None:
        super().start()

    async def finish(self) -> None:
        super().finish()

    async def fail(
        self,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().fail(error_message=error_message, payload=payload)

    async def close(self) -> None:
        super().close()


@pytest.fixture(autouse=True)
def fake_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.events = []
    FakeClient.failures = set()
    FakeAsyncClient.events = []
    FakeAsyncClient.failures = set()
    monkeypatch.setattr(decorator_module, "Client", FakeClient)
    monkeypatch.setattr(decorator_module, "AsyncClient", FakeAsyncClient)


def test_monitor_wraps_successful_sync_job() -> None:
    @monitor(ping_token="sync-secret")
    def job(value: int) -> int:
        return value * 2

    assert job(3) == 6
    assert FakeClient.config.ping_token == "sync-secret"
    assert FakeClient.events == [("start", None), ("finish", None), ("close", None)]


def test_monitor_wraps_successful_async_job() -> None:
    @monitor(ping_token="async-secret")
    async def job(value: int) -> int:
        return value * 2

    assert asyncio.run(job(3)) == 6
    assert FakeAsyncClient.config.ping_token == "async-secret"
    assert FakeAsyncClient.events == [
        ("start", None),
        ("finish", None),
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
    assert FakeClient.events == [
        ("start", None),
        ("fail", "job broke"),
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
    assert FakeAsyncClient.events == [
        ("start", None),
        ("fail", "job broke"),
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

    assert FakeClient.events[1] == ("fail", "x" * 2_000)


def test_monitor_preserves_function_metadata() -> None:
    @monitor(ping_token="secret")
    def scheduled_job() -> None:
        """Run the scheduled job."""

    assert scheduled_job.__name__ == "scheduled_job"
    assert scheduled_job.__doc__ == "Run the scheduled job."
