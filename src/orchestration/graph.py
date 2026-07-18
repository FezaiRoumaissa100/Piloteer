from langgraph.graph import StateGraph, START, END
from mcp import ClientSession
from orchestration.state import SharedState
from nodes.planner import planner_node
from nodes.actor import make_actor_node
from nodes.validator import validator_node


MAX_STEPS = 15

def route_after_planner(state: SharedState) -> str:
    """
    Routing function called after the Planner execution.
    """

    if not state.get("current_step"):
        print("\n[LangGraph] Planner returned no step. Stopping.")
        return "stop"

    return "action"


def route_after_validator(state: SharedState) -> str:
    """
    Routing function called after the Validator execution.
    Always routes back to the Planner for the next step or replanning,
    unless there's a critical error.
    """
    # error from Actor
    if state.get("last_action_result", "").startswith("error:"):
        print(f"\n[LangGraph] Actor error detected — stopping.")
        return "stop"

    # Validator determined the task is fully complete
    if state.get("task_done"):
        print("\n[LangGraph] Task is marked as DONE by Validator. Stopping.")
        return "stop"


    print("\n[LangGraph] Returning to Planner for next instruction.")
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
    graph.add_node("planner",   planner_node)
    graph.add_node("actor",     actor_node)
    graph.add_node("validator", validator_node)
    # Entry point
    graph.add_edge(START, "planner")
    # from planner
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "action": "actor",
            "stop":   END
        }
    )
    # actor to validator
    graph.add_edge("actor", "validator")

    # validator to planner
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "planning": "planner",
            "stop":     END
        }
    )
    return graph.compile()
