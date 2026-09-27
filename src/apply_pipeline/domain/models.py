import hashlib
from dataclasses import dataclass
from datetime import datetime

from apply_pipeline.domain.errors import InvalidVacancyError
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
        return make_vacancy_key(self.source, self.external_id)

    @property
    def content_hash(self) -> str:
        fields = (
            self.title,
            self.company,
            self.location or "",
            self.salary_text or "",
            self.description,
        )

        normalized_fields = (" ".join(value.split()) for value in fields)

        content = "\x1f".join(normalized_fields)

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def age_days(self, now: datetime) -> int:
        return (now - self.published_at).days


def make_vacancy_key(source: Source, external_id: str) -> str:
    return f"{source.value}:{external_id}"


def split_vacancy_key(key: str) -> tuple[Source, str]:
    source_value, separator, external_id = key.partition(":")

    if not separator:
        raise InvalidVacancyError("Vacancy key must contain ':'.")

    if not external_id.strip():
        raise InvalidVacancyError("Vacancy key must contain a non-empty external id.")

    try:
        source = Source(source_value)
    except ValueError as error:
        raise InvalidVacancyError(f"Unknown vacancy source: '{source_value}'.") from error

    return source, external_id
