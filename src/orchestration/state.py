from typing import TypedDict, Dict, Any, Optional


# ─────────────────────────────────────────────
#  Shared State — minimal pipeline
#  Planner → Actor → Validator (loop)
# ─────────────────────────────────────────────

class SharedState(TypedDict):
    # Task context (fixed at start)
    user_task:    str
    saas_context: str

    # Browser state
    current_url:     str
    snapshot_before: Optional[str]
    snapshot_after:  Optional[str]

    # Current step — 1 step at a time from the Planner
    current_step: Optional[Dict]   # {"tool": ..., "arguments": ..., "description": ...}

    # Results
    last_action_result: Optional[str]
    step_done:          bool        # set by Validator
    memory:             list[dict]  # history of steps and validator feedback

    # Termination
    task_done: bool                 # set by Validator when task is complete
    error:     Optional[str]


def initiate_state(user_task: str, saas_context: str) -> SharedState:
    return SharedState(
        user_task=user_task,
        saas_context=saas_context,

        current_url="",
        snapshot_before=None,
        snapshot_after=None,

        current_step=None,

        last_action_result=None,
        step_done=False,
        memory=[],

        task_done=False,
        error=None
    )