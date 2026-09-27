import hashlib
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from apply_pipeline.domain.errors import InvalidVacancyError
from apply_pipeline.domain.models import Vacancy, make_vacancy_key, split_vacancy_key
from apply_pipeline.domain.transitions import Source

PUBLISHED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _make_vacancy(
    *,
    external_id: str = "847958",
    title: str = "Python Developer",
    company: str = "Acme",
    url: str = "https://example.com/jobs/847958",
    published_at: datetime = PUBLISHED_AT,
) -> Vacancy:
    return Vacancy(
        source=Source.DJINNI,
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        description="Python backend vacancy",
        published_at=published_at,
    )


@pytest.fixture
def vacancy() -> Vacancy:
    return _make_vacancy()


INVALID_VACANCIES: list[Callable[[], Vacancy]] = [
    lambda: _make_vacancy(external_id=""),
    lambda: _make_vacancy(title=""),
    lambda: _make_vacancy(title="   "),
    lambda: _make_vacancy(company=""),
    lambda: _make_vacancy(url="example.com/jobs/847958"),
    lambda: _make_vacancy(
        published_at=datetime(2026, 9, 1, 12, 0),
    ),
]

INVALID_VACANCY_IDS = [
    "empty-external-id",
    "empty-title",
    "whitespace-title",
    "empty-company",
    "url-without-scheme",
    "naive-published-at",
]


@pytest.mark.parametrize(
    "factory",
    INVALID_VACANCIES,
    ids=INVALID_VACANCY_IDS,
)
def test_invalid_vacancy_data_raises_error(
    factory: Callable[[], Vacancy],
) -> None:
    with pytest.raises(InvalidVacancyError):
        factory()


def test_vacancy_has_no_status() -> None:
    # Status belongs to a user's match, not to the shared vacancy catalog.
    field_names = set(Vacancy.__dataclass_fields__)

    assert "status" not in field_names
    assert "history" not in field_names


def test_key(vacancy: Vacancy) -> None:
    assert vacancy.key == "djinni:847958"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (
            PUBLISHED_AT,
            0,
        ),
        (
            PUBLISHED_AT + timedelta(days=45),
            45,
        ),
        (
            PUBLISHED_AT + timedelta(days=45, hours=23),
            45,
        ),
        (
            datetime(
                2026,
                10,
                16,
                7,
                0,
                tzinfo=timezone(timedelta(hours=-5)),
            ),
            45,
        ),
    ],
    ids=[
        "zero-days",
        "exactly-45-days",
        "45-days-plus-23-hours",
        "45-days-different-timezone",
    ],
)
def test_age_days(
    vacancy: Vacancy,
    now: datetime,
    expected: int,
) -> None:
    assert vacancy.age_days(now) == expected


def test_key_is_built_by_make_vacancy_key(vacancy: Vacancy) -> None:
    assert vacancy.key == make_vacancy_key(Source.DJINNI, "847958")


@pytest.mark.parametrize("source", list(Source))
def test_split_reverses_make(source: Source) -> None:
    key = make_vacancy_key(source, "847958")

    assert split_vacancy_key(key) == (source, "847958")


def test_split_keeps_colons_inside_external_id() -> None:
    assert split_vacancy_key("dou:a:b:c") == (Source.DOU, "a:b:c")


@pytest.mark.parametrize(
    "key",
    ["", "djinni", "djinni847958", "djinni:", "djinni:  ", ":847958", "linkedin:1", "Djinni:1"],
    ids=[
        "empty",
        "no-colon",
        "no-colon-digits",
        "empty-external-id",
        "blank-external-id",
        "empty-source",
        "unknown-source",
        "source-is-case-sensitive",
    ],
)
def test_split_invalid_key_raises(key: str) -> None:
    with pytest.raises(InvalidVacancyError):
        split_vacancy_key(key)


def test_split_unknown_source_keeps_cause() -> None:
    with pytest.raises(InvalidVacancyError) as exc_info:
        split_vacancy_key("linkedin:1")

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_content_hash_is_sha256_of_joined_fields() -> None:
    vacancy = _make_vacancy()
    expected_content = "\x1f".join(
        ["Python Developer", "Acme", "", "", "Python backend vacancy"],
    )

    assert vacancy.content_hash == hashlib.sha256(expected_content.encode()).hexdigest()
    assert len(vacancy.content_hash) == 64


def test_content_hash_ignores_whitespace_changes() -> None:
    original = _make_vacancy()
    reformatted = replace(
        original,
        title="  Python   Developer ",
        description="Python\n\nbackend\tvacancy\n",
    )

    assert reformatted.content_hash == original.content_hash


@pytest.mark.parametrize(
    "change",
    [
        {"title": "Senior Python Developer"},
        {"company": "Other"},
        {"location": "Kyiv"},
        {"salary_text": "$2000"},
        {"description": "Java backend vacancy"},
    ],
    ids=["title", "company", "location", "salary", "description"],
)
def test_content_hash_changes_with_job_fields(change: dict[str, Any]) -> None:
    original = _make_vacancy()

    assert replace(original, **change).content_hash != original.content_hash


@pytest.mark.parametrize(
    "change",
    [
        {"url": "https://example.com/jobs/other"},
        {"external_id": "999"},
        {"published_at": PUBLISHED_AT + timedelta(days=3)},
    ],
    ids=["url", "external-id", "republished"],
)
def test_content_hash_ignores_where_and_when(change: dict[str, Any]) -> None:
    # A vacancy republished with the same text must not be paid for again.
    original = _make_vacancy()

    assert replace(original, **change).content_hash == original.content_hash


def test_content_hash_keeps_field_borders() -> None:
    first = replace(_make_vacancy(), title="Python Dev", company="eloper Acme")
    second = replace(_make_vacancy(), title="Python Developer", company="Acme")

    assert first.content_hash != second.content_hash


def test_missing_and_empty_optional_fields_hash_the_same() -> None:
    assert (
        replace(_make_vacancy(), location=None).content_hash
        == replace(_make_vacancy(), location="").content_hash
    )
