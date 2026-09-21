"""Settings shared by every test."""

import asyncio
from collections.abc import Callable, Mapping

import pytest


def pytest_asyncio_loop_factories(
    config: pytest.Config,
    item: pytest.Item,
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # Async psycopg cannot run on the ProactorEventLoop that Windows uses by default,
    # so async tests get the selector loop on every platform.
    return {"selector": asyncio.SelectorEventLoop}
