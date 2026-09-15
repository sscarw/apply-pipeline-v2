from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Source(StrEnum):
    DJINNI = "djinni"
    DOU = "dou"


class VacancyStatus(StrEnum):
    NEW = "new"
    FILTERED_OUT = "filtered_out"
    JUDGED = "judged"
    SHORTLISTED = "shortlisted"
    DISMISSED = "dismissed"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


ALLOWED_TRANSITIONS: Final[Mapping[VacancyStatus, frozenset[VacancyStatus]]] = MappingProxyType(
    {
        VacancyStatus.NEW: frozenset(
            {
                VacancyStatus.FILTERED_OUT,
                VacancyStatus.JUDGED,
            }
        ),
        VacancyStatus.FILTERED_OUT: frozenset(
            {
                VacancyStatus.SHORTLISTED,
            }
        ),
        VacancyStatus.JUDGED: frozenset(
            {
                VacancyStatus.SHORTLISTED,
                VacancyStatus.DISMISSED,
            }
        ),
        VacancyStatus.SHORTLISTED: frozenset(
            {
                VacancyStatus.APPLIED,
                VacancyStatus.DISMISSED,
            }
        ),
        VacancyStatus.DISMISSED: frozenset(
            {
                VacancyStatus.SHORTLISTED,
            }
        ),
        VacancyStatus.APPLIED: frozenset(
            {
                VacancyStatus.INTERVIEW,
                VacancyStatus.REJECTED,
            }
        ),
        VacancyStatus.INTERVIEW: frozenset(
            {
                VacancyStatus.OFFER,
                VacancyStatus.REJECTED,
            }
        ),
        VacancyStatus.OFFER: frozenset(),
        VacancyStatus.REJECTED: frozenset(),
    }
)

TERMINAL_STATUSES: Final[frozenset[VacancyStatus]] = frozenset(
    status for status, allowed in ALLOWED_TRANSITIONS.items() if not allowed
)


def can_transition(
    from_status: VacancyStatus,
    to_status: VacancyStatus,
) -> bool:
    return to_status in ALLOWED_TRANSITIONS[from_status]
