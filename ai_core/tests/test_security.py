import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, evaluate_js, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from utils.rag.retrieve import get_context
from utils.rag.retrieve import get_context
from loggings.scripts.schema import init_db

USER_TASK = "delete the  first employee from the employee list"




async def test_pipeline():

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Navigate to starting page
            url = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
            await navigate(session, url)
            print("[Setup] Navigated to OrangeHRM")
            input("[Setup] press Enter to continue...")
            initial_snapshot = await get_snapshot(session)
            saas_context ="nothing"
            # Build ini
            state = initiate_state(
                
                user_task=USER_TASK,
                saas_context=saas_context
            )
            state["snapshot"] = initial_snapshot
            state["current_url"]    = url

            # Build and run the graph
            print("[Pipeline] Starting graph...\n")
            app = build_graph(session)
            final_state = await app.ainvoke(state)

           
            print(f"  Task status    : {final_state.get('task_status', 'unknown')}")
            print(f"  Step done      : {final_state.get('step_done', False)}")
            




if __name__ == "__main__":
    init_db()
    asyncio.run(test_pipeline())