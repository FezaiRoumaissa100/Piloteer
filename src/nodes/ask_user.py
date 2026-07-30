from orchestration.state import SharedState


async def ask_user_node(state: SharedState) -> dict:
    # Read question directly from current_step — Actor is bypassed for ask_user
    current_step = state.get("current_step") or {}
    question = current_step.get("arguments", {}).get("question", "Please provide the required information.")

    channel = state.get("channel")
    if channel:
        answer = await channel.ask(question)
    else:
        print(f"\n[ask_user] {question}")
        answer = input("You : ").strip()

    print(f"[ask_user] Received: '{answer}'")

    return {
        "user_answer":      answer,
        "pending_question": None,
    }
