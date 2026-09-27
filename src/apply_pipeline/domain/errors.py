from uuid import UUID

from apply_pipeline.domain.transitions import MatchStatus


class DomainError(Exception):
    """Base class for all domain-level exceptions."""


class InvalidVacancyError(DomainError):
    """Raised when vacancy data is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidProfileError(DomainError):
    """Raised when candidate profile data or criteria are invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidUserError(DomainError):
    """Raised when user data is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidMatchError(DomainError):
    """Raised when match data is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ScoringError(DomainError):
    """Raised when scoring cannot be calculated from the provided input."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidVerdictError(DomainError):
    """Raised when judge verdict or usage data is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidTransitionError(DomainError):
    """Raised when a match status transition is not allowed."""

    def __init__(
        self,
        from_status: MatchStatus,
        to_status: MatchStatus,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"Cannot change status from {from_status} to {to_status}"

        super().__init__(message)
        self.from_status = from_status
        self.to_status = to_status


class NotFoundError(DomainError):
    """Raised when a requested domain entity is not found."""

    def __init__(self, entity: str, key: str) -> None:
        super().__init__(f'{entity} "{key}" not found')
        self.entity = entity
        self.key = key


class DuplicateEmailError(DomainError):
    """Raised when a user with the same email already exists."""

    def __init__(self, email: str) -> None:
        super().__init__(f'Email "{email}" is already in use')
        self.email = email


class ProfileVersionConflictError(DomainError):
    """Raised when a candidate profile version already exists."""

    def __init__(self, user_id: UUID, version: int) -> None:
        super().__init__(f'Profile version {version} for user "{user_id}" already exists')
        self.user_id = user_id
        self.version = version
