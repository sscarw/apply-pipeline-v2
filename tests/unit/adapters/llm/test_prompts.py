import pytest

from apply_pipeline.adapters.llm.prompts import (
    JUDGE_PROMPT_VERSION,
    build_judge_instructions,
    load_prompt,
)


def test_judge_prompt_file_exists_for_current_version() -> None:
    assert load_prompt(JUDGE_PROMPT_VERSION).strip()


def test_instructions_contain_judge_rules_and_profile() -> None:
    instructions = build_judge_instructions()

    assert load_prompt(JUDGE_PROMPT_VERSION) in instructions
    assert load_prompt("profile") in instructions


def test_rules_come_before_profile() -> None:
    instructions = build_judge_instructions()

    rules_at = instructions.index(load_prompt(JUDGE_PROMPT_VERSION))
    profile_at = instructions.index(load_prompt("profile"))
    assert rules_at < profile_at


def test_unknown_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("judge_v999")
