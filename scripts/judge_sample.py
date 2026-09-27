import argparse
import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from my_profile import build_my_profile

from apply_pipeline.adapters.llm.judge_agent import build_judge_agent
from apply_pipeline.adapters.llm.judge_graph import (
    LangGraphVacancyJudge,
    build_judge_graph,
)
from apply_pipeline.adapters.llm.models import build_judge_model
from apply_pipeline.config import get_settings
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.scoring import score_match
from apply_pipeline.domain.transitions import Source
from apply_pipeline.domain.user import Language


def load_labelled(
    path: Path,
    limit: int,
) -> list[tuple[Vacancy, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))

    result: list[tuple[Vacancy, str]] = []

    for item in data:
        try:
            source = Source(item["source"].lower())
        except ValueError:
            continue

        url = item["url"]
        external_id = url.rstrip("/").split("/")[-1]

        vacancy = Vacancy(
            source=source,
            external_id=external_id,
            url=url,
            title=item["title"],
            company=item["company"],
            description=item["description"],
            published_at=datetime.now(UTC),
            location=item.get("location"),
            salary_text=item.get("salary_text"),
        )

        result.append((vacancy, item["label"]))

        if len(result) >= limit:
            break

    return result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        type=Path,
        help="Path to labelled vacancies JSON file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of vacancies to judge",
    )
    args = parser.parse_args()

    settings = get_settings()

    model = build_judge_model(settings)
    agent = build_judge_agent(model)
    graph = build_judge_graph(agent)
    judge = LangGraphVacancyJudge(graph)

    profile = build_my_profile(
        uuid4(),
        now=datetime.now(UTC),
    )

    labelled = load_labelled(
        args.path,
        args.limit,
    )

    matched = 0

    apply_total = 0
    apply_passed = 0

    total_cost = Decimal("0")
    total_input_tokens = 0
    total_cache_read_tokens = 0

    for vacancy, label in labelled:
        if label == "apply":
            apply_total += 1

        verdict = await judge.judge(
            vacancy,
            profile,
            language=Language.UK,
        )

        if verdict.usage is not None:
            total_input_tokens += verdict.usage.input_tokens
            total_cache_read_tokens += verdict.usage.cache_read_tokens

            if verdict.usage.cost_usd is not None:
                total_cost += verdict.usage.cost_usd

        if verdict.failure is not None:
            print(
                f"{vacancy.title} | "
                f"label={label} | "
                f"judge=FAIL | "
                f"failure={verdict.failure.value} | "
                f"score=- | "
                f"blocked_by=- | "
                f"discarded={verdict.discarded} | "
                f"summary=-"
            )
            continue

        score = score_match(
            profile.criteria,
            verdict.results,
        )

        judge_label = "skip" if score.is_blocked else "apply"

        if judge_label == label:
            matched += 1

        if label == "apply" and judge_label == "apply":
            apply_passed += 1

        blocked_by = ", ".join(score.blocked_by) if score.blocked_by else "-"

        print(
            f"{vacancy.title} | "
            f"label={label} | "
            f"judge={judge_label} | "
            f"score={score.value} | "
            f"blocked_by={blocked_by} | "
            f"discarded={verdict.discarded} | "
            f"summary={verdict.summary}"
        )

    print(f"\nMatched {matched} of {len(labelled)}")

    print(f"Apply recall: {apply_passed} of {apply_total}")

    print(f"Total cost: ${total_cost}")

    print(f"Input tokens: {total_input_tokens}")

    print(f"Cache read tokens: {total_cache_read_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
