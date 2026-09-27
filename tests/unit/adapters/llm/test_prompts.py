from dataclasses import replace

import pytest
from jinja2 import UndefinedError

from apply_pipeline.adapters.llm.prompts import (
    _JINJA_ENV,
    JUDGE_PROMPT_VERSION,
    LANGUAGE_NAMES,
    PROFILE_TEMPLATE_FILENAME,
    PROMPTS_DIR,
    RULES_FILENAME,
    load_rules,
    prompted_criteria,
    render_profile,
)
from apply_pipeline.domain.profile import CandidateProfile, WorkFormat
from apply_pipeline.domain.user import Language


def test_prompt_files_follow_the_version() -> None:
    assert JUDGE_PROMPT_VERSION == "judge_v2"
    assert (PROMPTS_DIR / RULES_FILENAME).is_file()
    assert (PROMPTS_DIR / PROFILE_TEMPLATE_FILENAME).is_file()


def test_rules_are_the_plain_file() -> None:
    rules = load_rules()

    assert rules == (PROMPTS_DIR / RULES_FILENAME).read_text(encoding="utf-8")
    assert rules.strip()


def test_rules_are_static_text_not_a_template() -> None:
    # The rules are the cacheable prefix: they must be the same for every user.
    rules = load_rules()

    assert "{{" not in rules
    assert "{%" not in rules


def test_every_language_has_a_name() -> None:
    assert set(LANGUAGE_NAMES) == set(Language)


def test_prompted_criteria_drop_ignored_and_keep_order(profile: CandidateProfile) -> None:
    assert [criterion.id for criterion in prompted_criteria(profile)] == [
        "python",
        "no_crypto",
        "llm",
    ]


def test_profile_lists_prompted_criteria_with_ids(profile: CandidateProfile) -> None:
    text = render_profile(profile, Language.UK)

    assert "1. [python] Основна мова роботи Python" in text
    assert "2. [no_crypto] Компанія у сфері криптовалют" in text
    assert "3. [llm] Робота з LLM і агентами" in text
    assert "office_only" not in text


def test_profile_contains_structured_fields(profile: CandidateProfile) -> None:
    text = render_profile(profile, Language.UK)

    assert "Junior Python Developer, AI Engineer" in text
    assert "0 years" in text
    assert "Python, FastAPI" in text
    assert "(city: Львів)" in text
    assert "500 USD per month" in text
    assert "Write the summary in Ukrainian." in text


def test_summary_language_follows_the_user(profile: CandidateProfile) -> None:
    assert "Write the summary in English." in render_profile(profile, Language.EN)


def test_work_formats_are_sorted(profile: CandidateProfile) -> None:
    # A frozenset has no stable order between processes; the prompt must not change.
    assert "Work formats: hybrid, office, remote" in render_profile(profile, Language.UK)


def test_same_profile_renders_the_same_text(profile: CandidateProfile) -> None:
    copy = replace(profile, work_formats=frozenset(reversed(list(profile.work_formats))))

    assert render_profile(profile, Language.UK) == render_profile(copy, Language.UK)


def test_optional_fields_say_not_specified(profile: CandidateProfile) -> None:
    bare = replace(
        profile,
        skills=(),
        city=None,
        min_salary=None,
        work_formats=frozenset({WorkFormat.REMOTE}),
    )

    text = render_profile(bare, Language.UK)

    assert "Skills: not specified" in text
    assert "Minimum salary: not specified" in text
    assert "city:" not in text


@pytest.mark.parametrize(("years", "expected"), [(1, "1 year"), (2, "2 years")])
def test_experience_is_pluralized(profile: CandidateProfile, years: int, expected: str) -> None:
    text = render_profile(replace(profile, experience_years=years), Language.UK)

    assert f"Commercial experience: {expected}" in text


def test_template_fails_loudly_on_missing_variable() -> None:
    # StrictUndefined: a typo in the template must raise, not leave a hole in the prompt.
    with pytest.raises(UndefinedError):
        _JINJA_ENV.get_template(PROFILE_TEMPLATE_FILENAME).render()
