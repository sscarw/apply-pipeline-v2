from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.tables import (
    CandidateProfileRow,
    MatchRow,
    MatchStatusChangeRow,
    UserRow,
    VacancyRow,
)
from apply_pipeline.domain.errors import InvalidProfileError, ScoringError
from apply_pipeline.domain.match import Match, StatusChange
from apply_pipeline.domain.models import Vacancy, make_vacancy_key
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.scoring import MatchScore
from apply_pipeline.domain.transitions import MatchStatus, Source
from apply_pipeline.domain.user import Language, User

PROFILE_ADAPTER: Final[TypeAdapter[CandidateProfile]] = TypeAdapter(CandidateProfile)

PROFILE_STORAGE_FIELDS: Final[set[str]] = {
    "user_id",
    "version",
    "created_at",
}


def _parse_enum[E: StrEnum](
    enum_type: type[E],
    value: str,
    *,
    table: str,
    row_id: int | UUID | None,
    field: str,
) -> E:
    try:
        return enum_type(value)
    except ValueError as error:
        raise CorruptedRowError(
            table=table,
            row_id=row_id,
            field=field,
            value=value,
        ) from error


def vacancy_to_row(vacancy: Vacancy) -> VacancyRow:
    return VacancyRow(
        source=vacancy.source.value,
        external_id=vacancy.external_id,
        url=vacancy.url,
        title=vacancy.title,
        company=vacancy.company,
        description=vacancy.description,
        published_at=vacancy.published_at,
        location=vacancy.location,
        salary_text=vacancy.salary_text,
    )


def row_to_vacancy(row: VacancyRow) -> Vacancy:
    source = _parse_enum(
        Source,
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


def user_to_row(user: User) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email,
        language=user.language.value,
        monthly_budget_usd=user.monthly_budget_usd,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def row_to_user(row: UserRow) -> User:
    language = _parse_enum(
        Language,
        row.language,
        table="users",
        row_id=row.id,
        field="language",
    )

    return User(
        id=row.id,
        email=row.email,
        created_at=row.created_at,
        language=language,
        monthly_budget_usd=row.monthly_budget_usd,
        is_active=row.is_active,
    )


def profile_to_row(
    profile: CandidateProfile,
) -> CandidateProfileRow:
    data = PROFILE_ADAPTER.dump_python(
        profile,
        mode="json",
        exclude=PROFILE_STORAGE_FIELDS,
    )

    return CandidateProfileRow(
        user_id=profile.user_id,
        version=profile.version,
        created_at=profile.created_at,
        data=data,
    )


def row_to_profile(
    row: CandidateProfileRow,
) -> CandidateProfile:
    document: dict[str, Any] = {
        **row.data,
        "user_id": row.user_id,
        "version": row.version,
        "created_at": row.created_at,
    }

    try:
        return PROFILE_ADAPTER.validate_python(document)
    except (ValidationError, InvalidProfileError) as error:
        raise CorruptedRowError(
            table="candidate_profiles",
            row_id=row.id,
            field="data",
            value=row.data,
        ) from error


def row_to_match(row: MatchRow) -> Match:
    vacancy_source = _parse_enum(
        Source,
        row.vacancy.source,
        table="vacancies",
        row_id=row.vacancy.id,
        field="source",
    )

    vacancy_key = make_vacancy_key(
        vacancy_source,
        row.vacancy.external_id,
    )

    status = _parse_enum(
        MatchStatus,
        row.status,
        table="matches",
        row_id=row.id,
        field="status",
    )

    history = [
        StatusChange(
            from_status=_parse_enum(
                MatchStatus,
                change.from_status,
                table="match_status_changes",
                row_id=change.id,
                field="from_status",
            ),
            to_status=_parse_enum(
                MatchStatus,
                change.to_status,
                table="match_status_changes",
                row_id=change.id,
                field="to_status",
            ),
            changed_at=change.changed_at,
            reason=change.reason,
        )
        for change in row.history
    ]

    score: MatchScore | None = None

    if row.score_value is not None:
        score_columns = {
            "value": row.score_value,
            "blocked_by": row.blocked_by,
            "scored_count": row.scored_count,
            "unknown_count": row.unknown_count,
        }

        if row.blocked_by is None or row.scored_count is None or row.unknown_count is None:
            raise CorruptedRowError(
                table="matches",
                row_id=row.id,
                field="score",
                value=score_columns,
            )

        try:
            score = MatchScore(
                value=row.score_value,
                blocked_by=tuple(row.blocked_by),
                scored_count=row.scored_count,
                unknown_count=row.unknown_count,
            )
        except ScoringError as error:
            raise CorruptedRowError(
                table="matches",
                row_id=row.id,
                field="score",
                value=score_columns,
            ) from error

    return Match(
        user_id=row.user_id,
        vacancy_key=vacancy_key,
        created_at=row.created_at,
        status=status,
        history=history,
        score=score,
        profile_version=row.profile_version,
    )


def _status_change_to_row(
    change: StatusChange,
) -> MatchStatusChangeRow:
    return MatchStatusChangeRow(
        from_status=change.from_status.value,
        to_status=change.to_status.value,
        changed_at=change.changed_at,
        reason=change.reason,
    )


def apply_match_to_row(
    match: Match,
    row: MatchRow,
) -> None:
    row.status = match.status.value
    row.profile_version = match.profile_version

    if match.score is None:
        row.score_value = None
        row.blocked_by = None
        row.scored_count = None
        row.unknown_count = None
    else:
        row.score_value = match.score.value
        row.blocked_by = list(match.score.blocked_by)
        row.scored_count = match.score.scored_count
        row.unknown_count = match.score.unknown_count

    saved_history_count = len(row.history)

    for change in match.history[saved_history_count:]:
        row.history.append(_status_change_to_row(change))
