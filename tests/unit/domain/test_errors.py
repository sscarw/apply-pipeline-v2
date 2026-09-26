from uuid import UUID

import pytest

from apply_pipeline.domain.errors import (
    DomainError,
    DuplicateEmailError,
    NotFoundError,
    ProfileVersionConflictError,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_not_found_keeps_entity_and_key() -> None:
    error = NotFoundError("vacancy", "djinni:847958")

    assert error.entity == "vacancy"
    assert error.key == "djinni:847958"
    assert "vacancy" in str(error)
    assert "djinni:847958" in str(error)


def test_duplicate_email_keeps_email() -> None:
    error = DuplicateEmailError("andrii@example.com")

    assert error.email == "andrii@example.com"
    assert "andrii@example.com" in str(error)


def test_profile_version_conflict_keeps_user_and_version() -> None:
    error = ProfileVersionConflictError(USER_ID, 4)

    assert error.user_id == USER_ID
    assert error.version == 4
    assert str(USER_ID) in str(error)
    assert "4" in str(error)


@pytest.mark.parametrize(
    "error",
    [
        NotFoundError("user", str(USER_ID)),
        DuplicateEmailError("andrii@example.com"),
        ProfileVersionConflictError(USER_ID, 1),
    ],
    ids=["not-found", "duplicate-email", "version-conflict"],
)
def test_repository_errors_are_domain_errors(error: DomainError) -> None:
    # Services catch these without knowing anything about SQLAlchemy.
    assert isinstance(error, DomainError)
