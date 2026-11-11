import asyncio

import httpx2
import pytest

from still200_sdk._client import PING_TOKEN_HEADER, AsyncClient, Client
from still200_sdk._config import Config


def test_sync_client_sends_all_ping_types() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(204)

    config = Config(ping_token="job-secret")
    transport = httpx2.MockTransport(handler)

    with Client(config, transport=transport) as client:
        client.start()
        client.finish()
        client.fail(error_message="broken", payload={"attempt": 2})

    assert [request.url.path for request in requests] == [
        "/jobs/ping/start",
        "/jobs/ping/finish",
        "/jobs/ping/fail",
    ]
    assert all(
        request.headers[PING_TOKEN_HEADER] == "job-secret" for request in requests
    )
    assert requests[2].read() == b'{"error_message":"broken","payload":{"attempt":2}}'


def test_sync_client_raises_for_error_response() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, request=request)

    config = Config(ping_token="job-secret")
    transport = httpx2.MockTransport(handler)

    with (
        Client(config, transport=transport) as client,
        pytest.raises(httpx2.HTTPStatusError),
    ):
        client.start()


def test_async_client_sends_all_ping_types() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(204)

    async def run() -> None:
        config = Config(ping_token="job-secret")
        transport = httpx2.MockTransport(handler)

        async with AsyncClient(config, transport=transport) as client:
            await client.start()
            await client.finish()
            await client.fail(error_message="broken", payload={"attempt": 2})

    asyncio.run(run())

    assert [request.url.path for request in requests] == [
        "/jobs/ping/start",
        "/jobs/ping/finish",
        "/jobs/ping/fail",
    ]
    assert all(
        request.headers[PING_TOKEN_HEADER] == "job-secret" for request in requests
    )
    assert requests[2].read() == b'{"error_message":"broken","payload":{"attempt":2}}'


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_fail_omits_unavailable_failure_data(
    client_type: type[Client | AsyncClient],
) -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(204)

    config = Config(ping_token="job-secret")
    transport = httpx2.MockTransport(handler)

    if client_type is Client:
        with Client(config, transport=transport) as client:
            client.fail()
    else:

        async def run() -> None:
            async with AsyncClient(config, transport=transport) as client:
                await client.fail()

        asyncio.run(run())

    assert requests[0].read() == b"{}"
