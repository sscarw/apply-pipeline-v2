import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.mappers import profile_to_row, row_to_profile
from apply_pipeline.domain.criteria import Criterion, Priority
from apply_pipeline.domain.profile import CandidateProfile, Currency, Salary, WorkFormat

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _make_profile(**overrides: Any) -> CandidateProfile:
    values: dict[str, Any] = {
        "user_id": USER_ID,
        "version": 3,
        "created_at": CREATED_AT,
        "desired_roles": ("Junior Python Developer", "AI Engineer"),
        "experience_years": 0,
        "skills": ("Python", "FastAPI", "LangGraph"),
        "work_formats": frozenset({WorkFormat.REMOTE, WorkFormat.OFFICE}),
        "criteria": (
            Criterion("python", "Основна мова роботи Python", Priority.MUST),
            Criterion("no_crypto", "Криптовалюти, Web3", Priority.EXCLUDE),
            Criterion("llm", "Робота з LLM і агентами", Priority.IMPORTANT),
        ),
        "city": "Львів",
        "min_salary": Salary(500, Currency.USD),
        **overrides,
    }
    return CandidateProfile(**values)


def test_round_trip() -> None:
    profile = _make_profile()

    assert row_to_profile(profile_to_row(profile)) == profile


def test_round_trip_without_optional_fields() -> None:
    profile = _make_profile(city=None, min_salary=None, work_formats=frozenset({WorkFormat.REMOTE}))

    assert row_to_profile(profile_to_row(profile)) == profile


def test_managed_fields_go_to_columns_not_json() -> None:
    row = profile_to_row(_make_profile())

    assert row.user_id == USER_ID
    assert row.version == 3
    assert row.created_at == CREATED_AT
    assert {"user_id", "version", "created_at"}.isdisjoint(row.data)


def test_document_is_plain_json() -> None:
    row = profile_to_row(_make_profile())

    # JSONB accepts only JSON types: this must not raise.
    encoded = json.dumps(row.data, ensure_ascii=False)

    assert '"priority": "must"' in encoded
    assert row.data["min_salary"] == {"amount": 500, "currency": "usd"}
    assert sorted(row.data["work_formats"]) == ["office", "remote"]
    assert row.data["criteria"][0] == {
        "id": "python",
        "text": "Основна мова роботи Python",
        "priority": "must",
    }


def test_loaded_profile_has_immutable_types() -> None:
    profile = row_to_profile(profile_to_row(_make_profile()))

    assert isinstance(profile.desired_roles, tuple)
    assert isinstance(profile.work_formats, frozenset)
    assert isinstance(profile.criteria, tuple)
    assert isinstance(profile.criteria[0], Criterion)
    assert profile.criteria[0].priority is Priority.MUST


def _corrupt(change: dict[str, Any]) -> CorruptedRowError:
    row = profile_to_row(_make_profile())
    row.id = 42
    row.data = {**row.data, **change}

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_profile(row)

    return exc_info.value


@pytest.mark.parametrize(
    "change",
    [
        {"criteria": [{"id": "python", "text": "Python", "priority": "MUST"}]},
        {"work_formats": ["remote", "moon"]},
        {"experience_years": "a lot"},
        {"desired_roles": None},
    ],
    ids=["unknown-priority", "unknown-work-format", "wrong-type", "missing-roles"],
)
def test_invalid_document_raises(change: dict[str, Any]) -> None:
    error = _corrupt(change)

    assert error.table == "candidate_profiles"
    assert error.row_id == 42
    assert error.field == "data"


@pytest.mark.parametrize(
    "change",
    [
        {"work_formats": ["office"], "city": None},
        {"experience_years": 99},
        {"criteria": [{"id": "no_crypto", "text": "Crypto", "priority": "exclude"}]},
    ],
    ids=["office-without-city", "experience-over-60", "no-scoring-criteria"],
)
def test_document_breaking_domain_rules_raises(change: dict[str, Any]) -> None:
    # A valid JSON shape is not enough: the domain rules run again on load.
    assert _corrupt(change).field == "data"
