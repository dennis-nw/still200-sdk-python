from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest

import still200_sdk._decorator as decorator_module
from still200_sdk import monitor
from still200_sdk._config import Config


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    path: str
    ping_token: str | None
    body: dict[str, Any] | None


@pytest.fixture
def api_server() -> Generator[tuple[str, list[RecordedRequest]]]:
    requests: list[RecordedRequest] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", 0))
            content = self.rfile.read(content_length)
            body = json.loads(content) if content else None
            requests.append(
                RecordedRequest(
                    path=self.path,
                    ping_token=self.headers.get("STILL200_PING_TOKEN"),
                    body=body,
                )
            )
            self.send_response(204)
            self.end_headers()

        def log_message(self, format_: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        yield f"http://{host}:{port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def use_api_server(monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    def resolve_config(ping_token: str | None) -> Config:
        return Config(ping_token=ping_token or "integration-token", base_url=base_url)

    monkeypatch.setattr(decorator_module, "_resolve_config", resolve_config)


def test_sync_job_reports_start_and_finish(
    api_server: tuple[str, list[RecordedRequest]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url, requests = api_server
    use_api_server(monkeypatch, base_url)

    @monitor()
    def job() -> str:
        return "done"

    assert job() == "done"
    assert requests == [
        RecordedRequest("/jobs/ping/start", "integration-token", None),
        RecordedRequest("/jobs/ping/finish", "integration-token", None),
    ]


def test_async_job_reports_start_and_finish(
    api_server: tuple[str, list[RecordedRequest]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url, requests = api_server
    use_api_server(monkeypatch, base_url)

    @monitor(ping_token="async-token")
    async def job() -> str:
        return "done"

    assert asyncio.run(job()) == "done"
    assert requests == [
        RecordedRequest("/jobs/ping/start", "async-token", None),
        RecordedRequest("/jobs/ping/finish", "async-token", None),
    ]


def test_failed_job_reports_error_and_preserves_exception(
    api_server: tuple[str, list[RecordedRequest]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url, requests = api_server
    use_api_server(monkeypatch, base_url)
    error = RuntimeError("job broke")

    @monitor()
    def job() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        job()

    assert caught.value is error
    assert requests == [
        RecordedRequest("/jobs/ping/start", "integration-token", None),
        RecordedRequest(
            "/jobs/ping/fail",
            "integration-token",
            {"error_message": "job broke"},
        ),
    ]
