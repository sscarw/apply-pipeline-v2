from dataclasses import dataclass, field
from datetime import datetime

from apply_pipeline.domain.errors import (
    InvalidTransitionError,
    InvalidVacancyError,
)
from apply_pipeline.domain.transitions import (
    Source,
    VacancyStatus,
    can_transition,
)


@dataclass(frozen=True, slots=True)
class StatusChange:
    from_status: VacancyStatus
    to_status: VacancyStatus
    changed_at: datetime
    reason: str | None = None


@dataclass(slots=True)
class Vacancy:
    source: Source
    external_id: str
    url: str
    title: str
    company: str
    description: str
    published_at: datetime
    location: str | None = None
    salary_text: str | None = None
    status: VacancyStatus = VacancyStatus.NEW
    history: list[StatusChange] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise InvalidVacancyError("external_id cannot be empty")

        if not self.title.strip():
            raise InvalidVacancyError("title cannot be empty")

        if not self.company.strip():
            raise InvalidVacancyError("company cannot be empty")

        if not self.url.startswith(("http://", "https://")):
            raise InvalidVacancyError("url must start with http:// or https://")

        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise InvalidVacancyError("published_at must be timezone-aware")

    @property
    def key(self) -> str:
        return f"{self.source.value}:{self.external_id}"

    def change_status(
        self,
        new_status: VacancyStatus,
        *,
        now: datetime,
        reason: str | None = None,
    ) -> None:
        if not can_transition(self.status, new_status):
            raise InvalidTransitionError(self.status, new_status)

        if now.tzinfo is None or now.utcoffset() is None:
            raise InvalidVacancyError("now must be timezone-aware")

        old_status = self.status

        self.status = new_status
        self.history.append(
            StatusChange(
                from_status=old_status,
                to_status=new_status,
                changed_at=now,
                reason=reason,
            )
        )

    def age_days(self, now: datetime) -> int:
        return (now - self.published_at).days
