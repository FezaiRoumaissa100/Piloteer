from orchestration.state import SharedState
from tools.client_gemini import ask_llm_json
from prompts.planner_prompt import planner_system_prompt, planner_content_prompt
from loggings.scripts.logger import log_event
import asyncio
from datetime import datetime, timezone


async def planner_node(state: SharedState) -> dict:
    timestamp_start = datetime.now(timezone.utc).isoformat()
    
    subgoals      = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    current_subgoal_desc = subgoals[current_index]["description"] if subgoals else state["user_task"]
    current_hints        = subgoals[current_index].get("mini_planner_hints", "") if subgoals else ""
    saas_context    = state.get("saas_context", "")
    raw_snapshot    = state["snapshot"]
    memory          = state.get("memory", [])
    user_answer     = state.get("user_answer") or ""
    execution_mode  = state.get("execution_mode", "EXECUTE")

    snapshot = raw_snapshot

    memory_str = "No past actions yet."
    if memory:
        memory_str = "\n".join(
            f"- {'OK' if m.get('success') else 'FAIL'} {m.get('action_summary', 'No summary.')}"
            for m in memory
        )

    # Build prompts
    system_prompt = planner_system_prompt(execution_mode=execution_mode)
    prompt        = planner_content_prompt(saas_info=saas_context, snapshot=snapshot, current_subgoal=current_subgoal_desc, memory_str=memory_str, hints=current_hints, user_answer=user_answer)

    # Call Gemini
    response, usage = await ask_llm_json(
        prompt=prompt,
        system_prompt=system_prompt
    )

    
    if isinstance(response, dict):
        reasoning = response.get("reasoning", "")
        step      = response.get("step", None)
    else:
        reasoning = ""
        step      = None

    # Fallback guard: 
    if not step:
        step = {
            "tool": "browser_wait_for",
            "arguments": {"time": 3},
            "description": "Wait  for the page to load before retrying"
        }
    else:
        print(f"\n[Planner] Reasoning: {reasoning}")
        print(f"[Planner] Chosen Action: {step.get('tool')} - {step.get('arguments')}")


    asyncio.create_task(log_event(
        state=state, node_name="planner",
        timestamp_start=timestamp_start, gen_ai_model=usage.get("model")if isinstance(usage, dict) else None,
        gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
        gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
        payload={"reasoning": reasoning, "step": step}
    ))

    return {
        "current_step":           step,
        "step_done":              False,
        "error":                  None,
        "user_answer":            None,
        "timestamp_start":        timestamp_start,
        "last_planner_reasoning": reasoning if isinstance(reasoning, dict) else {},
    }