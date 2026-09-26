from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from apply_pipeline.domain.errors import InvalidUserError


class Language(StrEnum):
    UK = "uk"
    EN = "en"


@dataclass(slots=True)
class User:
    id: UUID
    email: str
    created_at: datetime
    language: Language = Language.UK
    monthly_budget_usd: Decimal = Decimal("1.00")
    is_active: bool = True

    def __post_init__(self) -> None:
        self.email = self.email.strip().lower()

        if self.email.count("@") != 1:
            raise InvalidUserError("Email must contain exactly one '@'.")

        local_part, domain_part = self.email.split("@")

        if not local_part or not domain_part:
            raise InvalidUserError("Email must contain non-empty parts before and after '@'.")

        if self.monthly_budget_usd < 0:
            raise InvalidUserError("Monthly budget cannot be negative.")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidUserError("Created_at must be timezone-aware.")
