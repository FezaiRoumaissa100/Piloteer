import json
from orchestration.state import SharedState
from tools.client_gemini import ask_llm, ask_llm_json
from prompts.high_level_planner_prompt import (
    decompose_task_prompt, revise_subgoal_prompt, finalize_task_prompt,
    DECOMPOSE_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT, FINALIZE_SYSTEM_PROMPT
)
from utils.rag.retrieve import get_saas_context_auto

async def high_level_planner_node(state: SharedState) -> dict:
    user_task = state["user_task"]
    current_url = state.get("current_url", "")
    saas_context = get_saas_context_auto(user_task, current_url=current_url)
    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    task_status = state.get("task_status", "pending")

    # Mode 3: Finalize — all subgoals done or MAX_STEPS reached, generate narrative final message
    if task_status in ("completed", "impossible_subgoal") or state.get("step_count", 0) >= 30:
        print(f"[High-Level Planner] Mode Finalize — status={task_status}")
        memory = state.get("memory", [])
        prompt = finalize_task_prompt(user_task, subgoals, memory)
        response = await ask_llm_json(
            prompt=prompt,
            system_prompt=FINALIZE_SYSTEM_PROMPT,
            model="gemini-3.5-flash"
        )
        final_message = response.get("final_message", "Task completed.")
        print(f"[High-Level Planner] Final message: {final_message}")
        return {
            "final_message": final_message,
            "task_status": "finalized"
        }
    if not subgoals:
        print("[High-Level Planner] Mode ask Decomposition")
        prompt = decompose_task_prompt(user_task, saas_context)
        response = await ask_llm_json(
            prompt=prompt,
            system_prompt=DECOMPOSE_SYSTEM_PROMPT,
            model="gemini-3.5-flash"
        )

        mode = response.get("mode", "EXECUTE").upper()
        print(f"[High-Level Planner] Detected mode: {mode}")

        # QUESTION or IMPOSSIBLE → answer directly without browser execution
        if mode in ("QUESTION", "IMPOSSIBLE"):
            answer = response.get("answer", "I was unable to process this request.")
            print(f"[High-Level Planner] Direct answer: {answer}")
            return {
                "final_message": answer,
                "task_status": "finalized"
            }

        # EXECUTE → decompose into subgoals for browser execution
        raw_subgoals = response.get("subgoals", [])
        initialized_subgoals = []
        for i, sg in enumerate(raw_subgoals):
            initialized_subgoals.append({
                "id": i,
                "description": sg["description"],
                "mini_planner_hints": sg.get("mini_planner_hints", ""),
                "status": "pending",
                "attempts": 0,
                "failure_reason": None
            })

        print(f"[High-Level Planner] Generated ", initialized_subgoals)

        return {
            "subgoals": initialized_subgoals,
            "current_subgoal_index": 0,
            "task_status": "in_progress"
        }


    # Mode 2: Revision on Escalation
    print(f"[High-Level Planner] revising: #{current_index}")
    blocked_subgoal = subgoals[current_index]
    completed = [sg for sg in subgoals if sg["status"] == "completed"]
    remaining = [sg for sg in subgoals[current_index + 1:] if sg["status"] == "pending"]

    memory = state.get("memory", [])
    prompt = revise_subgoal_prompt(user_task, completed, blocked_subgoal, remaining, memory)
    
    response = await ask_llm_json(
        prompt=prompt,
        system_prompt=REVISE_SYSTEM_PROMPT,
        model="gemini-3.5-flash"
    )
    chain = response.get("reasoning", {})
    diagnosis = chain.get("3_decision", response.get("diagnosis", "No diagnosis provided"))
    print(f"[High-Level Planner] Diagnosis: {diagnosis}")
    new_subgoals_data = response.get("new_subgoals", [])

    # Case: REVISE determined task is impossible (empty new_subgoals)
    if not new_subgoals_data:
        print("[High-Level Planner] REVISE: task declared impossible — finalizing.")
        return {
            "task_status": "impossible_subgoal"
        }
    updated_subgoals = list(subgoals)[:current_index]
    for i, sg in enumerate(new_subgoals_data):
        desc = sg.get("description", str(sg))
        updated_subgoals.append({
            "id": current_index + i,
            "description": desc,
            "mini_planner_hints": sg.get("mini_planner_hints", ""),
            "status": "pending",
            "attempts": 0,
            "failure_reason": None
        })
    print(f"[High-Level Planner] Updated subgoals: {updated_subgoals}") 
    return {
        "subgoals": updated_subgoals
    }


