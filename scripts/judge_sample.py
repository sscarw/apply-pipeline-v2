import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from apply_pipeline.adapters.llm.judge_agent import build_judge_agent
from apply_pipeline.adapters.llm.judge_graph import LangGraphVacancyJudge, build_judge_graph
from apply_pipeline.adapters.llm.models import build_judge_model
from apply_pipeline.config import get_settings
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.transitions import Source


def load_labelled(path: Path, limit: int) -> list[tuple[Vacancy, str]]:
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

    labelled = load_labelled(args.path, args.limit)

    matched = 0

    for vacancy, label in labelled:
        verdict = await judge.judge(vacancy)

        judge_label = "apply" if verdict.apply else "skip"

        if judge_label == label:
            matched += 1

        gaps = ", ".join(verdict.gaps) if verdict.gaps else "-"

        print(
            f"{vacancy.title} | "
            f"label={label} | "
            f"judge={judge_label} | "
            f"reason={verdict.reason} | "
            f"gaps={gaps}"
        )

    print(f"\nMatched {matched} of {len(labelled)}")


if __name__ == "__main__":
    asyncio.run(main())
