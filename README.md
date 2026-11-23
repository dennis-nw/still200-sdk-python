# Still200 Python SDK

Monitor Python scheduled jobs with [Still200](https://still200.com) using a
decorator, without writing repetitive monitoring boilerplate.

```python
from still200_sdk import monitor


@monitor()
async def generate_report() -> None:
    ...
```

When the function runs, the SDK reports when the job starts and whether it
finishes successfully or fails.

## Installation

Using uv:

```bash
uv add still200-sdk
```

Or using pip:

```bash
pip install still200-sdk
```

The SDK requires Python 3.12 or later.

## Configuration

Still200 generates a unique ping token when you create a scheduled-job monitor.
Set that token in the job's environment:

```bash
export STILL200_PING_TOKEN="your-ping-token"
```

Keep this token secret. Do not commit it to source control or include it
directly in your script.

If `STILL200_PING_TOKEN` is missing, the decorated function raises a
configuration error before the job starts. This prevents a job from silently
running without monitoring.

The SDK supports both asynchronous and synchronous functions.

## Async jobs

```python
import asyncio

from still200_sdk import monitor


@monitor()
async def generate_report() -> None:
    # Run the scheduled task.
    ...


if __name__ == "__main__":
    asyncio.run(generate_report())
```

## Synchronous jobs

```python
from still200_sdk import monitor


@monitor()
def clean_expired_sessions() -> None:
    # Run the scheduled task.
    ...


if __name__ == "__main__":
    clean_expired_sessions()
```

The decorator preserves the function's arguments, return value, and original
exception behavior.

## Accessing the current run

Still200 assigns a unique ID to each invocation. The SDK manages that ID
automatically and includes it in finish or failure pings. If your job needs the
ID for logs, traces, or its own records, access the current run inside the
decorated function:

```python
from still200_sdk import get_current_run, monitor


@monitor()
async def generate_report() -> None:
    run = get_current_run()
    print(f"Still200 run: {run.id}")
```

For the ID alone, use `get_current_run_id()`. Calling either accessor outside
an active monitored invocation raises `NoActiveRunError`.

## Multiple scheduled jobs

For separate scripts or processes, give each process its own value for
`STILL200_PING_TOKEN`:

```bash
STILL200_PING_TOKEN="report-token" python report_job.py
STILL200_PING_TOKEN="cleanup-token" python cleanup_job.py
```

If multiple monitored jobs run in the same process, load separate secrets and
pass them explicitly:

```python
import os

from still200_sdk import monitor


@monitor(ping_token=os.environ["REPORT_JOB_PING_TOKEN"])
def generate_report() -> None:
    ...


@monitor(ping_token=os.environ["CLEANUP_JOB_PING_TOKEN"])
def clean_expired_sessions() -> None:
    ...
```

An explicit `ping_token` takes precedence over `STILL200_PING_TOKEN`.

## Runtime behavior

For each invocation, the SDK sends:

1. A start ping before running the function and captures the run ID returned by
   Still200.
2. A finish ping for that run if the function returns successfully.
3. A failure ping for that run if the function raises an exception.

Failure pings include the exception message, limited to 2,000 characters. The
SDK does not automatically send function arguments because they may contain
sensitive data.

Still200 reporting errors are logged but do not change the job's behavior:

- If a start ping fails, the job still runs.
- If Still200 does not return a valid run ID, the job still runs but the SDK
  cannot send a correlated finish or failure ping.
- If a finish ping fails, the job's result is still returned.
- If a failure ping fails, the job's original exception is still raised.

## Development

Clone this repo and install the project and development dependencies:

```bash
uv sync --dev
```

Run the tests and lint checks:

```bash
uv run pytest
uv run ruff check src tests
```
