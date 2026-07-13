from orchestration.state import SharedState
from tools.llm_client import ask_llm_json
from prompts.validator_prompt import VALIDATOR_INSTRUCTIONS, validator_content_prompt


async def validator_node(state: SharedState) -> dict:
    step = state.get("current_step")
    if not step:
        print("[Validator] No step to validate.")
        return {"step_done": False}

    prompt = validator_content_prompt(
        state["snapshot_before"], 
        state["snapshot_after"], 
        step, 
        state["user_task"]
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
        reasoning = "Failed to parse validator JSON."

    print(f"\n[Validator] Reasoning : {reasoning}")
    print(f"[Validator] Step {step.get('tool')} → {'SUCCESS' if step_success else 'FAILURE'}")
    print(f"[Validator] task_done : {task_done}")

    new_memory = state.get("memory", [])
    new_memory.append({
        "step_attempted": step,
        "step_success": step_success,
        "reasoning": reasoning
    })

    return {
        "step_done": step_success,
        "task_done": task_done,
        "memory": new_memory
    }
