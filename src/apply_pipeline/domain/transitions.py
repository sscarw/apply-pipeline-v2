from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Source(StrEnum):
    DJINNI = "djinni"
    DOU = "dou"


class MatchStatus(StrEnum):
    NEW = "new"
    FILTERED_OUT = "filtered_out"
    JUDGED = "judged"
    SHORTLISTED = "shortlisted"
    DISMISSED = "dismissed"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


ALLOWED_TRANSITIONS: Final[Mapping[MatchStatus, frozenset[MatchStatus]]] = MappingProxyType(
    {
        MatchStatus.NEW: frozenset(
            {
                MatchStatus.FILTERED_OUT,
                MatchStatus.JUDGED,
            }
        ),
        MatchStatus.FILTERED_OUT: frozenset(
            {
                MatchStatus.SHORTLISTED,
            }
        ),
        MatchStatus.JUDGED: frozenset(
            {
                MatchStatus.SHORTLISTED,
                MatchStatus.DISMISSED,
            }
        ),
        MatchStatus.SHORTLISTED: frozenset(
            {
                MatchStatus.APPLIED,
                MatchStatus.DISMISSED,
            }
        ),
        MatchStatus.DISMISSED: frozenset(
            {
                MatchStatus.SHORTLISTED,
            }
        ),
        MatchStatus.APPLIED: frozenset(
            {
                MatchStatus.INTERVIEW,
                MatchStatus.REJECTED,
            }
        ),
        MatchStatus.INTERVIEW: frozenset(
            {
                MatchStatus.OFFER,
                MatchStatus.REJECTED,
            }
        ),
        MatchStatus.OFFER: frozenset(),
        MatchStatus.REJECTED: frozenset(),
    }
)

TERMINAL_STATUSES: Final[frozenset[MatchStatus]] = frozenset(
    status for status, allowed in ALLOWED_TRANSITIONS.items() if not allowed
)


def can_transition(
    from_status: MatchStatus,
    to_status: MatchStatus,
) -> bool:
    return to_status in ALLOWED_TRANSITIONS[from_status]
