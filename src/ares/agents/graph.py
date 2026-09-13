"""LangGraph state machine builder and orchestrator for Ares."""

from functools import partial
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ares.agents.nodes.approval import approval_node
from ares.agents.nodes.coder import coder_node
from ares.agents.nodes.evaluator import TestRunnerFunc, evaluator_node
from ares.agents.nodes.triage import triage_node
from ares.agents.routing import route_evaluator
from ares.agents.state import AgentState


def build_repair_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    llm: Any = None,
    test_runner: TestRunnerFunc | None = None,
) -> CompiledStateGraph[AgentState, None, Any, Any]:
    """Build and compile the autonomous code repair LangGraph.

    Args:
        checkpointer: State persistence saver (MemorySaver or PostgresSaver).
        llm: Language model instance or mock.
        test_runner: Custom test runner function for testing/sandboxing.

    Returns:
        CompiledStateGraph ready for execution.
    """
    builder = StateGraph(AgentState)

    # Bind node functions with injected dependencies
    triage_fn = partial(triage_node, llm=llm) if llm else triage_node
    coder_fn = partial(coder_node, llm=llm) if llm else coder_node
    evaluator_fn = (
        partial(evaluator_node, test_runner=test_runner) if test_runner else evaluator_node
    )

    builder.add_node("triage", triage_fn)
    builder.add_node("coder", coder_fn)
    builder.add_node("evaluator", evaluator_fn)
    builder.add_node("approval", approval_node)

    # Sequential edges
    builder.add_edge(START, "triage")
    builder.add_edge("triage", "coder")
    builder.add_edge("coder", "evaluator")

    # Conditional branching from Evaluator
    builder.add_conditional_edges(
        "evaluator",
        route_evaluator,
        {
            "coder": "coder",
            "approval": "approval",
            "failure": END,
        },
    )

    builder.add_edge("approval", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    compiled: CompiledStateGraph[AgentState, None, Any, Any] = builder.compile(checkpointer=saver)
    return compiled


def run_repair_workflow(
    initial_state: AgentState,
    thread_id: str = "ares-session-default",
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    llm: Any = None,
    test_runner: TestRunnerFunc | None = None,
) -> AgentState:
    """Execute the repair graph to completion or interruption."""
    graph = build_repair_graph(checkpointer=checkpointer, llm=llm, test_runner=test_runner)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(initial_state, config=config)
    return cast(AgentState, result)
