from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from apply_pipeline.domain.criteria import Criterion, CriterionResult, CriterionStatus, Priority
from apply_pipeline.domain.errors import ScoringError

WEIGHTS: Final[Mapping[Priority, int]] = MappingProxyType(
    {
        Priority.MUST: 3,
        Priority.IMPORTANT: 2,
        Priority.NICE: 1,
    }
)


@dataclass(frozen=True, slots=True)
class MatchScore:
    value: int
    blocked_by: tuple[str, ...]
    scored_count: int
    unknown_count: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ScoringError("Match score value must be between 0 and 100.")

        if self.blocked_by and self.value != 0:
            raise ScoringError("Blocked match score must have value 0.")

        if self.scored_count < 0:
            raise ScoringError("Scored count cannot be negative.")

        if self.unknown_count < 0:
            raise ScoringError("Unknown count cannot be negative.")

        if self.unknown_count > self.scored_count:
            raise ScoringError("Unknown count cannot be greater than scored count.")

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked_by)

    @property
    def is_low_confidence(self) -> bool:
        # More than half of the scored criteria are unknown; integers, like the score.
        return self.unknown_count * 2 > self.scored_count


def score_match(
    criteria: Sequence[Criterion],
    results: Sequence[CriterionResult],
) -> MatchScore:
    results_by_id: dict[str, CriterionResult] = {}

    for result in results:
        if result.criterion_id in results_by_id:
            raise ScoringError(f"Duplicate result for criterion '{result.criterion_id}'.")

        results_by_id[result.criterion_id] = result

    criterion_ids = {criterion.id for criterion in criteria}

    for criterion_id in results_by_id:
        if criterion_id not in criterion_ids:
            raise ScoringError(f"Result references unknown criterion '{criterion_id}'.")

    blocked_by: list[str] = []

    scored_count = 0
    unknown_count = 0

    earned_units = 0
    maximum_units = 0

    for criterion in criteria:
        # A criterion the judge skipped counts as unknown, never as met.
        found = results_by_id.get(criterion.id)
        status = CriterionStatus.UNKNOWN if found is None else found.status

        if criterion.priority == Priority.IGNORE:
            continue

        if criterion.priority == Priority.MUST and status == CriterionStatus.NOT_MET:
            blocked_by.append(criterion.id)

        if criterion.priority == Priority.EXCLUDE:
            if status == CriterionStatus.MET:
                blocked_by.append(criterion.id)

            continue

        weight = WEIGHTS[criterion.priority]

        scored_count += 1
        maximum_units += weight * 2

        if status == CriterionStatus.MET:
            earned_units += weight * 2

        elif status == CriterionStatus.UNKNOWN:
            earned_units += weight
            unknown_count += 1

    if scored_count == 0:
        raise ScoringError("Cannot calculate score without scoring criteria.")

    if blocked_by:
        return MatchScore(
            value=0,
            blocked_by=tuple(blocked_by),
            scored_count=scored_count,
            unknown_count=unknown_count,
        )

    value = (earned_units * 100 + maximum_units // 2) // maximum_units

    return MatchScore(
        value=value,
        blocked_by=(),
        scored_count=scored_count,
        unknown_count=unknown_count,
    )
