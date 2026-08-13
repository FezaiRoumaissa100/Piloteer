from langgraph.graph import StateGraph, START, END
from mcp import ClientSession
from orchestration.state import SharedState
from nodes.planner import planner_node
from nodes.actor import make_actor_node
from nodes.validator import validator_node
from nodes.task_director import task_director_node
from nodes.ask_user import ask_user_node
from security.output_guardrail import output_guardrail_node


MAX_STEPS = 30

def route_after_task_director(state: SharedState) -> str:
    if state.get("task_status") == "finalized":
        print("\n[LangGraph] Task finalized — stopping.")
        return "stop"
    if state.get("task_status") == "task_impossible":
        print("\n[LangGraph] to TaskDirector for finalization.")
        return "task_director"
    return "planning"


def route_after_planner(state: SharedState) -> str:
    if not state.get("current_step"):
        print("\n[LangGraph] Planner returned no step. Stopping.")
        return "stop"
    if state["current_step"].get("tool") == "ask_user":
        return "ask_user"
    return "output_guardrail"


def route_after_output_guardrail(state: SharedState) -> str:
    """PASS :actor directly | HITL : ask_user for human confirmation."""
    if state.get("security_verdict") == "HITL":
        return "ask_user"
    return "action"


def route_after_ask_user(state: SharedState) -> str:
    if state.get("task_status") == "task_impossible":
        return "task_director"

    if state.get("security_verdict") == "HITL":
        answer = (state.get("user_answer") or "").strip().lower()
        if answer == "allow":
            print("[OutputGuardrail] User authorized the action — proceeding to Actor.")
            return "action"
    return "planning"


def route_after_validator(state: SharedState) -> str:
    """
    Hierarchical routing after Validator execution.
    """
    if state.get("last_action_result", "").startswith("error: no step"):
        print(f"\n[LangGraph] Actor error detected — stopping.")
        return "stop"

    if state.get("task_status") == "completed":
        print("\n[LangGraph] Task completed — routing to HL Planner for final message.")
        return "finalize"

    if state.get("task_status") == "needs_revision":
        print("\n[LangGraph] Subgoal marked impossible or needs revision — routing to TaskDirector.")
        return "task_director"

    # MAX_STEPS safety — force finalize if agent is looping
    step_count = state.get("step_count", 0)
    if step_count >= MAX_STEPS:
        print(f"\n[LangGraph] MAX_STEPS ({MAX_STEPS}) reached — forcing finalize.")
        return "finalize"

    # Check if current subgoal needs escalation (3 failed attempts)
    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    
    if subgoals and current_index < len(subgoals):
        if subgoals[current_index].get("status") == "failed":
            print("\n[LangGraph] Escalating to TaskDirector for revision.")
            return "task_director"

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

    # Nodes
    graph.add_node("task_director",    task_director_node)
    graph.add_node("planner",          planner_node)
    graph.add_node("output_guardrail", output_guardrail_node)
    graph.add_node("actor",            actor_node)
    graph.add_node("validator",        validator_node)
    graph.add_node("ask_user",         ask_user_node)

    #Edges
    graph.add_edge(START, "task_director")

    graph.add_conditional_edges(
        "task_director",
        route_after_task_director,
        {"planning": "planner", "stop": END, "task_director": "task_director"}
    )

   
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "output_guardrail": "output_guardrail",
            "ask_user":         "ask_user",
            "stop":             END
        }
    )

    # output_guardrail → actor (PASS) or ask_user (HITL)
    graph.add_conditional_edges(
        "output_guardrail",
        route_after_output_guardrail,
        {"action": "actor", "ask_user": "ask_user"}
    )

    
    graph.add_conditional_edges(
        "ask_user",
        route_after_ask_user,
        {"action": "actor", "planning": "planner", "task_director": "task_director"}
    )

    graph.add_edge("actor", "validator")

    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "planning":     "planner",
            "task_director": "task_director",
            "finalize":     "task_director",
            "stop":         END
        }
    )
    return graph.compile()
