"""LangGraph workflow for the HomeWatt Advisor planner."""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agents.appliance_agent import appliance_analyzer_node
from app.agents.bill_agent import bill_calculator_node
from app.agents.guide_agent import guide_writer_node
from app.agents.optimizer_agent import usage_optimizer_node
from app.agents.supervisor import supervisor_node
from app.graph.state import HomeWattState


def _next_after_appliance(state: HomeWattState) -> Literal["bill_calculator", "guide_writer"]:
    if state.get("error") or state.get("casual_response"):
        return "guide_writer"
    return "bill_calculator"


def _next_after_mcp(state: HomeWattState) -> Literal["usage_optimizer", "guide_writer"]:
    if state.get("error"):
        return "guide_writer"
    return "usage_optimizer"


def _next_after_optimizer(state: HomeWattState) -> Literal["guide_writer"]:
    return "guide_writer"


def build_homewatt_graph():
    graph = StateGraph(HomeWattState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("appliance_analyzer", appliance_analyzer_node)
    graph.add_node("bill_calculator", bill_calculator_node)
    graph.add_node("usage_optimizer", usage_optimizer_node)
    graph.add_node("guide_writer", guide_writer_node)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "appliance_analyzer")
    graph.add_conditional_edges("appliance_analyzer", _next_after_appliance)
    graph.add_conditional_edges("bill_calculator", _next_after_mcp)
    graph.add_conditional_edges("usage_optimizer", _next_after_optimizer)
    graph.add_edge("guide_writer", END)

    return graph.compile()


homewatt_graph = build_homewatt_graph()


async def run_homewatt_workflow(
    user_id: int,
    session_id: int | None,
    message: str,
) -> dict:
    """Run the planner workflow and return the answer plus final state."""
    initial_state: HomeWattState = {
        "user_id": user_id,
        "session_id": session_id,
        "message": message,
    }
    final_state = await homewatt_graph.ainvoke(initial_state)
    return {
        "answer": final_state.get("final_answer", ""),
        "state": final_state,
    }
