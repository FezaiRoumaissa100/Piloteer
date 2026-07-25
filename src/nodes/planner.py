from orchestration.state import SharedState
from tools.client_gemini import ask_llm_json
from prompts.planner_prompt import planner_system_prompt, planner_content_prompt
from utils.context.tree_pruner import prune_snapshot


async def planner_node(state: SharedState) -> dict:
    subgoals      = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    current_subgoal_desc = subgoals[current_index]["description"] if subgoals else state["user_task"]
    current_hints        = subgoals[current_index].get("mini_planner_hints", "") if subgoals else ""
    
    saas_context = state.get("saas_context", "")
    raw_snapshot = state["snapshot_after"]
    memory       = state.get("memory", [])

    snapshot = prune_snapshot(raw_snapshot) if raw_snapshot else ""

   
    memory_str = "No past actions yet."
    if memory:
        memory_str = "\n".join(
            f"Step: {m['step_attempted'].get('tool')} - Success: {m['step_success']} - Validator Reasoning: {m['reasoning']}"
            for m in memory
        )

    # Build prompts
    system_prompt = planner_system_prompt(snapshot, current_subgoal_desc, saas_context)
    prompt        = planner_content_prompt(snapshot, current_subgoal_desc, memory_str, hints=current_hints)

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

