from orchestration.state import SharedState
from tools.client_gemini import ask_llm_json
from prompts.planner_prompt import planner_system_prompt, planner_content_prompt
from utils.tree_pruner import prune_snapshot


async def planner_node(state: SharedState) -> dict:
    """
    Planner agent — LangGraph node.

    Reads from state:
      - user_task, saas_context, snapshot_after

    Writes to state:
      - current_step  (single step dict or None)
      - step_done     (reset to False for new step)
    """

    subgoals      = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    current_subgoal_desc = subgoals[current_index]["description"] if subgoals else state["user_task"]
    
    saas_context = state["saas_context"]
    raw_snapshot = state["snapshot_after"]
    memory       = state.get("memory", [])

    # Prune snapshot before sending to LLM (Level-1 tree pruning)
    snapshot = prune_snapshot(raw_snapshot) if raw_snapshot else ""

   
    memory_str = "No past actions yet."
    if memory:
        memory_str = "\n".join(
            f"Step: {m['step_attempted'].get('tool')} - Success: {m['step_success']} - Validator Reasoning: {m['reasoning']}"
            for m in memory
        )

    # Build prompts
    system_prompt = planner_system_prompt(snapshot, current_subgoal_desc, saas_context)
    prompt        = planner_content_prompt(snapshot, current_subgoal_desc, memory_str)

    # Call Gemini
    response = await ask_llm_json(
        prompt=prompt,
        system_prompt=system_prompt,
        model="gemini-3.5-flash"
    )

    # Extract fields
    if isinstance(response, dict):
        reasoning = response.get("reasoning", "")
        step      = response.get("step", None)
    else:
        reasoning = ""
        step      = None

    print("\n[Planner] Reasoning :", reasoning)
    print("[Planner] Next step : ",step)

    return {
        "current_step": step,
        "step_done":    False,
        "error":        None
    }

