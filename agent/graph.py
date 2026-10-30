from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    triage_node,
    emergency_halt_node,
    navigation_node,
    care_summary_node
)


def route_after_triage(state: AgentState) -> str:
    """Conditional Edge: Halts flow immediately if an emergency red flag is found."""
    if state.get("is_emergency") or state.get("urgency_level", "").lower() == "emergency":
        return "emergency_halt"
    return "navigation"


def build_healthcare_graph():
    """Builds and compiles the MediPilot Multi-Agent Graph."""
    workflow = StateGraph(AgentState)

    # 1. Register the Sub-Agent nodes
    workflow.add_node("triage", triage_node)
    workflow.add_node("emergency_halt", emergency_halt_node)
    workflow.add_node("navigation", navigation_node)
    workflow.add_node("care_summary", care_summary_node)

    # 2. Set the entry point
    workflow.set_entry_point("triage")

    # 3. Add conditional edge from Triage
    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "emergency_halt": "emergency_halt",
            "navigation": "navigation"
        }
    )

    # 4. Standard flow edges
    workflow.add_edge("navigation", "care_summary")
    workflow.add_edge("care_summary", END)
    workflow.add_edge("emergency_halt", END)

    return workflow.compile()