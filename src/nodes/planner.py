"""
planner.py — Piloteer
Planner agent node for LangGraph.

Receives the current page snapshot + user task,
calls Gemini, and returns the SINGLE NEXT step to execute.
"""

from orchestration.state import SharedState
from tools.llm_client import ask_llm_json
from prompts.planner_prompt import planner_system_prompt, planner_content_prompt


async def planner_node(state: SharedState) -> dict:
    """
    Planner agent — LangGraph node.

    Reads from state:
      - user_task, saas_context, snapshot_after

    Writes to state:
      - current_step  (single step dict or None)
      - step_done     (reset to False for new step)
    """

    task         = state["user_task"]
    saas_context = state["saas_context"]
    snapshot     = state["snapshot_after"]
    memory       = state.get("memory", [])

    # Format memory into string
    memory_str = "No past actions yet."
    if memory:
        memory_str = "\n".join(
            f"Step: {m['step_attempted'].get('tool')} - Success: {m['step_success']} - Validator Reasoning: {m['reasoning']}"
            for m in memory
        )

    # Build prompts
    system_prompt = planner_system_prompt(snapshot, task, saas_context)
    prompt        = planner_content_prompt(snapshot, task, memory_str)

    # Call Gemini — returns {"reasoning": ..., "step": ...}
    response = await ask_llm_json(
        prompt=prompt,
        system_prompt=system_prompt,
        model="gemini-2.5-flash"
    )

    # Extract fields
    if isinstance(response, dict):
        reasoning = response.get("reasoning", "")
        step      = response.get("step", None)
    else:
        reasoning = ""
        step      = None

    print(f"\n[Planner] Reasoning : {reasoning}")
    print(f"[Planner] Next step : {step}")

    return {
        "current_step": step,
        "step_done":    False,
        "error":        None
    }

