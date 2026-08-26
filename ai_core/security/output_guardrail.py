import json
from orchestration.state import SharedState
from security.embedder import get_security_collection, embed_text


MONITORED_TOOLS = {"browser_click", "browser_navigate"}
RISK_THRESHOLD  = 0.75


async def output_guardrail_node(state: SharedState) -> dict:
    step = state.get("current_step") or {}
    tool = step.get("tool", "")

    if tool not in MONITORED_TOOLS:
        return {"security_verdict": "PASS", "security_score": 0.0}

    # Score only the planned action — no subgoal signal
    action_description = step.get("description", "")

    print(f"\n[OutputGuardrail]  Step : {action_description[:120]}")

    try:
        collection = get_security_collection()

        if not action_description:
            return {"security_verdict": "PASS", "security_score": 0.0}

        vec     = embed_text(action_description)
        results = collection.query(query_embeddings=[vec], n_results=1)

        if not results["distances"] or not results["distances"][0]:
            return {"security_verdict": "PASS", "security_score": 0.0}

        dist    = results["distances"][0][0]
        matched = results["documents"][0][0] if results["documents"][0] else "unknown"
        risk_score = 1.0 - dist

    except Exception as e:
        print(f"[OutputGuardrail]  ChromaDB error — defaulting to PASS: {e}")
        return {"security_verdict": "PASS", "security_score": 0.0}

    print(f"[OutputGuardrail]  Score={risk_score:.2f} | Matched='{matched[:60]}'")

    if risk_score >= RISK_THRESHOLD:
        print(f"[OutputGuardrail]  HITL triggered (score={risk_score:.2f})")

        # Natural-language message readable by both the chat UI and the TTS voice
        action_label = action_description or tool
        hitl_message = (
            f"The agent wants to execute this action: \"{action_label}\". "
            f"It may be irreversible and risky. Do you allow it?"
        )

        return {
            "security_verdict": "HITL",
            "security_score":   risk_score,
            "pending_question": f"HITL:{hitl_message}",
        }

    print(f"[OutputGuardrail]  PASS (score={risk_score:.2f})")
    return {"security_verdict": "PASS", "security_score": risk_score}
