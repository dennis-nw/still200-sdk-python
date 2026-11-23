import asyncio
import uuid

import httpx2
import pytest

from still200_sdk._client import AsyncClient, Client
from still200_sdk._config import Config

RUN_ID = uuid.uuid4()


def _response(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == "/jobs/ping/start":
        return httpx2.Response(201, json={"id": str(RUN_ID)})
    return httpx2.Response(204)


def test_sync_client_sends_all_ping_types() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return _response(request)

    config = Config(ping_token="job-secret")
    transport = httpx2.MockTransport(handler)

    with Client(config, transport=transport) as client:
        run = client.start()
        client.finish(run.id)
        client.fail(run.id, error_message="broken", payload={"attempt": 2})

    assert run.id == RUN_ID

    assert [request.url.path for request in requests] == [
        "/jobs/ping/start",
        "/jobs/ping/finish",
        "/jobs/ping/fail",
    ]
    assert all(
        request.headers["Still200-Ping-Token"] == "job-secret" for request in requests
    )
    assert "Still200-Run-Id" not in requests[0].headers
    assert requests[1].headers["Still200-Run-Id"] == str(RUN_ID)
    assert requests[2].headers["Still200-Run-Id"] == str(RUN_ID)
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
        return _response(request)

    async def run() -> None:
        config = Config(ping_token="job-secret")
        transport = httpx2.MockTransport(handler)

        async with AsyncClient(config, transport=transport) as client:
            run = await client.start()
            await client.finish(run.id)
            await client.fail(run.id, error_message="broken", payload={"attempt": 2})
            assert run.id == RUN_ID

    asyncio.run(run())

    assert [request.url.path for request in requests] == [
        "/jobs/ping/start",
        "/jobs/ping/finish",
        "/jobs/ping/fail",
    ]
    assert all(
        request.headers["Still200-Ping-Token"] == "job-secret" for request in requests
    )
    assert "Still200-Run-Id" not in requests[0].headers
    assert requests[1].headers["Still200-Run-Id"] == str(RUN_ID)
    assert requests[2].headers["Still200-Run-Id"] == str(RUN_ID)
    assert requests[2].read() == b'{"error_message":"broken","payload":{"attempt":2}}'


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_fail_omits_unavailable_failure_data(
    client_type: type[Client | AsyncClient],
) -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return _response(request)

    config = Config(ping_token="job-secret")
    transport = httpx2.MockTransport(handler)

    if client_type is Client:
        with Client(config, transport=transport) as client:
            client.fail(RUN_ID)
    else:

        async def run() -> None:
            async with AsyncClient(config, transport=transport) as client:
                await client.fail(RUN_ID)

        asyncio.run(run())

    assert requests[0].read() == b"{}"
    assert requests[0].headers["Still200-Run-Id"] == str(RUN_ID)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_start_requires_valid_run_id_in_response(
    client_type: type[Client | AsyncClient],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(201, json={"id": "not-a-uuid"})

    config = Config(ping_token="job-secret")
    transport = httpx2.MockTransport(handler)

    if client_type is Client:
        with Client(config, transport=transport) as client, pytest.raises(ValueError):
            client.start()
    else:

        async def run() -> None:
            async with AsyncClient(config, transport=transport) as client:
                with pytest.raises(ValueError):
                    await client.start()

        asyncio.run(run())
