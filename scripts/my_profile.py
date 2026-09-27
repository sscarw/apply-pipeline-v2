"""The author's own search profile, used by the local scripts as real test data.

It replaces the old prompts/profile.md: stop factors 1-11 of judge_v1 became criteria.
Anything that is fine when a vacancy is silent about it (seniority, years, English
level, office) is an `exclude` criterion, so silence never lowers the score. Only what
must be present in the text is a `must`.
"""

from datetime import datetime
from uuid import UUID

from apply_pipeline.domain.criteria import Criterion, Priority
from apply_pipeline.domain.profile import CandidateProfile, Currency, Salary, WorkFormat

MY_CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        "python_core",
        "Основна мова щоденної роботи — Python, а не лише згадка серед інших мов.",
        Priority.MUST,
    ),
    Criterion(
        "writes_code",
        "Це інженерна роль, де людина щодня пише код: не дизайн, продажі, рекрутинг, "
        "менеджмент, підтримка, ручне тестування і не лише no-code інструменти "
        "(n8n, Zapier, Make).",
        Priority.MUST,
    ),
    Criterion(
        "senior_title",
        "У назві посади рівень Middle, Senior, Lead, Head, Principal, Staff або Architect "
        "без варіанту Junior, Trainee чи Intern.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "experience_3_plus",
        "Обов'язкова вимога: 3 роки комерційного досвіду або більше.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "english_c1",
        "Обов'язкова англійська рівня C1, C2, Advanced або Fluent.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "third_language",
        "Обов'язкове знання ще однієї мови, крім української та англійської "
        "(польська, німецька тощо).",
        Priority.EXCLUDE,
    ),
    Criterion(
        "office_elsewhere",
        "Робота лише з офісу в місті, відмінному від Львова, без віддаленої опції.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "bad_industry",
        "Компанія або продукт у сфері криптовалют, Web3, блокчейну, гемблінгу, беттінгу, "
        "adult або арбітражу трафіку.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "military_service",
        "Робота передбачає службу у військовому підрозділі або контракт зі ЗСУ.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "unpaid",
        "Стажування або робота без оплати.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "salary_below_min",
        "Зарплату вказано явно в доларах, і навіть її верхня межа нижча за $500 на місяць.",
        Priority.EXCLUDE,
    ),
    Criterion(
        "llm_agents",
        "Робота з LLM, AI-агентами, RAG або prompt engineering.",
        Priority.IMPORTANT,
    ),
    Criterion(
        "junior_friendly",
        "Вакансія прямо відкрита для junior, trainee, студентів або людей без досвіду.",
        Priority.IMPORTANT,
    ),
    Criterion(
        "stack_match",
        "У стеку є FastAPI, LangGraph, PostgreSQL або pgvector.",
        Priority.NICE,
    ),
)


def build_my_profile(user_id: UUID, *, now: datetime) -> CandidateProfile:
    return CandidateProfile(
        user_id=user_id,
        version=1,
        created_at=now,
        desired_roles=("Junior Python Developer", "Junior AI Engineer"),
        experience_years=0,
        skills=(
            "Python",
            "FastAPI",
            "Pydantic",
            "asyncio",
            "pytest",
            "LangGraph",
            "LangChain",
            "Pydantic AI",
            "OpenAI API",
            "Anthropic API",
            "RAG",
            "Qdrant",
            "pgvector",
            "PostgreSQL",
            "SQLAlchemy",
            "Alembic",
            "Docker",
            "GitHub Actions",
            "MCP",
        ),
        work_formats=frozenset({WorkFormat.REMOTE, WorkFormat.OFFICE}),
        criteria=MY_CRITERIA,
        city="Львів",
        min_salary=Salary(500, Currency.USD),
    )
