from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from apply_pipeline.domain.criteria import Criterion, Priority
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.user import Language

JUDGE_PROMPT_VERSION = "judge_v2"

PROMPTS_DIR = Path(__file__).parent / "prompts"

RULES_FILENAME = f"{JUDGE_PROMPT_VERSION}.md"
PROFILE_TEMPLATE_FILENAME = f"{JUDGE_PROMPT_VERSION}_profile.md.j2"

LANGUAGE_NAMES: Final[Mapping[Language, str]] = MappingProxyType(
    {
        Language.UK: "Ukrainian",
        Language.EN: "English",
    }
)

_JINJA_ENV = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def load_rules() -> str:
    return (PROMPTS_DIR / RULES_FILENAME).read_text(encoding="utf-8")


def prompted_criteria(
    profile: CandidateProfile,
) -> tuple[Criterion, ...]:
    return tuple(
        criterion for criterion in profile.criteria if criterion.priority != Priority.IGNORE
    )


def render_profile(
    profile: CandidateProfile,
    language: Language,
) -> str:
    work_formats = sorted(work_format.value for work_format in profile.work_formats)

    salary: str | None = None

    if profile.min_salary is not None:
        salary = (
            f"{profile.min_salary.amount} {profile.min_salary.currency.value.upper()} per month"
        )

    template = _JINJA_ENV.get_template(PROFILE_TEMPLATE_FILENAME)

    return template.render(
        roles=profile.desired_roles,
        experience_years=profile.experience_years,
        skills=profile.skills,
        work_formats=work_formats,
        city=profile.city,
        salary=salary,
        criteria=prompted_criteria(profile),
        language_name=LANGUAGE_NAMES[language],
    )
