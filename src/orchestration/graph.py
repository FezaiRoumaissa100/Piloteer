"""
graph.py — Piloteer
LangGraph orchestration — minimal pipeline.

Flow:
  planner → (task_done?) 
               YES → END
               NO  → actor → validator → planner (loop)
"""

from langgraph.graph import StateGraph, END
from mcp import ClientSession

from orchestration.state import SharedState
from nodes.planner import planner_node
from nodes.actor import make_actor_node
from nodes.validator import validator_node


MAX_STEPS = 15

def route_after_planner(state: SharedState) -> str:
    """
    Routing function called after the Planner execution.
    If task_done is True, end the workflow. Otherwise go to Actor.
    """
    if state["task_done"]:
        print("\n[Graph] Task is marked as DONE by Planner. Stopping.")
        return "end"
    
    if not state.get("current_step"):
        print("\n[Graph] Planner returned no step but task is not done. Stopping.")
        return "end"

    return "actor"


def route_after_validator(state: SharedState) -> str:
    """
    Routing function called after the Validator execution.
    Always routes back to the Planner for the next step or replanning,
    unless there's a critical error.
    """
    # Stop on error from Actor
    if state.get("last_action_result", "").startswith("error:"):
        print(f"\n[Graph] Actor error detected — stopping.")
        return "end"

    # Stop if Validator determined the task is fully complete
    if state.get("task_done"):
        print("\n[Graph] Task is marked as DONE by Validator. Stopping.")
        return "end"

    # Minimal version: we always go back to planner to either plan next step or replan
    print("\n[Graph] Returning to Planner for next instruction.")
    return "planner"


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
    graph.set_entry_point("planner")

    # Routing from planner
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "actor": "actor",
            "end":   END
        }
    )

    # Fixed edge: actor always goes to validator
    graph.add_edge("actor", "validator")

    # Routing from validator back to planner
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "planner": "planner",
            "end":     END
        }
    )

    return graph.compile()
