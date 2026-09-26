"""Domain objects for the repository integration tests."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.domain.criteria import Criterion, Priority
from apply_pipeline.domain.match import Match
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.profile import CandidateProfile, WorkFormat
from apply_pipeline.domain.transitions import Source
from apply_pipeline.domain.user import User

CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def make_vacancy(external_id: str = "847958", **overrides: Any) -> Vacancy:
    values: dict[str, Any] = {
        "source": Source.DJINNI,
        "external_id": external_id,
        "url": f"https://djinni.co/jobs/{external_id}/",
        "title": "Python Engineer",
        "company": "Broscorp",
        "description": "Build LLM agents in Python.",
        "published_at": CREATED_AT,
        "location": "Remote, UA",
        "salary_text": "$1000-1500",
        **overrides,
    }
    return Vacancy(**values)


def make_user(email: str = "andrii@example.com", **overrides: Any) -> User:
    values: dict[str, Any] = {"id": uuid4(), "email": email, "created_at": CREATED_AT, **overrides}
    return User(**values)


def make_profile(user_id: UUID, **overrides: Any) -> CandidateProfile:
    values: dict[str, Any] = {
        "user_id": user_id,
        "version": 1,
        "created_at": CREATED_AT,
        "desired_roles": ("Junior Python Developer",),
        "experience_years": 0,
        "skills": ("Python", "FastAPI"),
        "work_formats": frozenset({WorkFormat.REMOTE}),
        "criteria": (
            Criterion("python", "Основна мова роботи Python", Priority.MUST),
            Criterion("no_crypto", "Криптовалюти, Web3", Priority.EXCLUDE),
        ),
        **overrides,
    }
    return CandidateProfile(**values)


def make_match(user_id: UUID, vacancy_key: str = "djinni:847958", **overrides: Any) -> Match:
    values: dict[str, Any] = {
        "user_id": user_id,
        "vacancy_key": vacancy_key,
        "created_at": CREATED_AT,
        **overrides,
    }
    return Match(**values)


async def reload(session: AsyncSession) -> None:
    """Send pending changes and forget loaded objects, so the next read hits the database."""
    await session.flush()
    session.expunge_all()


AddVacancies = Callable[..., Awaitable[list[str]]]
