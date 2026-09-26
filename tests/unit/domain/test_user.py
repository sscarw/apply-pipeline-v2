from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from apply_pipeline.domain.errors import InvalidUserError
from apply_pipeline.domain.user import Language, User

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _make_user(
    *,
    email: str = "andrii@example.com",
    created_at: datetime = CREATED_AT,
    monthly_budget_usd: Decimal = Decimal("1.00"),
) -> User:
    return User(
        id=USER_ID,
        email=email,
        created_at=created_at,
        monthly_budget_usd=monthly_budget_usd,
    )


def test_defaults() -> None:
    user = User(id=USER_ID, email="andrii@example.com", created_at=CREATED_AT)

    assert user.language == Language.UK
    assert user.language.value == "uk"
    assert user.monthly_budget_usd == Decimal("1.00")
    assert user.is_active is True


def test_language_values_are_locale_codes() -> None:
    # "uk" is the ISO 639-1 code for Ukrainian (not the United Kingdom); Babel uses it.
    assert [language.value for language in Language] == ["uk", "en"]


@pytest.mark.parametrize(
    "raw_email",
    ["Andrii@Example.COM", "  andrii@example.com  ", "\tANDRII@example.com\n"],
    ids=["mixed-case", "spaces", "tabs-and-newline"],
)
def test_email_is_normalized(raw_email: str) -> None:
    assert _make_user(email=raw_email).email == "andrii@example.com"


@pytest.mark.parametrize(
    "email",
    [
        "",
        "   ",
        "andrii.example.com",
        "andrii@@example.com",
        "a@b@example.com",
        "@example.com",
        "andrii@",
    ],
    ids=[
        "empty",
        "whitespace",
        "no-at",
        "double-at",
        "two-ats",
        "empty-local-part",
        "empty-domain",
    ],
)
def test_invalid_email_raises_error(email: str) -> None:
    with pytest.raises(InvalidUserError):
        _make_user(email=email)


def test_zero_budget_is_allowed() -> None:
    assert _make_user(monthly_budget_usd=Decimal("0")).monthly_budget_usd == 0


def test_negative_budget_raises_error() -> None:
    with pytest.raises(InvalidUserError):
        _make_user(monthly_budget_usd=Decimal("-0.01"))


def test_naive_created_at_raises_error() -> None:
    with pytest.raises(InvalidUserError):
        _make_user(created_at=datetime(2026, 9, 1, 12, 0))


def test_user_is_mutable_entity() -> None:
    user = _make_user()

    user.language = Language.EN
    user.monthly_budget_usd = Decimal("2.50")

    assert user.language == Language.EN
    assert user.monthly_budget_usd == Decimal("2.50")
