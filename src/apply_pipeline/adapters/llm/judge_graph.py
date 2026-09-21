from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic_ai import Agent, AgentRunError, FallbackExceptionGroup

from apply_pipeline.adapters.llm.judge_agent import vacancy_to_prompt
from apply_pipeline.adapters.llm.prompts import JUDGE_PROMPT_VERSION
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.judge import JudgeVerdict
from apply_pipeline.domain.models import Vacancy


class JudgeState(TypedDict, total=False):
    vacancy: Vacancy
    prompt: str
    output: JudgeOutput | None
    error: str | None
    verdict: JudgeVerdict | None


def route_after_call(state: JudgeState) -> str:
    if state.get("output") is not None:
        return "finalize"

    return "fail_open"


def build_judge_graph(
    agent: Agent[None, JudgeOutput],
) -> CompiledStateGraph[JudgeState, None, JudgeState, JudgeState]:
    def prepare(state: JudgeState) -> dict[str, object]:
        return {
            "prompt": vacancy_to_prompt(state["vacancy"]),
        }

    async def call_model(state: JudgeState) -> dict[str, object]:
        try:
            result = await agent.run(state["prompt"])
            return {
                "output": result.output,
            }
        except (AgentRunError, FallbackExceptionGroup) as error:
            return {
                "error": str(error),
            }

    def finalize(state: JudgeState) -> dict[str, object]:
        output = state.get("output")
        assert output is not None

        return {
            "verdict": JudgeVerdict(
                apply=output.apply,
                reason=output.reason,
                gaps=tuple(output.gaps),
                prompt_version=JUDGE_PROMPT_VERSION,
                fail_open=False,
            )
        }

    def fail_open(state: JudgeState) -> dict[str, object]:
        return {
            "verdict": JudgeVerdict(
                apply=True,
                reason="judge unavailable, check manually",
                gaps=(),
                prompt_version=JUDGE_PROMPT_VERSION,
                fail_open=True,
            )
        }

    graph = StateGraph(JudgeState)

    graph.add_node("prepare", prepare)
    graph.add_node("call_model", call_model)
    graph.add_node("finalize", finalize)
    graph.add_node("fail_open", fail_open)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "call_model")

    graph.add_conditional_edges(
        "call_model",
        route_after_call,
        {
            "finalize": "finalize",
            "fail_open": "fail_open",
        },
    )

    graph.add_edge("finalize", END)
    graph.add_edge("fail_open", END)

    return graph.compile()


class LangGraphVacancyJudge:
    def __init__(
        self,
        graph: CompiledStateGraph[JudgeState, None, JudgeState, JudgeState],
    ) -> None:
        self.graph = graph

    async def judge(self, vacancy: Vacancy) -> JudgeVerdict:
        result = await self.graph.ainvoke({"vacancy": vacancy})

        verdict = result.get("verdict")
        if not isinstance(verdict, JudgeVerdict):
            raise RuntimeError("Judge graph did not return a valid JudgeVerdict")

        return verdict
