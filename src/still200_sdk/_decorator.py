"""Scheduled-job monitoring decorator."""

import inspect
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, cast

from still200_sdk._client import AsyncClient, Client
from still200_sdk._config import Config
from still200_sdk._run import _reset_current_run, _set_current_run

MAX_ERROR_MESSAGE_LENGTH = 2_000

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


def monitor(*, ping_token: str | None = None) -> Callable[[F], F]:
    """Monitor a synchronous or asynchronous scheduled job."""

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                config = _resolve_config(ping_token)

                try:
                    client = AsyncClient(config)
                except Exception:
                    logger.warning(
                        "Failed to initialize Still200 monitoring", exc_info=True
                    )
                    return await func(*args, **kwargs)

                run_token = None
                try:
                    run = await _report_safely_async(client.start)
                    run_token = _set_current_run(run) if run is not None else None

                    try:
                        result = await func(*args, **kwargs)
                    except Exception as error:
                        error_message = _error_message(error)
                        if run is not None:
                            await _report_safely_async(
                                lambda: client.fail(run.id, error_message=error_message)
                            )
                        raise

                    if run is not None:
                        await _report_safely_async(lambda: client.finish(run.id))
                    return result
                finally:
                    if run_token is not None:
                        _reset_current_run(run_token)
                    await _report_safely_async(client.close)

            return cast(F, async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            config = _resolve_config(ping_token)

            try:
                client = Client(config)
            except Exception:
                logger.warning(
                    "Failed to initialize Still200 monitoring", exc_info=True
                )
                return func(*args, **kwargs)

            run_token = None
            try:
                run = _report_safely(client.start)
                run_token = _set_current_run(run) if run is not None else None

                try:
                    result = func(*args, **kwargs)
                except Exception as error:
                    error_message = _error_message(error)
                    if run is not None:
                        _report_safely(
                            lambda: client.fail(run.id, error_message=error_message)
                        )
                    raise

                if run is not None:
                    _report_safely(lambda: client.finish(run.id))
                return result
            finally:
                if run_token is not None:
                    _reset_current_run(run_token)
                _report_safely(client.close)

        return cast(F, sync_wrapper)

    return decorator


def _resolve_config(ping_token: str | None) -> Config:
    if ping_token is None:
        return Config.from_env()

    return Config(ping_token=ping_token)


def _error_message(error: Exception) -> str:
    message = str(error) or type(error).__name__
    return message[:MAX_ERROR_MESSAGE_LENGTH]


def _report_safely[T](operation: Callable[[], T]) -> T | None:
    try:
        return operation()
    except Exception:
        logger.warning(
            "Failed to report scheduled job status to Still200", exc_info=True
        )
        return None


async def _report_safely_async[T](
    operation: Callable[[], Awaitable[T]],
) -> T | None:
    try:
        return await operation()
    except Exception:
        logger.warning(
            "Failed to report scheduled job status to Still200", exc_info=True
        )
        return None
