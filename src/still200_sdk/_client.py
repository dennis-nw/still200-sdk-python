"""HTTP client for the Still200 API."""

from types import TracebackType
from typing import Any, Self

import httpx2

from still200_sdk._config import Config

PING_TOKEN_HEADER = "STILL200_PING_TOKEN"
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

    def start(self) -> None:
        """Report that the scheduled job has started."""
        self._ping("start")

    def finish(self) -> None:
        """Report that the scheduled job completed successfully."""
        self._ping("finish")

    def fail(
        self,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Report that the scheduled job failed."""
        data = _failure_data(error_message=error_message, payload=payload)
        self._ping("fail", json=data)

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

    def _ping(self, ping_type: str, *, json: dict[str, Any] | None = None) -> None:
        response = self._client.post(f"{PING_PATH}/{ping_type}", json=json)
        response.raise_for_status()


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

    async def start(self) -> None:
        """Report that the scheduled job has started."""
        await self._ping("start")

    async def finish(self) -> None:
        """Report that the scheduled job completed successfully."""
        await self._ping("finish")

    async def fail(
        self,
        *,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Report that the scheduled job failed."""
        data = _failure_data(error_message=error_message, payload=payload)
        await self._ping("fail", json=data)

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
        json: dict[str, Any] | None = None,
    ) -> None:
        response = await self._client.post(f"{PING_PATH}/{ping_type}", json=json)
        response.raise_for_status()


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
