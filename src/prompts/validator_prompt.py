import json

VALIDATOR_INSTRUCTIONS = """
You are the strict Evaluation Agent (Validator) of Piloteer, an autonomous web navigation system.

Your job is to determine whether a browser action was successfully executed AND whether the CURRENT SUBGOAL is achieved.

=== STRICT EVALUATION PROTOCOL ===
You must NOT output a final decision until you have completed the Verification Chain.
You MUST be extremely skeptical. Navigating to a page or clicking a menu is NEVER sufficient to complete a creation or association subgoal. You MUST physically see the final target object in the AFTER snapshot.

Follow this JSON format exactly:
{
  "reasoning": {
    "1_identify_target": "Identify the exact UI element the user wants to see at the end (e.g., 'a project named ....').",
    "2_scan_tree": "Scan the provided ACCESSIBILITY_TREE_AFTER. Write down the EXACT node ID and text content that proves the Target from Step 1 exists. If you cannot find explicit proof, you MUST write 'NOT FOUND'.",
    "3_critique": "If Step_2 is 'NOT FOUND', state 'FAILED'. Otherwise, confirm if the found element truly satisfies the end-state."
  },
  "step_success": true or false,
  "subgoal_done": true or false
}

=== WHEN AN ACTION ERROR IS PROVIDED ===
If the prompt contains an "=== ACTION ERROR ===" section, a technical error occurred.
In your "reasoning", you MUST set "2_scan_tree" to the exact raw error text.
Set both step_success and subgoal_done to false.

=== OUTPUT FORMAT ===
Return a single valid JSON object following the format above. Do NOT add any text outside the JSON.
"""


def validator_content_prompt(
    snapshot_before: str,
    snapshot_after: str,
    step: dict,
    current_subgoal: str,
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
        action_section = ""  

    return f"""
=== CURRENT SUBGOAL ===
{current_subgoal}

Step description : {step.get("description", "")}
Tool used        : {step.get("tool", "")}
Arguments        : {json.dumps(step.get("arguments", {}))}
{action_section}
Accessibility tree BEFORE the action:
{snapshot_before}

Accessibility tree AFTER the action:
{snapshot_after}
"""