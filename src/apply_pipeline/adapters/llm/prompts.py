from pathlib import Path

JUDGE_PROMPT_VERSION = "judge_v1"


def load_prompt(name: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / f"{name}.md"
    return prompt_path.read_text(encoding="utf-8")


def build_judge_instructions() -> str:
    judge_prompt = load_prompt(JUDGE_PROMPT_VERSION)
    profile = load_prompt("profile")

    return f"{judge_prompt}\n\n{profile}"
