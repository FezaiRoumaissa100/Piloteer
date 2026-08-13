from typing import TypedDict, Dict, Any, Optional
import uuid
from datetime import datetime, timezone


class SharedState(TypedDict):
    # Task context 
    user_task:    str
    saas_context: str
    channel:      Any 

    # Hierarchical Planning
    subgoals:              list[dict]
    current_subgoal_index: int
    task_status:           str
    step_count:            int           

    # Browser state
    current_url:     str
    snapshot: Optional[str]
    screenshot: Optional[str]

    # Telemetry & Logging
    trace_id:           Optional[str]

    #step infos
    current_step: Optional[Dict]   
    last_action_result:   Optional[str]
    last_action_is_error: bool
    step_done:            bool
    memory:               list[dict]

    # ask_user
    pending_question: Optional[str] 
    user_answer:      Optional[str]   

    # Termination
    error:         Optional[str]
    final_message: Optional[str]
    execution_mode: Optional[str]
    conversation_history: list[dict]  # [{"user": ..., "agent": ...}]

    # Security Guardrails
    security_verdict:       Optional[str]    # "PASS" | "HITL"
    security_score:         Optional[float]  # 0.0 to 1.0
    last_planner_reasoning: Optional[dict]   # Planner reasoning dict (enriches security signal)


def initiate_state(user_task: str, saas_context: str, channel=None) -> SharedState:
    return SharedState(
        user_task=user_task,
        saas_context=saas_context,
        channel=channel,

        subgoals=[],
        current_subgoal_index=0,
        task_status="pending",
        step_count=0,

        current_url="",
        snapshot=None,
        screenshot=None,

        trace_id=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",

        current_step=None,

        last_action_result=None,
        last_action_is_error=False,
        step_done=False,
        memory=[],

        pending_question=None,
        user_answer=None,

        error=None,
        final_message=None,
        execution_mode="EXECUTE",
        conversation_history=[],

        security_verdict=None,
        security_score=None,
        last_planner_reasoning=None,
    )