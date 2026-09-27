from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic_ai import (
    Agent,
    AgentRunError,
    FallbackExceptionGroup,
    capture_run_messages,
)
from pydantic_ai.messages import ModelResponse
from pydantic_ai.usage import RunUsage

from apply_pipeline.adapters.llm.evidence import check_answers
from apply_pipeline.adapters.llm.judge_agent import (
    JudgeDeps,
    vacancy_to_prompt,
)
from apply_pipeline.adapters.llm.prompts import (
    JUDGE_PROMPT_VERSION,
    prompted_criteria,
)
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.judge import (
    JudgeFailure,
    JudgeUsage,
    JudgeVerdict,
)
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.user import Language


class JudgeState(TypedDict, total=False):
    vacancy: Vacancy
    profile: CandidateProfile
    language: Language

    prompt: str
    output: JudgeOutput | None
    usage: JudgeUsage | None
    failure: JudgeFailure | None
    error: str | None

    verdict: JudgeVerdict | None


def _to_judge_usage(
    run_usage: RunUsage,
    model_name: str,
) -> JudgeUsage:
    return JudgeUsage(
        model_name=model_name,
        input_tokens=run_usage.input_tokens,
        output_tokens=run_usage.output_tokens,
        cache_read_tokens=run_usage.cache_read_tokens,
        cost_usd=run_usage.cost,
    )


def route_after_call(state: JudgeState) -> str:
    if state.get("output") is not None:
        return "finalize"

    return "fail_open"


def build_judge_graph(
    agent: Agent[JudgeDeps, JudgeOutput],
) -> CompiledStateGraph[
    JudgeState,
    None,
    JudgeState,
    JudgeState,
]:
    def prepare(
        state: JudgeState,
    ) -> dict[str, object]:
        return {
            "prompt": vacancy_to_prompt(state["vacancy"]),
        }

    async def call_model(
        state: JudgeState,
    ) -> dict[str, object]:
        run_usage = RunUsage()

        with capture_run_messages() as messages:

            def failure_result(
                error: BaseException,
            ) -> dict[str, object]:
                if run_usage.requests == 0:
                    return {
                        "error": str(error),
                        "failure": JudgeFailure.UNAVAILABLE,
                        "usage": None,
                    }

                model_name = "unknown"

                for message in reversed(messages):
                    if isinstance(message, ModelResponse):
                        model_name = message.model_name or "unknown"
                        break

                return {
                    "error": str(error),
                    "failure": JudgeFailure.INVALID_OUTPUT,
                    "usage": _to_judge_usage(
                        run_usage,
                        model_name,
                    ),
                }

            try:
                result = await agent.run(
                    state["prompt"],
                    deps=JudgeDeps(
                        profile=state["profile"],
                        language=state["language"],
                    ),
                    usage=run_usage,
                )

                model_name = result.response.model_name or "unknown"

                return {
                    "output": result.output,
                    "usage": _to_judge_usage(
                        run_usage,
                        model_name,
                    ),
                    "failure": None,
                }

            except FallbackExceptionGroup as error:
                return failure_result(error)

            except AgentRunError as error:
                return failure_result(error)

    def finalize(
        state: JudgeState,
    ) -> dict[str, object]:
        output = state.get("output")
        usage = state.get("usage")

        assert output is not None
        assert usage is not None

        criteria = prompted_criteria(state["profile"])

        criterion_ids = {criterion.id for criterion in criteria}

        checked = check_answers(
            output.answers,
            criterion_ids=criterion_ids,
            vacancy_text=state["prompt"],
        )

        return {
            "verdict": JudgeVerdict(
                results=checked.results,
                summary=output.summary,
                prompt_version=JUDGE_PROMPT_VERSION,
                usage=usage,
                failure=None,
                discarded=checked.discarded,
            )
        }

    def fail_open(
        state: JudgeState,
    ) -> dict[str, object]:
        failure = state.get("failure")

        assert failure is not None

        return {
            "verdict": JudgeVerdict(
                results=(),
                summary=None,
                prompt_version=JUDGE_PROMPT_VERSION,
                usage=state.get("usage"),
                failure=failure,
                discarded=0,
            )
        }

    graph = StateGraph(JudgeState)

    graph.add_node("prepare", prepare)
    graph.add_node("call_model", call_model)
    graph.add_node("finalize", finalize)
    graph.add_node("fail_open", fail_open)

    graph.add_edge(
        START,
        "prepare",
    )

    graph.add_edge(
        "prepare",
        "call_model",
    )

    graph.add_conditional_edges(
        "call_model",
        route_after_call,
        {
            "finalize": "finalize",
            "fail_open": "fail_open",
        },
    )

    graph.add_edge(
        "finalize",
        END,
    )

    graph.add_edge(
        "fail_open",
        END,
    )

    return graph.compile()


class LangGraphVacancyJudge:
    def __init__(
        self,
        graph: CompiledStateGraph[
            JudgeState,
            None,
            JudgeState,
            JudgeState,
        ],
    ) -> None:
        self.graph = graph

    @property
    def prompt_version(self) -> str:
        return JUDGE_PROMPT_VERSION

    async def judge(
        self,
        vacancy: Vacancy,
        profile: CandidateProfile,
        *,
        language: Language,
    ) -> JudgeVerdict:
        result = await self.graph.ainvoke(
            {
                "vacancy": vacancy,
                "profile": profile,
                "language": language,
            }
        )

        verdict = result.get("verdict")

        if not isinstance(
            verdict,
            JudgeVerdict,
        ):
            raise RuntimeError("Judge graph did not return a valid JudgeVerdict")

        return verdict
