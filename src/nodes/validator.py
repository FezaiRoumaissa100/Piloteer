from orchestration.state import SharedState
from tools.client_gemini import ask_llm_json
from prompts.validator_prompt import VALIDATOR_INSTRUCTIONS, validator_content_prompt


async def validator_node(state: SharedState) -> dict:
    step = state.get("current_step")
    if not step:
        print("[Validator] No step to validate.")
        return {"step_done": False}

    is_error     = state.get("last_action_is_error", False)
    action_result = state.get("last_action_result", "No result")

    prompt = validator_content_prompt(
        state["snapshot_before"],
        state["snapshot_after"],
        step,
        state["user_task"],
        action_result,
        is_error=is_error
    )
    response = await ask_llm_json(
        prompt=prompt,
        system_prompt=VALIDATOR_INSTRUCTIONS,
        model="gemini-2.5-flash"
    )

    if isinstance(response, dict):
        step_success = response.get("step_success", False)
        task_done = response.get("task_done", False)
        reasoning = response.get("reasoning", "")
    else:
        step_success = False
        task_done = False
        reasoning = "No response from Validator"

    print("\n[Validator] Reasoning :", reasoning)
    print(f"[Validator] Step {step.get('tool')} :{'SUCCESS' if step_success else 'FAILURE'}")
    print(f"[Validator] task_done : {task_done}")

    new_memory = state.get("memory", [])
    new_memory.append({
        "step_attempted": step,
        "step_success": step_success,
        "reasoning": reasoning
    })
    print("[validator] the memory :",new_memory)

    return {
        "step_done": step_success,
        "task_done": task_done,
        "memory": new_memory
    }
