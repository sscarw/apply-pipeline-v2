from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.tables import StatusChangeRow, VacancyRow
from apply_pipeline.domain.models import StatusChange, Vacancy
from apply_pipeline.domain.transitions import Source, VacancyStatus


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


def _parse_status(value: str, *, table: str, row_id: int | None, field: str) -> VacancyStatus:
    try:
        return VacancyStatus(value)
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
        status=str(vacancy.status.value),
    )

    row.history = [
        StatusChangeRow(
            from_status=str(change.from_status.value),
            to_status=str(change.to_status.value),
            changed_at=change.changed_at,
            reason=change.reason,
        )
        for change in vacancy.history
    ]

    return row


def row_to_vacancy(row: VacancyRow) -> Vacancy:
    source = _parse_source(
        row.source,
        table="vacancies",
        row_id=row.id,
        field="source",
    )

    status = _parse_status(
        row.status,
        table="vacancies",
        row_id=row.id,
        field="status",
    )

    history = [
        StatusChange(
            from_status=_parse_status(
                history_row.from_status,
                table="vacancy_status_changes",
                row_id=history_row.id,
                field="from_status",
            ),
            to_status=_parse_status(
                history_row.to_status,
                table="vacancy_status_changes",
                row_id=history_row.id,
                field="to_status",
            ),
            changed_at=history_row.changed_at,
            reason=history_row.reason,
        )
        for history_row in row.history
    ]

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
        status=status,
        history=history,
    )
