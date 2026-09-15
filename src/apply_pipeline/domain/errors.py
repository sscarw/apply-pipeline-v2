from apply_pipeline.domain.transitions import VacancyStatus


class DomainError(Exception):
    """Base class for all domain-level exceptions."""


class InvalidVacancyError(DomainError):
    """Raised when vacancy data is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidTransitionError(DomainError):
    """Raised when a vacancy status transition is not allowed."""

    def __init__(
        self,
        from_status: VacancyStatus,
        to_status: VacancyStatus,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"Cannot change status from {from_status} to {to_status}"

        super().__init__(message)
        self.from_status = from_status
        self.to_status = to_status
