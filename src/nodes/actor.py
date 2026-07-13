"""
actor.py — Piloteer
Actor agent node for LangGraph.

Executes the single current_step from state using the MCP session.
Zero reasoning — just dispatches the exact tool call.
"""

import asyncio
from mcp import ClientSession
from orchestration.state import SharedState
from tools.mcp_client import get_snapshot, wait_for

# Tools that trigger navigation — need extra wait before snapshot
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
          - snapshot_before, snapshot_after, last_action_result
        """

        step = state["current_step"]

        # Guard: Planner returned no step (task_done or error)
        if not step:
            print("[Actor] No step to execute (task_done or no valid action).")
            return {
                "snapshot_before":    None,
                "snapshot_after":     None,
                "last_action_result": "error: no step"
            }

        print(f"\n[Actor] Executing: {step.get('description', '')}")
        print(f"        Tool: {step['tool']} | Args: {step['arguments']}")

        # 1. Capture snapshot BEFORE
        snapshot_before = await get_snapshot(session)

        # 2. Execute the MCP tool call
        arguments = step["arguments"].copy()
        if step["tool"] == "browser_type":
            arguments["slowly"] = True  # character-by-character for visual demo

        result = await session.call_tool(
            name=step["tool"],
            arguments=arguments
        )

        # 3. Wait for page to stabilize if action triggers navigation
        if step["tool"] in NAVIGATION_TOOLS:
            print("[Actor] Waiting for page to stabilize...")
            await wait_for(session, time=1)

        # 4. Capture snapshot AFTER
        snapshot_after = await get_snapshot(session)

        action_result = result.content[0].text if result.content else "done"
        print(f"[Actor] Result: {action_result[:120]}...")

        return {
            "snapshot_before":    snapshot_before,
            "snapshot_after":     snapshot_after,
            "last_action_result": action_result
        }

    return actor_node
