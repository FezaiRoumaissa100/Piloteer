from orchestration.state import SharedState
from tools.client_gemini import ask_llm_json
from prompts.validator_prompt import VALIDATOR_INSTRUCTIONS, validator_content_prompt


async def validator_node(state: SharedState) -> dict:
    step = state.get("current_step")
    if not step:
        print("[Validator] No step to validate.")
        return {"step_done": False}

    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    current_subgoal_desc = subgoals[current_index]["description"] if subgoals else state["user_task"]

    is_error     = state.get("last_action_is_error", False)
    action_result = state.get("last_action_result", "No result")

    prompt = validator_content_prompt(
        state["snapshot_before"],
        state["snapshot_after"],
        step,
        current_subgoal_desc,
        action_result,
        is_error=is_error
    )
    response = await ask_llm_json(
        prompt=prompt,
        system_prompt=VALIDATOR_INSTRUCTIONS,
        model="gemini-3.5-flash"
    )

    if isinstance(response, dict):
        step_success = response.get("step_success", False)
        subgoal_done = response.get("subgoal_done", False)
        reasoning = response.get("reasoning", "")
    else:
        step_success = False
        subgoal_done = False
        reasoning = "No response from Validator"

    print("\n[Validator] Reasoning :", reasoning)
    print(f"[Validator] Step {step.get('tool')} :{'SUCCESS' if step_success else 'FAILURE'}")
    print(f"[Validator] subgoal_done : {subgoal_done}")

    new_memory = state.get("memory", [])
    new_memory.append({
        "step_attempted": step,
        "step_success": step_success,
        "reasoning": reasoning
    })
    print("[validator] the memory :",new_memory)

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
            # A step succeeded, but subgoal is not done. Reset attempts since we are making progress.
            active_subgoal["attempts"] = 0
            active_subgoal["status"] = "in_progress"
            task_status = "in_progress"
            
        updated_subgoals[current_index] = active_subgoal
    else:
        task_status = "pending"

    return {
        "step_done": step_success,
        "subgoals": updated_subgoals,
        "current_subgoal_index": new_index,
        "task_status": task_status,
        "memory": new_memory
    }

