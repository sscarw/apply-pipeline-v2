import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.mappers import decision_row_to_results, verdict_to_decision_row
from apply_pipeline.domain.criteria import CriterionResult, CriterionStatus
from apply_pipeline.domain.judge import JudgeFailure, JudgeUsage, JudgeVerdict

DECIDED_AT = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
VACANCY_HASH = "a" * 64

USAGE = JudgeUsage("gpt-4.1-mini", 2300, 180, 1024, Decimal("0.001700"))
RESULTS = (
    CriterionResult("python", CriterionStatus.MET, "Python 3.13, FastAPI"),
    CriterionResult("no_crypto", CriterionStatus.UNKNOWN),
    CriterionResult("remote", CriterionStatus.NOT_MET, "лише офіс у Києві"),
)

JUDGED = JudgeVerdict(RESULTS, "Python і LLM.", "judge_v2", USAGE, None, 1)
UNAVAILABLE = JudgeVerdict((), None, "judge_v2", None, JudgeFailure.UNAVAILABLE, 0)
INVALID_OUTPUT = JudgeVerdict((), None, "judge_v2", USAGE, JudgeFailure.INVALID_OUTPUT, 0)


def _row(verdict: JudgeVerdict) -> Any:
    return verdict_to_decision_row(
        verdict,
        match_id=11,
        profile_version=3,
        vacancy_hash=VACANCY_HASH,
        decided_at=DECIDED_AT,
    )


def test_judged_verdict_fills_every_column() -> None:
    row = _row(JUDGED)

    assert (row.match_id, row.profile_version, row.vacancy_hash) == (11, 3, VACANCY_HASH)
    assert row.prompt_version == "judge_v2"
    assert row.failure is None
    assert row.summary == "Python і LLM."
    assert row.discarded == 1
    assert row.model_name == "gpt-4.1-mini"
    assert (row.input_tokens, row.output_tokens, row.cache_read_tokens) == (2300, 180, 1024)
    assert row.cost_usd == Decimal("0.001700")
    assert row.decided_at == DECIDED_AT


def test_results_are_plain_json() -> None:
    row = _row(JUDGED)

    json.dumps(row.results, ensure_ascii=False)
    assert row.results == [
        {"criterion_id": "python", "status": "met", "evidence": "Python 3.13, FastAPI"},
        {"criterion_id": "no_crypto", "status": "unknown", "evidence": None},
        {"criterion_id": "remote", "status": "not_met", "evidence": "лише офіс у Києві"},
    ]


def test_unavailable_has_no_usage_columns() -> None:
    row = _row(UNAVAILABLE)

    assert row.failure == "unavailable"
    assert row.results == []
    assert row.summary is None
    columns = (row.model_name, row.input_tokens, row.output_tokens, row.cache_read_tokens)
    assert columns == (None, None, None, None)
    assert row.cost_usd is None


def test_invalid_output_keeps_what_was_paid() -> None:
    row = _row(INVALID_OUTPUT)

    assert row.failure == "invalid_output"
    assert row.results == []
    assert row.input_tokens == 2300
    assert row.cost_usd == Decimal("0.001700")


def test_results_round_trip() -> None:
    # This is what lets old decisions be rescored with new weights, without the LLM.
    assert decision_row_to_results(_row(JUDGED)) == RESULTS


def test_failed_decision_has_no_results() -> None:
    assert decision_row_to_results(_row(UNAVAILABLE)) == ()


@pytest.mark.parametrize(
    "results",
    [
        [{"criterion_id": "python", "status": "MET", "evidence": "Python"}],
        [{"criterion_id": "python", "status": "met", "evidence": None}],
        [{"criterion_id": "python", "status": "unknown", "evidence": "Python"}],
        [{"status": "met", "evidence": "Python"}],
        {"python": "met"},
    ],
    ids=["uppercase-status", "met-without-quote", "unknown-with-quote", "no-id", "not-a-list"],
)
def test_corrupted_results_raise(results: Any) -> None:
    row = _row(JUDGED)
    row.id = 5
    row.results = results

    with pytest.raises(CorruptedRowError) as exc_info:
        decision_row_to_results(row)

    assert (exc_info.value.table, exc_info.value.row_id, exc_info.value.field) == (
        "judge_decisions",
        5,
        "results",
    )
