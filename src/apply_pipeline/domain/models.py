from dataclasses import dataclass
from datetime import datetime

from apply_pipeline.domain.errors import (
    InvalidVacancyError,
)
from apply_pipeline.domain.transitions import Source


@dataclass(slots=True)
class Vacancy:
    source: Source
    external_id: str
    url: str
    title: str
    company: str
    description: str
    published_at: datetime
    location: str | None = None
    salary_text: str | None = None

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise InvalidVacancyError("external_id cannot be empty")

        if not self.title.strip():
            raise InvalidVacancyError("title cannot be empty")

        if not self.company.strip():
            raise InvalidVacancyError("company cannot be empty")

        if not self.url.startswith(("http://", "https://")):
            raise InvalidVacancyError("url must start with http:// or https://")

        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise InvalidVacancyError("published_at must be timezone-aware")

    @property
    def key(self) -> str:
        return f"{self.source.value}:{self.external_id}"

    def age_days(self, now: datetime) -> int:
        return (now - self.published_at).days
