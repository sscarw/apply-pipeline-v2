from dataclasses import dataclass
from enum import StrEnum

from apply_pipeline.domain.errors import InvalidProfileError, ScoringError


class Priority(StrEnum):
    MUST = "must"
    IMPORTANT = "important"
    NICE = "nice"
    EXCLUDE = "exclude"
    IGNORE = "ignore"


class CriterionStatus(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Criterion:
    id: str
    text: str
    priority: Priority

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidProfileError("Criterion id cannot be empty.")

        if len(self.id) > 64:
            raise InvalidProfileError("Criterion id cannot be longer than 64 characters.")

        if any(char.isspace() for char in self.id):
            raise InvalidProfileError("Criterion id cannot contain whitespace.")

        if not self.text.strip():
            raise InvalidProfileError("Criterion text cannot be empty.")

        if len(self.text) > 300:
            raise InvalidProfileError("Criterion text cannot be longer than 300 characters.")


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_id: str
    status: CriterionStatus
    evidence: str | None = None

    def __post_init__(self) -> None:
        has_evidence = self.evidence is not None and bool(self.evidence.strip())

        if self.status != CriterionStatus.UNKNOWN and not has_evidence:
            raise ScoringError("Evidence is required when criterion status is MET or NOT_MET.")

        if self.status == CriterionStatus.UNKNOWN and self.evidence is not None:
            raise ScoringError("Evidence must be None when criterion status is UNKNOWN.")
