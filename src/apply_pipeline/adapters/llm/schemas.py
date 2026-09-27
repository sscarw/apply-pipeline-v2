from pydantic import BaseModel, Field

from apply_pipeline.domain.criteria import CriterionStatus
from apply_pipeline.domain.profile import MAX_CRITERIA


class CriterionAnswer(BaseModel):
    criterion_id: str = Field(description="Criterion ID from square brackets, exactly as written.")
    status: CriterionStatus = Field(description="Criterion status.")
    evidence: str | None = Field(
        default=None,
        max_length=400,
        description=("Exact quote from the vacancy for MET and NOT_MET; null for UNKNOWN."),
    )


class JudgeOutput(BaseModel):
    answers: list[CriterionAnswer] = Field(
        max_length=MAX_CRITERIA,
        description="Answers for the criteria shown to the judge.",
    )
    summary: str = Field(
        max_length=400,
        description=(
            "One or two sentences, up to 300 characters, in the language specified in the profile."
        ),
    )
