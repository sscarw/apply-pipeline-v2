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
