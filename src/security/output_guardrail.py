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
RISK_THRESHOLD  = 0.65   # higher = less sensitive, lower = more sensitive


async def output_guardrail_node(state: SharedState) -> dict:
    step = state.get("current_step") or {}
    tool = step.get("tool", "")

   
    if tool not in MONITORED_TOOLS:
        return {"security_verdict": "PASS", "security_score": 0.0}

    reasoning = state.get("last_planner_reasoning") or {}
    signal = " ".join(filter(None, [
        step.get("description", ""),
        reasoning.get("4_make_decision", ""),
    ]))

    print(f"\n[OutputGuardrail]  Checking: {signal[:120]}...")

    #Semantic similarity against the blacklist
    try:
        collection   = get_security_collection()
        query_vector = embed_text(signal)
        results      = collection.query(query_embeddings=[query_vector], n_results=1)
    except Exception as e:
        print(f"[OutputGuardrail]   ChromaDB error — defaulting to PASS: {e}")
        return {"security_verdict": "PASS", "security_score": 0.0}

    if not results["distances"] or not results["distances"][0]:
        return {"security_verdict": "PASS", "security_score": 0.0}

    distance   = results["distances"][0][0]
    risk_score = 1.0 / (1.0 + distance)
    matched    = results["documents"][0][0] if results["documents"][0] else "unknown"

    print(f"[OutputGuardrail]  Risk Score: {risk_score:.2f} | Closest intent: '{matched[:60]}'")

    #Verdict
    if risk_score >= RISK_THRESHOLD:
        print(f"[OutputGuardrail]   HITL triggered (score={risk_score:.2f})")
        question = (
            f" SECURITY ALERT — Risky action detected (risk score: {risk_score:.2f}/1.00)\n"
            f"The agent wants to: \"{step.get('description', 'unknown action')}\"\n"
            f"Type 'allow' to authorize or 'deny' to block this action."
        )
        return {
            "security_verdict":  "HITL",
            "security_score":    risk_score,
            "pending_question":  question,
        }

    print(f"[OutputGuardrail]  PASS (score={risk_score:.2f})")
    return {"security_verdict": "PASS", "security_score": risk_score}
