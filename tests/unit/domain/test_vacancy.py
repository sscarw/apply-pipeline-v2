from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

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
