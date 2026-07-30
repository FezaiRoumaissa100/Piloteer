import asyncio
from mcp import ClientSession
from orchestration.state import SharedState
from tools.mcp_client import get_snapshot, wait_for

# Tools that trigger navigation :need extra wait before snapshot
NAVIGATION_TOOLS = {"browser_click", "browser_navigate", "browser_press_key"}


def make_actor_node(session: ClientSession):
    """
    Factory that captures the MCP session and returns the actor node.
    Called once in graph.py — the session lives for the whole pipeline.
    """

    async def actor_node(state: SharedState) -> dict:
        """
        Actor agent — LangGraph node.

        Reads from state:
          - current_step

        Writes to state:
          - snapshot_before, snapshot_after, last_action_result, last_action_is_error
        """

        step = state["current_step"]

        if not step:
            print("[Actor] No step to execute.")
            return {
                "snapshot_before":    None,
                "snapshot_after":     None,
                "last_action_result": "error: no step"
            }

        print("[Actor] Executing:", step.get('description', ''))
        print("[Actor] Tool:", step['tool'], "| Args:", step['arguments'])
        snapshot_before = await get_snapshot(session)

        arguments = step.get("arguments", {}).copy()

        if step["tool"] == "browser_finish_subgoal":
            print("[Actor] Intercepting browser_finish_subgoal...")
            action_result = "The Planner indicates the current subgoal is complete. Validator, please perform a final double-check by analyzing the snapshots."
            snapshot_after = snapshot_before
            is_error = False

        elif step["tool"] == "ask_user":
            question = step.get("arguments", {}).get("question", "Please provide a value.")
            field    = step.get("arguments", {}).get("field", "")
            print(f"\n[Agent]  {question}")
            return {
                "pending_question": question,
                "current_step":     step,
                "snapshot_before":  snapshot_before,
                "snapshot_after":   snapshot_before,
                "last_action_result":   f"Waiting for user input on field: {field}",
                "last_action_is_error": False,
            }

        else:
            result = await session.call_tool(
                name=step["tool"],
                arguments=arguments
            )
           
            if step["tool"] in NAVIGATION_TOOLS:
                print("[Actor] Waiting for page to stabilize...")
                await wait_for(session, time=3)
        
            snapshot_after = await get_snapshot(session)
            is_error = getattr(result, "isError", False)
            action_result = result.content[0].text if result.content else "Command executed with no text output."
            
        print("[Actor] Result:", action_result)

        return {
            "snapshot_before":      snapshot_before,
            "snapshot_after":       snapshot_after,
            "last_action_result":   action_result,
            "last_action_is_error": is_error
        }

    return actor_node
