"""HTTP client for the Still200 API."""

import uuid
from types import TracebackType
from typing import Any, Self

import httpx2

from still200_sdk._config import Config
from still200_sdk._run import CurrentRun

PING_TOKEN_HEADER = "Still200-Ping-Token"
RUN_ID_HEADER = "Still200-Run-Id"
PING_PATH = "/jobs/ping"


class Client:
    """Synchronous client for scheduled-job pings."""

    def __init__(
        self,
        config: Config,
        *,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._client = httpx2.Client(
            base_url=config.base_url,
            headers={PING_TOKEN_HEADER: config.ping_token},
            timeout=config.timeout,
            transport=transport,
        )

    def start(self) -> CurrentRun:
        """Report that the scheduled job has started."""
        return _run_from_response(self._ping("start"))

    def finish(self, run_id: uuid.UUID) -> None:
        """Report that the scheduled job completed successfully."""
        self._ping("finish", headers=_run_headers(run_id))

    def fail(
        self,
        run_id: uuid.UUID,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Report that the scheduled job failed."""
        data = _failure_data(error_message=error_message, payload=payload)
        self._ping("fail", headers=_run_headers(run_id), json=data)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _ping(
        self,
        ping_type: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx2.Response:
        response = self._client.post(
            f"{PING_PATH}/{ping_type}", headers=headers, json=json
        )
        response.raise_for_status()
        return response


class AsyncClient:
    """Asynchronous client for scheduled-job pings."""

    def __init__(
        self,
        config: Config,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx2.AsyncClient(
            base_url=config.base_url,
            headers={PING_TOKEN_HEADER: config.ping_token},
            timeout=config.timeout,
            transport=transport,
        )

    async def start(self) -> CurrentRun:
        """Report that the scheduled job has started."""
        return _run_from_response(await self._ping("start"))

    async def finish(self, run_id: uuid.UUID) -> None:
        """Report that the scheduled job completed successfully."""
        await self._ping("finish", headers=_run_headers(run_id))

    async def fail(
        self,
        run_id: uuid.UUID,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Report that the scheduled job failed."""
        data = _failure_data(error_message=error_message, payload=payload)
        await self._ping("fail", headers=_run_headers(run_id), json=data)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def _ping(
        self,
        ping_type: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx2.Response:
        response = await self._client.post(
            f"{PING_PATH}/{ping_type}", headers=headers, json=json
        )
        response.raise_for_status()
        return response


def _run_from_response(response: httpx2.Response) -> CurrentRun:
    data = response.json()
    run_id = data.get("id") if isinstance(data, dict) else None

    try:
        return CurrentRun(id=uuid.UUID(str(run_id)))
    except ValueError as exc:
        raise ValueError(
            "Still200 start response did not contain a valid run ID."
        ) from exc


def _run_headers(run_id: uuid.UUID) -> dict[str, str]:
    return {RUN_ID_HEADER: str(run_id)}


def _failure_data(
    *,
    error_message: str | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    if error_message is not None:
        data["error_message"] = error_message
    if payload is not None:
        data["payload"] = payload

    return data
