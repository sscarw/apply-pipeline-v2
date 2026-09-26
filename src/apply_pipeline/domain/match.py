from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from apply_pipeline.domain.errors import InvalidMatchError, InvalidTransitionError
from apply_pipeline.domain.scoring import MatchScore
from apply_pipeline.domain.transitions import MatchStatus, can_transition


@dataclass(frozen=True, slots=True)
class StatusChange:
    from_status: MatchStatus
    to_status: MatchStatus
    changed_at: datetime
    reason: str | None = None


@dataclass(slots=True)
class Match:
    user_id: UUID
    vacancy_key: str
    created_at: datetime
    status: MatchStatus = MatchStatus.NEW
    history: list[StatusChange] = field(default_factory=list)
    score: MatchScore | None = None
    profile_version: int | None = None

    def __post_init__(self) -> None:
        if not self.vacancy_key.strip():
            raise InvalidMatchError("Vacancy key cannot be empty.")

        if ":" not in self.vacancy_key:
            raise InvalidMatchError("Vacancy key must contain ':'.")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidMatchError("created_at must be timezone-aware.")

    def change_status(
        self,
        new_status: MatchStatus,
        *,
        now: datetime,
        reason: str | None = None,
    ) -> None:
        if not can_transition(self.status, new_status):
            raise InvalidTransitionError(
                self.status,
                new_status,
            )

        if now.tzinfo is None or now.utcoffset() is None:
            raise InvalidMatchError("now must be timezone-aware.")

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

    def record_score(
        self,
        score: MatchScore,
        *,
        profile_version: int,
        now: datetime,
    ) -> None:
        if profile_version < 1:
            raise InvalidMatchError("Profile version must be at least 1.")

        if score.is_blocked:
            new_status = MatchStatus.FILTERED_OUT
            reason = f"blocked by: {', '.join(score.blocked_by)}"
        else:
            new_status = MatchStatus.JUDGED
            reason = f"score {score.value}"

        self.change_status(
            new_status,
            now=now,
            reason=reason,
        )

        self.score = score
        self.profile_version = profile_version
