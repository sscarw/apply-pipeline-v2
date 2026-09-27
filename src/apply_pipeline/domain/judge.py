from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from apply_pipeline.domain.criteria import CriterionResult
from apply_pipeline.domain.errors import InvalidVerdictError


class JudgeFailure(StrEnum):
    """Why the judge produced no result, told apart by money spent.

    UNAVAILABLE: no model answered at all, so nothing was billed. The vacancy stays
    new and the next scheduled run judges it again for free.
    INVALID_OUTPUT: a model answered and was billed, but never with a valid result.
    It is not retried automatically and waits for a manual re-judge.
    """

    UNAVAILABLE = "unavailable"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True, slots=True)
class JudgeUsage:
    """Usage metrics for the model that actually answered the judge request."""

    model_name: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: Decimal | None

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise InvalidVerdictError("Model name cannot be empty.")

        if min(self.input_tokens, self.output_tokens, self.cache_read_tokens) < 0:
            raise InvalidVerdictError("Token counts cannot be negative.")

        if self.cost_usd is not None and self.cost_usd < 0:
            raise InvalidVerdictError("Cost cannot be negative.")


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    """Structured result of judging a vacancy against candidate criteria.

    Contains criterion results, a user-facing summary, prompt version,
    model usage information, the failure kind, and discarded answer count.

    A verdict with a failure carries no results and no summary. It has usage
    exactly when the failure was billed (INVALID_OUTPUT), so spending is never
    lost. A verdict without a failure comes from a valid model answer and always
    has a summary and usage.
    """

    results: tuple[CriterionResult, ...]
    summary: str | None
    prompt_version: str
    usage: JudgeUsage | None
    failure: JudgeFailure | None
    discarded: int

    def __post_init__(self) -> None:
        if not self.prompt_version.strip():
            raise InvalidVerdictError("Prompt version cannot be empty.")

        if self.discarded < 0:
            raise InvalidVerdictError("Discarded count cannot be negative.")

        if self.failure is not None:
            self._check_failed()
            return

        if self.summary is None or not self.summary.strip():
            raise InvalidVerdictError("Judged verdict must have a summary.")

        if self.usage is None:
            raise InvalidVerdictError("Judged verdict must have usage.")

    def _check_failed(self) -> None:
        if self.results or self.summary is not None or self.discarded != 0:
            raise InvalidVerdictError(
                "Failed verdict cannot have results, summary or discarded answers."
            )

        billed = self.failure is JudgeFailure.INVALID_OUTPUT

        if billed and self.usage is None:
            raise InvalidVerdictError("Billed failure must keep its usage.")

        if not billed and self.usage is not None:
            raise InvalidVerdictError("Unavailable model cannot have usage.")

    @property
    def fail_open(self) -> bool:
        """True when no model gave a valid answer and the vacancy needs another look."""
        return self.failure is not None
