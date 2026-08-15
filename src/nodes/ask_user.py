from orchestration.state import SharedState


async def ask_user_node(state: SharedState) -> dict:
    
    security_verdict = state.get("security_verdict")
    # Use pending_question if set (HITL path), else extract from planner step
    pending = state.get("pending_question")
    if pending:
        question = pending
    else:
        current_step = state.get("current_step") or {}
        question = current_step.get("arguments", {}).get("question", "Please provide the required information.")

    
    channel = state.get("channel")
    if channel:
        answer = await channel.ask(question)
    else:
        print(f"\n[ask_user] {question}")
        answer = input("You : ").strip()

    print(f"[ask_user] Received: '{answer}'")

    
    updates = {
        "user_answer": answer,
        "pending_question": None,
    }
    
    if security_verdict == "HITL" and answer.lower() != "allow":
        print("[ask_user] User denied the action ...aborting task .")
        step = state.get("current_step") or {}
        memory = state.get("memory") or []
        memory.append({
            "success": False,
            "action_summary": (
                f"FATAL SECURITY DENIAL: The action '{step.get('description', '')}' "
                f"was blocked by the human supervisor. The entire task is deemed unsafe and impossible."
            )
        })
        updates["memory"] = memory
        updates["task_status"] = "task_impossible"
        updates["security_verdict"] = None

    return updates
