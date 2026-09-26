from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from apply_pipeline.domain.criteria import Criterion
from apply_pipeline.domain.errors import InvalidProfileError
from apply_pipeline.domain.scoring import WEIGHTS


class WorkFormat(StrEnum):
    REMOTE = "remote"
    OFFICE = "office"
    HYBRID = "hybrid"


class Currency(StrEnum):
    UAH = "uah"
    USD = "usd"
    EUR = "eur"


@dataclass(frozen=True, slots=True)
class Salary:
    amount: int
    currency: Currency

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise InvalidProfileError("Salary amount must be greater than zero.")


MAX_CRITERIA: Final[int] = 30


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    user_id: UUID
    version: int
    created_at: datetime
    desired_roles: tuple[str, ...]
    experience_years: int
    skills: tuple[str, ...]
    work_formats: frozenset[WorkFormat]
    criteria: tuple[Criterion, ...]
    city: str | None = None
    min_salary: Salary | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidProfileError("Profile version must be at least 1.")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidProfileError("Profile created_at must be timezone-aware.")

        if not self.desired_roles:
            raise InvalidProfileError("Profile must contain at least one desired role.")

        if any(not role.strip() for role in self.desired_roles):
            raise InvalidProfileError("Desired roles cannot contain empty values.")

        if not 0 <= self.experience_years <= 60:
            raise InvalidProfileError("Experience years must be between 0 and 60.")

        if not self.work_formats:
            raise InvalidProfileError("Profile must contain at least one work format.")

        requires_city = (
            WorkFormat.OFFICE in self.work_formats or WorkFormat.HYBRID in self.work_formats
        )

        if requires_city and (self.city is None or not self.city.strip()):
            raise InvalidProfileError("City is required for office or hybrid work.")

        if len(self.criteria) > MAX_CRITERIA:
            raise InvalidProfileError(f"Profile cannot contain more than {MAX_CRITERIA} criteria.")

        criterion_ids = tuple(criterion.id for criterion in self.criteria)

        if len(criterion_ids) != len(set(criterion_ids)):
            raise InvalidProfileError("Criterion ids must be unique.")

        # A priority takes part in scoring exactly when it has a weight.
        if not any(criterion.priority in WEIGHTS for criterion in self.criteria):
            raise InvalidProfileError("Profile must contain at least one scoring criterion.")

    def revise(
        self,
        *,
        now: datetime,
        **changes: Any,
    ) -> CandidateProfile:
        protected_fields = {
            "user_id",
            "version",
            "created_at",
        }

        if protected_fields.intersection(changes):
            raise InvalidProfileError("user_id, version and created_at cannot be changed directly.")

        return replace(
            self,
            **changes,
            version=self.version + 1,
            created_at=now,
        )
