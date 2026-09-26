from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.tables import VacancyRow
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.transitions import MatchStatus, Source


def _parse_source(value: str, *, table: str, row_id: int | None, field: str) -> Source:
    try:
        return Source(value)
    except ValueError as error:
        raise CorruptedRowError(
            table=table,
            row_id=row_id,
            field=field,
            value=value,
        ) from error


def _parse_status(value: str, *, table: str, row_id: int | None, field: str) -> MatchStatus:
    try:
        return MatchStatus(value)
    except ValueError as error:
        raise CorruptedRowError(
            table=table,
            row_id=row_id,
            field=field,
            value=value,
        ) from error


def vacancy_to_row(vacancy: Vacancy) -> VacancyRow:
    row = VacancyRow(
        source=str(vacancy.source.value),
        external_id=vacancy.external_id,
        url=vacancy.url,
        title=vacancy.title,
        company=vacancy.company,
        description=vacancy.description,
        published_at=vacancy.published_at,
        location=vacancy.location,
        salary_text=vacancy.salary_text,
    )

    return row


def row_to_vacancy(row: VacancyRow) -> Vacancy:
    source = _parse_source(
        row.source,
        table="vacancies",
        row_id=row.id,
        field="source",
    )

    return Vacancy(
        source=source,
        external_id=row.external_id,
        url=row.url,
        title=row.title,
        company=row.company,
        description=row.description,
        published_at=row.published_at,
        location=row.location,
        salary_text=row.salary_text,
    )
