"""
security/output_guardrail.py
LangGraph node — Output Guardrail.
Sits between the Planner and the Actor.
Intercepts planned actions,
scores them semantically against the security blacklist,
and triggers HITL (Human-In-The-Loop) if the risk score is too high.
"""
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

    # Build the two signals independently
    step_signal    = step.get("description", "")
    subgoals       = state.get("subgoals", [])
    current_index  = state.get("current_subgoal_index", 0)
    subgoal_signal = subgoals[current_index]["description"] if subgoals and current_index < len(subgoals) else ""

    print(f"\n[OutputGuardrail]  Step   : {step_signal[:100]}")
    print(f"[OutputGuardrail]  Subgoal: {subgoal_signal[:100]}")

    try:
        collection = get_security_collection()

        def _score(text: str) -> tuple[float, str]:
            if not text:
                return 0.0, "unknown"
            vec     = embed_text(text)
            results = collection.query(query_embeddings=[vec], n_results=1)
            if not results["distances"] or not results["distances"][0]:
                return 0.0, "unknown"
            dist    = results["distances"][0][0]
            matched = results["documents"][0][0] if results["documents"][0] else "unknown"
            return 1.0 - dist, matched

        step_score,    step_matched    = _score(step_signal)
        subgoal_score, subgoal_matched = _score(subgoal_signal)

    except Exception as e:
        print(f"[OutputGuardrail]   ChromaDB error — defaulting to PASS: {e}")
        return {"security_verdict": "PASS", "security_score": 0.0}

    # Take the worst-case (max) score
    risk_score = max(step_score, subgoal_score)
    matched    = subgoal_matched if subgoal_score >= step_score else step_matched

    print(f"[OutputGuardrail]  Step score={step_score:.2f} | Subgoal score={subgoal_score:.2f} | Final={risk_score:.2f} | '{matched[:60]}'")

    if risk_score >= RISK_THRESHOLD:
        action_desc = step.get("description", "perform a sensitive action")
        print(f"[OutputGuardrail] HITL triggered (score={risk_score:.2f}) for action: {action_desc}")
        question = f"HITL:{action_desc}"
        return {
            "security_verdict": "HITL",
            "security_score":   risk_score,
            "pending_question": question,
        }

    print(f"[OutputGuardrail]  PASS (score={risk_score:.2f})")
    return {"security_verdict": "PASS", "security_score": risk_score}
