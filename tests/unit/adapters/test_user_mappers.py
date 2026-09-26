from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.mappers import row_to_user, user_to_row
from apply_pipeline.domain.user import Language, User

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _make_user() -> User:
    return User(
        id=USER_ID,
        email="Andrii@Example.com",
        created_at=CREATED_AT,
        language=Language.EN,
        monthly_budget_usd=Decimal("2.50"),
        is_active=False,
    )


def test_round_trip() -> None:
    user = _make_user()

    assert row_to_user(user_to_row(user)) == user


def test_row_holds_plain_values() -> None:
    row = user_to_row(_make_user())

    assert row.id == USER_ID
    assert row.email == "andrii@example.com"
    assert row.language == "en"
    assert row.monthly_budget_usd == Decimal("2.50")
    assert row.is_active is False
    assert row.created_at == CREATED_AT


def test_unknown_language_raises_with_user_id() -> None:
    row = user_to_row(_make_user())
    row.language = "de"

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_user(row)

    error = exc_info.value

    assert error.table == "users"
    assert error.row_id == USER_ID
    assert error.field == "language"
    assert error.value == "de"
