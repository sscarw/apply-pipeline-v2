"""Fixtures shared by the LLM judge tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from apply_pipeline.domain.criteria import Criterion, Priority
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.profile import CandidateProfile, Currency, Salary, WorkFormat
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


@pytest.fixture
def profile() -> CandidateProfile:
    """A small profile with one criterion of every kind, including an ignored one."""
    return CandidateProfile(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        version=3,
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        desired_roles=("Junior Python Developer", "AI Engineer"),
        experience_years=0,
        skills=("Python", "FastAPI"),
        work_formats=frozenset({WorkFormat.REMOTE, WorkFormat.OFFICE, WorkFormat.HYBRID}),
        criteria=(
            Criterion("python", "Основна мова роботи Python", Priority.MUST),
            Criterion("office_only", "Лише офіс, без віддаленої роботи", Priority.IGNORE),
            Criterion("no_crypto", "Компанія у сфері криптовалют", Priority.EXCLUDE),
            Criterion("llm", "Робота з LLM і агентами", Priority.IMPORTANT),
        ),
        city="Львів",
        min_salary=Salary(500, Currency.USD),
    )
