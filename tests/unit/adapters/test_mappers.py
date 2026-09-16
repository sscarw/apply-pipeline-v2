from datetime import UTC, datetime

import pytest

from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.mappers import row_to_vacancy, vacancy_to_row
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.transitions import Source, VacancyStatus

PUBLISHED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _make_vacancy(
    *,
    external_id: str = "847958",
    location: str | None = None,
    salary_text: str | None = None,
) -> Vacancy:
    return Vacancy(
        source=Source.DJINNI,
        external_id=external_id,
        url="https://example.com/jobs/847958",
        title="Python Developer",
        company="Acme",
        description="Python backend vacancy",
        published_at=PUBLISHED_AT,
        location=location,
        salary_text=salary_text,
    )


def test_round_trip_with_history() -> None:
    vacancy = _make_vacancy()

    vacancy.change_status(
        VacancyStatus.JUDGED,
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        reason="Passed initial check",
    )
    vacancy.change_status(
        VacancyStatus.SHORTLISTED,
        now=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
        reason="Good match",
    )
    vacancy.change_status(
        VacancyStatus.APPLIED,
        now=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
        reason="Application sent",
    )

    row = vacancy_to_row(vacancy)
    result = row_to_vacancy(row)

    assert result == vacancy
    assert row.status == "applied"
    assert len(row.history) == 3


def test_round_trip_without_history() -> None:
    vacancy = _make_vacancy()

    row = vacancy_to_row(vacancy)
    result = row_to_vacancy(row)

    assert result == vacancy
    assert result.status == VacancyStatus.NEW
    assert result.history == []
    assert row.history == []


@pytest.mark.parametrize(
    ("location", "salary_text"),
    [
        ("Lviv", "$2000-$3000"),
        (None, None),
    ],
    ids=[
        "with-optional-fields",
        "without-optional-fields",
    ],
)
def test_optional_fields(
    location: str | None,
    salary_text: str | None,
) -> None:
    vacancy = _make_vacancy(
        location=location,
        salary_text=salary_text,
    )

    row = vacancy_to_row(vacancy)
    result = row_to_vacancy(row)

    assert result.location == location
    assert result.salary_text == salary_text


def test_unknown_status_raises() -> None:
    vacancy = _make_vacancy()

    row = vacancy_to_row(vacancy)
    row.status = "archived"

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_vacancy(row)

    error = exc_info.value

    assert error.field == "status"
    assert error.value == "archived"


def test_unknown_status_in_history_raises() -> None:
    vacancy = _make_vacancy()

    vacancy.change_status(
        VacancyStatus.JUDGED,
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        reason="Passed initial check",
    )

    row = vacancy_to_row(vacancy)
    row.history[0].to_status = "archived"

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_vacancy(row)

    error = exc_info.value

    assert error.table == "vacancy_status_changes"
    assert error.field == "to_status"
    assert error.value == "archived"


def test_unknown_source_raises() -> None:
    vacancy = _make_vacancy()

    row = vacancy_to_row(vacancy)
    row.source = "linkedin"

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_vacancy(row)

    error = exc_info.value

    assert error.field == "source"
    assert error.value == "linkedin"
