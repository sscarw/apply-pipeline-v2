"""Settings shared by every test."""

import asyncio
import os
from collections.abc import Callable, Mapping

import pytest
from pydantic_ai import models

# Tests must never call a paid LLM API: any real model request fails loudly.
# Agents under test get TestModel or FunctionModel instead.
models.ALLOW_MODEL_REQUESTS = False
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


def pytest_asyncio_loop_factories(
    config: pytest.Config,
    item: pytest.Item,
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # Async psycopg cannot run on the ProactorEventLoop that Windows uses by default,
    # so async tests get the selector loop on every platform.
    return {"selector": asyncio.SelectorEventLoop}
