from pydantic import BaseModel, Field


class JudgeOutput(BaseModel):
    apply: bool = Field(description="Whether the candidate should apply for this vacancy")

    reason: str = Field(
        max_length=200,
        description="One sentence in Ukrainian explaining why",
    )

    gaps: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Skills required by the vacancy that the candidate does not have",
    )
