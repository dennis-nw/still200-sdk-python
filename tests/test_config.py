import pytest

from still200_sdk._config import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    PING_TOKEN_ENV_VAR,
    Config,
)


def test_config_has_production_defaults() -> None:
    config = Config(ping_token="secret")

    assert config.base_url == DEFAULT_BASE_URL
    assert config.timeout == DEFAULT_TIMEOUT


def test_config_removes_trailing_slash() -> None:
    config = Config(ping_token="secret", base_url="https://example.com/")

    assert config.base_url == "https://example.com"


def test_config_does_not_expose_ping_token_in_repr() -> None:
    config = Config(ping_token="super-secret")

    assert "super-secret" not in repr(config)


def test_config_loads_ping_token_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PING_TOKEN_ENV_VAR, "secret")

    config = Config.from_env()

    assert config.ping_token == "secret"


def test_config_requires_ping_token_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PING_TOKEN_ENV_VAR, raising=False)

    with pytest.raises(ValueError, match=f"{PING_TOKEN_ENV_VAR} is not set"):
        Config.from_env()


@pytest.mark.parametrize("ping_token", ["", " ", "\t"])
def test_config_rejects_empty_ping_token(ping_token: str) -> None:
    with pytest.raises(ValueError, match="ping_token must not be empty"):
        Config(ping_token=ping_token)


@pytest.mark.parametrize("base_url", ["", "/", "///"])
def test_config_rejects_empty_base_url(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url must not be empty"):
        Config(ping_token="secret", base_url=base_url)


@pytest.mark.parametrize("timeout", [0, -1])
def test_config_rejects_non_positive_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout must be greater than zero"):
        Config(ping_token="secret", timeout=timeout)
