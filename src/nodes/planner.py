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
    user_answer  = state.get("user_answer") or ""

    snapshot = prune_snapshot(raw_snapshot) if raw_snapshot else ""

   
    memory_str = "No past actions yet."
    if memory:
        memory_str = "\n".join(
            f"Step: {m['step_attempted'].get('tool')} - Success: {m['step_success']} - Validator Reasoning: {m['reasoning']}"
            for m in memory
        )

    # Build prompts
    system_prompt = planner_system_prompt(snapshot, current_subgoal_desc, saas_context)
    prompt        = planner_content_prompt(snapshot, current_subgoal_desc, memory_str, hints=current_hints, user_answer=user_answer)

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
    print("[Planner] Next step : ", step)

    # Send step description to chat interface in real time
    channel = state.get("channel")
    if channel and step:
        tool = step.get("tool", "")
        desc = step.get("description", "")
        if tool == "ask_user":
            pass  # ask_user_node handles its own message
        elif tool == "browser_finish_subgoal":
            await channel.send("Verifying subgoal completion...", "agent")
        elif desc:
            await channel.send(desc, "agent")

    return {
        "current_step": step,
        "step_done":    False,
        "error":        None,
        "user_answer":  None,
    }


