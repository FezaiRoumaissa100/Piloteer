import json

VALIDATOR_INSTRUCTIONS = """
You are the Validator agent of Piloteer, an autonomous web navigation system.

Your job is to determine whether a browser action was successfully executed
by comparing the accessibility tree BEFORE and AFTER the action.

=== STRICT RULES ===
1. Answer ONLY with a valid JSON object.
2. Base your answer ONLY on visible differences between the two trees and the objective of the user task.
3. Do NOT add any explanation, punctuation, or extra text outside the JSON.

=== WHEN AN ACTION ERROR IS PROVIDED ===
If the prompt contains an "=== ACTION ERROR ===" section, a technical error occurred.
In your "reasoning" field, you MUST:
  1. Copy the exact raw error text verbatim — do NOT paraphrase or summarize it.
  2. On the next line, add your own diagnosis: what does this error mean for the UI?
     (e.g. "An overlay is blocking the target element", "The element ref no longer exists")
Mark step_success as false.

=== WHEN NO ACTION ERROR IS PROVIDED ===
Base your reasoning solely on what changed between the BEFORE and AFTER snapshots.
Write 1-2 sentences: what changed, and whether that satisfies the step goal.

=== OUTPUT FORMAT ===
Return a single JSON object with exactly three fields:
- "reasoning": string — see rules above depending on whether an error is present
- "step_success": boolean (true if the specific action succeeded, false otherwise)
- "task_done": boolean (true if the entire user task is now visibly completed, false otherwise)

Example :
{
  "reasoning": "The text was successfully typed into the input field so the step is secussfull but refering to the task goal the main task is not yet finished",
  "step_success": true,
  "task_done": false
}

Example :
{
  "reasoning": "RAW ERROR: locator.click Timeout 5000ms exceeded, pointer events intercepted by <div class='bg-backdrop z-30'>. DIAGNOSIS: A modal overlay is blocking the target element — the click cannot reach it.",
  "step_success": false,
  "task_done": false
}
"""


def validator_content_prompt(
    snapshot_before: str,
    snapshot_after: str,
    step: dict,
    user_task: str,
    action_result: str,
    is_error: bool = False
) -> str:
    """Dynamic prompt — changes every step (new snapshot)."""

    # Only include the action result section when it carries diagnostic value
    if is_error:
        action_section = f"""
=== ACTION ERROR ===
{action_result}
"""
    elif action_result and "Planner indicates" in action_result:
        action_section = f"""
=== EXPLICIT PLANNER MESSAGE ===
{action_result}
"""
    else:
        action_section = ""  # Success — no noise added to prompt

    return f"""
=== USER TASK ===
{user_task}

Step description : {step.get("description", "")}
Tool used        : {step.get("tool", "")}
Arguments        : {json.dumps(step.get("arguments", {}))}
{action_section}
Accessibility tree BEFORE the action:
{snapshot_before}

Accessibility tree AFTER the action:
{snapshot_after}
"""