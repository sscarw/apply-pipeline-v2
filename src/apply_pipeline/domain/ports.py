from typing import Protocol
from uuid import UUID

from apply_pipeline.domain.judge import JudgeVerdict
from apply_pipeline.domain.match import Match
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.transitions import MatchStatus
from apply_pipeline.domain.user import User


class VacancyJudge(Protocol):
    """Decides whether a vacancy is worth applying to.

    Services depend on this port rather than on LangGraph or a model provider,
    so the LLM judge can be swapped for a fake in tests.
    """

    async def judge(self, vacancy: Vacancy) -> JudgeVerdict:
        """Read the vacancy and return the verdict.

        Never raises because a model is unavailable: in that case the verdict
        lets the vacancy through with fail_open=True.
        """
        ...


class VacancyRepository(Protocol):
    """Stores and retrieves vacancies.

    The repository never commits transactions. Transaction boundaries are
    controlled by the caller so multiple operations can be one atomic unit.
    """

    async def add_if_absent(self, vacancy: Vacancy) -> bool:
        """Insert the vacancy if it does not already exist."""
        ...

    async def get(self, key: str) -> Vacancy | None:
        """Return a vacancy by its natural key, or None if it does not exist."""
        ...


class UserRepository(Protocol):
    """Stores and retrieves users.

    The repository never commits transactions. Transaction boundaries are
    controlled by the caller so multiple operations can be one atomic unit.
    """

    async def add(self, user: User) -> None:
        """Add a user, raising DuplicateEmailError if the email is occupied."""
        ...

    async def get(self, user_id: UUID) -> User | None:
        """Return a user by id, or None if it does not exist."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Return a user by normalized email, or None if it does not exist."""
        ...


class ProfileRepository(Protocol):
    """Stores and retrieves candidate profile versions.

    The repository never commits transactions. Transaction boundaries are
    controlled by the caller so multiple operations can be one atomic unit.
    """

    async def add(self, profile: CandidateProfile) -> None:
        """Add a profile version.

        Raises ProfileVersionConflictError if the version already exists and
        NotFoundError if the user does not exist.
        """
        ...

    async def get_latest(
        self,
        user_id: UUID,
    ) -> CandidateProfile | None:
        """Return the latest profile version for a user, or None."""
        ...

    async def get(
        self,
        user_id: UUID,
        version: int,
    ) -> CandidateProfile | None:
        """Return a specific profile version, or None if it does not exist."""
        ...


class MatchRepository(Protocol):
    """Stores and retrieves vacancy matches for users.

    The repository never commits transactions. Transaction boundaries are
    controlled by the caller so multiple operations can be one atomic unit.
    """

    async def add_if_absent(self, match: Match) -> bool:
        """Insert a new match if absent.

        Raises NotFoundError if the referenced vacancy does not exist.
        """
        ...

    async def get(
        self,
        user_id: UUID,
        vacancy_key: str,
    ) -> Match | None:
        """Return a match by user and vacancy key, or None."""
        ...

    async def save(self, match: Match) -> None:
        """Persist changes to an existing match.

        Raises NotFoundError if the match does not exist.
        """
        ...

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        status: MatchStatus,
        limit: int,
    ) -> list[Match]:
        """Return matches for a user and status, with best scores first."""
        ...
