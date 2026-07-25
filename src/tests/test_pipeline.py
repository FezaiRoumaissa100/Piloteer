import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph


USER_TASK = "create a new project 'STAGE' and add the issue 'commnce' on it"



async def test_pipeline():

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("\n[Setup] MCP server connected")

            # Navigate to starting page
            await navigate(session, "https://linear.app")
            print("[Setup] Navigated to Linear")

            # Show cursor + action highlights (must be AFTER navigate)
            await session.call_tool("browser_video_show_actions", arguments={
                "cursor": "pointer",
                "duration": 800,
                "position": "top-right"
            })

            # Manual login pause for SaaS
            print("MANUAL ACTION REQUIRED: Please log in manually in the browser.")
            await asyncio.to_thread(input, "Press [ENTER] here once you are on the dashboard...")

            # Get initial snapshot to inject into state AFTER login
            initial_snapshot = await get_snapshot(session)
            # Build initial state
            state = initiate_state(
                user_task=USER_TASK,
                saas_context=""
            )
            state["snapshot_after"] = initial_snapshot
            state["current_url"]    = "https://www.google.com"

            # Build and run the graph
            print("[Pipeline] Starting graph...\n")
            app = build_graph(session)
            final_state = await app.ainvoke(state)

           
            print(f"  Task status    : {final_state.get('task_status', 'unknown')}")
            print(f"  Step done      : {final_state.get('step_done', False)}")
            




if __name__ == "__main__":
    asyncio.run(test_pipeline())
