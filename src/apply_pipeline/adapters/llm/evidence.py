from collections.abc import Collection, Sequence
from dataclasses import dataclass

from apply_pipeline.adapters.llm.schemas import CriterionAnswer
from apply_pipeline.domain.criteria import CriterionResult, CriterionStatus


@dataclass(frozen=True, slots=True)
class CheckedAnswers:
    results: tuple[CriterionResult, ...]
    discarded: int


def normalize_for_search(text: str) -> str:
    return " ".join(text.casefold().split())


def check_answers(
    answers: Sequence[CriterionAnswer],
    *,
    criterion_ids: Collection[str],
    vacancy_text: str,
) -> CheckedAnswers:
    normalized_vacancy = normalize_for_search(vacancy_text)

    results: list[CriterionResult] = []
    seen_ids: set[str] = set()
    discarded = 0

    for answer in answers:
        criterion_id = answer.criterion_id

        if criterion_id not in criterion_ids:
            discarded += 1
            continue

        if criterion_id in seen_ids:
            discarded += 1
            continue

        seen_ids.add(criterion_id)

        if answer.status == CriterionStatus.UNKNOWN:
            results.append(
                CriterionResult(
                    criterion_id=criterion_id,
                    status=CriterionStatus.UNKNOWN,
                    evidence=None,
                )
            )
            continue

        evidence = answer.evidence

        if evidence is not None:
            evidence = evidence.strip().strip("'\"«»„“”").strip()

        if not evidence or normalize_for_search(evidence) not in normalized_vacancy:
            results.append(
                CriterionResult(
                    criterion_id=criterion_id,
                    status=CriterionStatus.UNKNOWN,
                    evidence=None,
                )
            )
            discarded += 1
            continue

        results.append(
            CriterionResult(
                criterion_id=criterion_id,
                status=answer.status,
                evidence=evidence,
            )
        )

    return CheckedAnswers(
        results=tuple(results),
        discarded=discarded,
    )
