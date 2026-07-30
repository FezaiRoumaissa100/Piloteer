from langgraph.graph import StateGraph, START, END
from mcp import ClientSession
from orchestration.state import SharedState
from nodes.planner import planner_node
from nodes.actor import make_actor_node
from nodes.validator import validator_node
from nodes.high_level_planner import high_level_planner_node
from nodes.ask_user import ask_user_node


MAX_STEPS = 15

def route_after_planner(state: SharedState) -> str:
    if not state.get("current_step"):
        print("\n[LangGraph] Planner returned no step. Stopping.")
        return "stop"
    if state["current_step"].get("tool") == "ask_user":
        return "ask_user"
    return "action"


def route_after_validator(state: SharedState) -> str:
    """
    Hierarchical routing after Validator execution.
    """
    if state.get("last_action_result", "").startswith("error: no step"):
        print(f"\n[LangGraph] Actor error detected — stopping.")
        return "stop"

    if state.get("task_status") == "completed":
        print("\n[LangGraph] Task is marked as COMPLETED. Stopping.")
        return "stop"

    # Check if current subgoal needs escalation
    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    
    if subgoals and current_index < len(subgoals):
        if subgoals[current_index].get("status") == "failed":
            print("\n[LangGraph] Escalating to High-Level Planner for revision.")
            return "high_level_planner"

    print("\n[LangGraph] Returning to Low-Level Planner for next instruction.")
    return "planning"


def build_graph(session: ClientSession):
    """
    Builds and compiles the LangGraph pipeline.
    Args:
        session : Active MCP ClientSession — shared across all nodes.
    Returns:
        Compiled LangGraph app.
    """
    actor_node = make_actor_node(session)
    graph = StateGraph(SharedState)
    
    # Register nodes
    graph.add_node("high_level_planner", high_level_planner_node)
    graph.add_node("planner",            planner_node)
    graph.add_node("actor",              actor_node)
    graph.add_node("validator",          validator_node)
    graph.add_node("ask_user",           ask_user_node)
    
    # Entry point is now the high level planner
    graph.add_edge(START, "high_level_planner")
    
    # High-level planner always delegates to low-level planner
    graph.add_edge("high_level_planner", "planner")
    
    # Low-level planner -> Actor or ask_user
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "action":   "actor",
            "ask_user": "ask_user",
            "stop":     END
        }
    )

    # ask_user -> back to planner with the answer
    graph.add_edge("ask_user", "planner")
    
    # Actor -> Validator
    graph.add_edge("actor", "validator")

    # Validator -> routing
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "planning":           "planner",
            "high_level_planner": "high_level_planner",
            "stop":               END
        }
    )
    return graph.compile()
