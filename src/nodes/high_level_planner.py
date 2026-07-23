import json
from orchestration.state import SharedState
from tools.client_gemini import ask_llm, ask_llm_json
from prompts.high_level_planner_prompt import decompose_task_prompt, revise_subgoal_prompt, DECOMPOSE_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT

async def high_level_planner_node(state: SharedState) -> dict:
    """
    High-Level Planner Agent — LangGraph node.
    Mode 1: Decompose global task (if subgoals is empty)
    Mode 2: Revise blocked subgoal (if called on escalation)
    """

    user_task = state["user_task"]
    saas_context = state["saas_context"]
    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)


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
                "status": "pending",
                "attempts": 0,
                "failure_reason": None
            })

        print(f"[High-Level Planner] Generated {len(initialized_subgoals)} subgoals:")
        for sg in initialized_subgoals:
            print(f"   #{sg['id']} → {sg['description']}")
        return {
            "subgoals": initialized_subgoals,
            "current_subgoal_index": 0,
            "task_status": "in_progress"
        }

    # Mode 2: Revision on Escalation
    print(f"[High-Level Planner] Mode 2: Revising Blocked Subgoal #{current_index}")
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
    
    scope = response.get("scope", "local")
    print(f"[High-Level Planner] Scope: {scope}")
    
    new_description = response.get("revised_current", blocked_subgoal["description"])
    # Fallback for old prompt structure just in case
    if "revised_description" in response and "revised_current" not in response:
        new_description = response["revised_description"]
        
    print(f"[High-Level Planner] Revised current: {new_description}")

    # Update the blocked subgoal in place
    updated_subgoals = list(subgoals) 
    updated_subgoals[current_index] = {
        "id": blocked_subgoal["id"],
        "description": new_description,
        "status": "pending",
        "attempts": 0,
        "failure_reason": None
    }

    if scope == "downstream" and "revised_downstream" in response:
        print("[High-Level Planner] Scope is downstream. Replacing remaining subgoals.")
        # Truncate the list to remove old downstream subgoals
        updated_subgoals = updated_subgoals[:current_index + 1]
        
        # Append the new downstream subgoals
        new_downstream = response.get("revised_downstream", [])
        for i, desc in enumerate(new_downstream):
            updated_subgoals.append({
                "id": blocked_subgoal["id"] + i + 1,
                "description": desc,
                "status": "pending",
                "attempts": 0,
                "failure_reason": None
            })

    return {
        "subgoals": updated_subgoals
    }
