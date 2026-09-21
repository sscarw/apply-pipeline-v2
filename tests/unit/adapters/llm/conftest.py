"""Fixtures shared by the LLM judge tests."""

from datetime import UTC, datetime

import pytest

from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.transitions import Source


@pytest.fixture
def vacancy() -> Vacancy:
    """A complete vacancy; tests change single fields with dataclasses.replace."""
    return Vacancy(
        source=Source.DJINNI,
        external_id="847958",
        url="https://djinni.co/jobs/847958-python-engineer/",
        title="Python Engineer",
        company="Broscorp",
        description="Build LLM agents in Python with FastAPI and LangGraph.",
        published_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        location="Remote, UA",
        salary_text="$1000-1500",
    )
