import json
from orchestration.state import SharedState
from tools.client_gemini import ask_llm, ask_llm_json
from prompts.high_level_planner_prompt import decompose_task_prompt, revise_subgoal_prompt, DECOMPOSE_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT
from utils.rag.retrieve import get_saas_context

async def high_level_planner_node(state: SharedState) -> dict:
    user_task = state["user_task"]
    saas_context = get_saas_context(user_task)
    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)

    # Mode 1: Decompose Task into Subgoals
    if not subgoals:
        print("[High-Level Planner] Mode ask Decomposition")
        prompt = decompose_task_prompt(user_task, saas_context)
        response = await ask_llm_json(
            prompt=prompt,
            system_prompt=DECOMPOSE_SYSTEM_PROMPT,
            model="gemini-3.5-flash"
          
        )
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

        print(f"[High-Level Planner] Generated ",initialized_subgoals)

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

    prompt = revise_subgoal_prompt(user_task, completed, blocked_subgoal, remaining)
    
    response = await ask_llm_json(
        prompt=prompt,
        system_prompt=REVISE_SYSTEM_PROMPT,
         model="gemini-3.5-flash"
       
    )
    diagnosis = response.get("diagnosis", "No diagnosis provided")
    print(f"[High-Level Planner] Diagnosis: {diagnosis}")
    new_subgoals_data = response.get("new_subgoals", [])
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


