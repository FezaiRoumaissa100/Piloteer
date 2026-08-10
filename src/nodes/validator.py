from orchestration.state import SharedState
from tools.client_gemini import ask_llm_json
from prompts.validator_prompt import VALIDATOR_INSTRUCTIONS, validator_content_prompt
from loggings.scripts.logger import log_event
import asyncio
from datetime import datetime, timezone


async def validator_node(state: SharedState) -> dict:
    timestamp_start = datetime.now(timezone.utc).isoformat()
    
    step = state.get("current_step")
    if not step:
        return {"step_done": False}

    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    current_subgoal_desc = subgoals[current_index]["description"] if subgoals else state["user_task"]

    is_error      = state.get("last_action_is_error", False)
    action_result = state.get("last_action_result", "No result")

    if state.get("task_status") == "needs_revision" and action_result.startswith("The Planner has determined"):
        reason_line = [l for l in action_result.splitlines() if l.startswith("Reason:")]
        reason = reason_line[0].replace("Reason: ", "") if reason_line else "Data not found."

        new_memory = state.get("memory", [])
        new_memory.append({"action_summary": f"Subgoal impossible: {reason}", "success": False})

        updated_subgoals = list(subgoals)
        if subgoals and current_index < len(updated_subgoals):
            active_subgoal = updated_subgoals[current_index].copy()
            active_subgoal["status"] = "impossible"
            active_subgoal["failure_reason"] = reason
            updated_subgoals[current_index] = active_subgoal
            new_index = current_index + 1
        else:
            new_index = current_index

        return {
            "step_done": False,
            "subgoals": updated_subgoals,
            "current_subgoal_index": new_index,
            "task_status": "needs_revision",
            "memory": new_memory
        }
   

    current_url = state.get("current_url", "")
    prompt = validator_content_prompt(
        state["snapshot"],
        step,
        current_subgoal_desc,
        action_result,
        current_url=current_url,
        is_error=is_error
    )
    response, usage = await ask_llm_json(
        prompt=prompt,
        system_prompt=VALIDATOR_INSTRUCTIONS,
        model="gemini-3.5-flash"
    )

    if isinstance(response, dict):
        step_success  = response.get("step_success", False)
        subgoal_done  = response.get("subgoal_done", False)
        memory_entry  = response.get("memory_entry", "")
        chain = response.get("reasoning", {})
        if isinstance(chain, dict) and chain:
            reasoning = (
                f"Subgoal: {chain.get('1_analyze_subgoal', '')}\n"
                f"Step: {chain.get('2_analyze_step_result', '')}\n"
                f"State: {chain.get('3_analyze_current_state', '')}\n"
                f"Decision: {chain.get('4_verification', '')}"
            )
        else:
            reasoning = str(chain) or "No reasoning provided."
        if not memory_entry:
            memory_entry = reasoning
    else:
        step_success  = False
        subgoal_done  = False
        reasoning     = "No valid response from Validator"
        memory_entry  = "No valid response from Validator"



    new_memory = state.get("memory", [])
    new_memory.append({
        "action_summary": memory_entry,
        "success": step_success,
    })

    updated_subgoals = list(subgoals)
    new_index = current_index

    if subgoals and current_index < len(updated_subgoals):
        active_subgoal = updated_subgoals[current_index].copy()

        if subgoal_done:
            active_subgoal["status"] = "completed"
            new_index += 1
            if new_index >= len(updated_subgoals):
                task_status = "completed"
            else:
                task_status = "in_progress"
        elif not step_success:
            active_subgoal["attempts"] += 1
            active_subgoal["failure_reason"] = reasoning
            active_subgoal["status"] = "failed" if active_subgoal["attempts"] >= 3 else "in_progress"
            task_status = "in_progress"
        else:
            active_subgoal["status"] = "in_progress"
            task_status = "in_progress"
            
        updated_subgoals[current_index] = active_subgoal
    else:
        task_status = "pending"



    step_count = state.get("step_count", 0) + 1

   
    asyncio.create_task(log_event(
        state=state, node_name="validator",
        timestamp_start=timestamp_start, gen_ai_model=usage.get("model") if isinstance(usage, dict) else None,
        gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None, 
        gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
        payload=response
    ))

    return {
        "step_done": step_success,
        "subgoals": updated_subgoals,
        "current_subgoal_index": new_index,
        "task_status": task_status,
        "memory": new_memory,
        "step_count": step_count
    }


