from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    """The judge's answer to "should the candidate apply to this vacancy?".

    A value object: once the judge has decided, the verdict never changes.

    Attributes:
        apply: True when no stop factor was found and the candidate should apply.
        reason: One sentence explaining the decision, in Ukrainian.
        gaps: Skills the vacancy asks for that the candidate does not have yet,
            most important first. Gaps never block a vacancy on their own.
        prompt_version: The prompt that produced the verdict, e.g. "judge_v1",
            so verdicts made with different prompts can be told apart.
        fail_open: True when no model could answer and the vacancy was let
            through unjudged, to be checked by hand.
    """

    apply: bool
    reason: str
    gaps: tuple[str, ...]
    prompt_version: str
    fail_open: bool
