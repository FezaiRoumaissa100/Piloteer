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
        chain = response.get("reasoning", {})
        if isinstance(chain, dict) and chain:
            target   = chain.get("1_identify_target", "")
            evidence = chain.get("2_scan_tree", "")
            critique = chain.get("3_critique", "")
            reasoning = f"Target: {target}\nEvidence: {evidence}\nCritique: {critique}"
        else:
            reasoning = chain or "No reasoning provided."
    else:
        step_success = False
        subgoal_done = False
        reasoning = "No valid response from Validator"

    print("\n[Validator] response", response)

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

    # Send real-time feedback to chat
    channel = state.get("channel")
    if channel:
        if subgoal_done:
            await channel.send(f"Subgoal completed: {current_subgoal_desc}", "success")
        elif not step_success:
            await channel.send(f"Step failed, retrying... ({critique})", "error")

    return {
        "step_done": step_success,
        "subgoals": updated_subgoals,
        "current_subgoal_index": new_index,
        "task_status": task_status,
        "memory": new_memory
    }


