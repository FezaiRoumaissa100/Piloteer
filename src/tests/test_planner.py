"""
test_planner.py — Piloteer / tests
Tests the Planner agent end-to-end:
  1. Opens a real browser via MCP
  2. Navigates to Google
  3. Gets the accessibility tree (snapshot)
  4. Feeds it to the Planner with a user task + SaaS context
  5. Prints the generated execution plan
"""

import sys
import os
import asyncio
import json

# Allow imports from src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from nodes.planner import planner_node


# ─────────────────────────────────────────────
#  Test inputs
# ─────────────────────────────────────────────

USER_TASK = "Search for 'Playwright web automation' on Google and choose result"

SAAS_CONTEXT = """
Google Search is a web search engine.
The home page has a search bar in the center.
You type your query and press Enter or click the 'Google Search' button.
Results appear on the next page as a list of links.
"""


# ─────────────────────────────────────────────
#  Test function
# ─────────────────────────────────────────────

async def test_planner():
    print("\n" + "="*60)
    print("PILOTEER — Planner Agent Test")
    print("="*60)

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("\n[1/4] MCP server connected")

            # Step 1: Navigate to Google
            await navigate(session, "https://www.google.com")
            print("[2/4] Navigated to Google")

            # Step 2: Get the accessibility tree of the current page
            snapshot = await get_snapshot(session)
            print("[3/4] Accessibility tree captured")
            print("\n--- SNAPSHOT (first 800 chars) ---")
            print(snapshot[:800])
            print("...")

            # Step 3: Build the state
            state = initiate_state(
                user_task=USER_TASK,
                saas_context=SAAS_CONTEXT
            )
            # Inject the snapshot as if the Actor had just navigated
            state["snapshot_after"] = snapshot

            print("\n[4/4] Calling Planner agent...")
            print(f"    Task: {USER_TASK}")

            # Step 4: Call the Planner
            result = await planner_node(state)

            # Step 5: Display the plan
            plan = result.get("current_plan", [])

            print("\n" + "="*60)
            print("PLANNER OUTPUT — Execution Plan")
            print("="*60)

            if not plan:
                print("No plan generated — check Gemini API key or response format.")
            else:
                for step in plan:
                    print(f"\n  Step {step.get('step', '?')} — {step.get('description', '')}")
                    print(f"    Tool      : {step.get('tool', '')}")
                    print(f"    Arguments : {json.dumps(step.get('arguments', {}), indent=14)}")

            print("\n" + "="*60)
            print(f"Total steps generated: {len(plan)}")
            print("="*60 + "\n")

            input("Browser is open. Press Enter to close it...")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(test_planner())
