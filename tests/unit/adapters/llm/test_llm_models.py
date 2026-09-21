from typing import Any

import pytest
from pydantic import SecretStr
from pydantic_ai.models.fallback import FallbackModel

from apply_pipeline.adapters.llm.models import build_judge_model
from apply_pipeline.config import Settings


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql+psycopg://user:password@127.0.0.1:5433/db",
        "redis_url": "redis://127.0.0.1:6379/0",
        "openai_api_key": SecretStr("sk-test"),
        "anthropic_api_key": None,
        **overrides,
    }
    # _env_file=None keeps the developer's real .env out of the test.
    return Settings(_env_file=None, **values)


def _model_names(model: FallbackModel) -> list[str]:
    return [inner.model_name for inner in model.models]


def test_openai_only_builds_primary_and_fallback() -> None:
    model = build_judge_model(_settings())

    assert isinstance(model, FallbackModel)
    assert _model_names(model) == ["gpt-4.1-mini", "gpt-4o-mini"]


def test_anthropic_key_adds_third_model() -> None:
    model = build_judge_model(_settings(anthropic_api_key=SecretStr("sk-ant-test")))

    assert isinstance(model, FallbackModel)
    assert _model_names(model) == ["gpt-4.1-mini", "gpt-4o-mini", "claude-haiku-4-5-20251001"]


def test_model_names_come_from_settings() -> None:
    settings = _settings(openai_model="gpt-5-mini", openai_fallback_model="gpt-4.1-nano")

    model = build_judge_model(settings)

    assert isinstance(model, FallbackModel)
    assert _model_names(model) == ["gpt-5-mini", "gpt-4.1-nano"]


def test_missing_openai_key_raises() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_judge_model(_settings(openai_api_key=None))


def test_empty_env_key_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@127.0.0.1:5433/db")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key is None
