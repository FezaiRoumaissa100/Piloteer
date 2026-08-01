"""
Piloteer — FastAPI WebSocket server.
Launches the agent pipeline for each connected browser session.
"""
import sys
import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from interface.channel import WebSocketChannel
from utils.rag.retrieve import get_saas_context_auto

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="Piloteer")

# Serve static files (index.html)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the chat interface."""
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    channel = WebSocketChannel(websocket)

    await channel.send("Hello! I am Piloteer, your AI assistant for web automation.", "system")
    await channel.send("Opening browser...", "system")

    try:
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Navigate to OrangeHRM
                await navigate(session, "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login")
                await session.call_tool("browser_video_show_actions", arguments={
                    "cursor": "pointer",
                    "duration": 800,
                    "position": "top-right"
                })

                await channel.send("Browser ready.", "system")
                await channel.send("What would you like to do today?", "agent")

                # Wait for the user's task
                user_task = await websocket.receive_text()
                await channel.send(f"Task received: {user_task}", "system")

                # Get initial snapshot
                initial_snapshot = await get_snapshot(session)
                
                # Retrieve RAG Context automatically
                saas_context = get_saas_context_auto(user_task, current_url="https://opensource-demo.orangehrmlive.com/web/index.php/auth/login")

                # Build state with WebSocket channel
                state = initiate_state(
                    user_task=user_task,
                    saas_context=saas_context,
                    channel=channel
                )
                state["snapshot_after"] = initial_snapshot
                state["current_url"]    = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"

                # Register the channel's reply receiver so ask_user works
                # Messages arriving while pipeline runs are forwarded to the queue
                pipeline_task = asyncio.create_task(_run_pipeline(session, state, channel))

                # While pipeline runs, route incoming WS messages as user replies
                while not pipeline_task.done():
                    try:
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                        await channel.receive_reply(msg)
                    except asyncio.TimeoutError:
                        pass

                final_state = await pipeline_task

                final_message = final_state.get("final_message")
                if final_message:
                    await channel.send(final_message, "success")
                else:
                    status = final_state.get("task_status", "unknown")
                    await channel.send(f"Task finished with status: {status}", "success")

    except WebSocketDisconnect:
        print("[Server] Client disconnected.")
    except Exception as e:
        print(f"[Server] Error: {e}")
        try:
            await channel.send(f"❌ Server error: {str(e)}", "error")
        except Exception:
            pass


async def _run_pipeline(session: ClientSession, state: dict, channel: WebSocketChannel):
    """Runs the LangGraph pipeline in a background task."""
    app_graph = build_graph(session)
    return await app_graph.ainvoke(state)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("interface.server:app", host="0.0.0.0", port=8000, reload=False)
