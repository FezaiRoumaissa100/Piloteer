"""
Piloteer - FastAPI WebSocket server.
Persistent browser session with multi-turn conversation loop.
"""
import sys
import os
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from interface.channel import WebSocketChannel
from utils.rag.retrieve import get_context

app = FastAPI(title="Piloteer")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
BASE_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"


@app.get("/")
async def root():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    channel = WebSocketChannel(websocket)

    # Session-level state — persists across all tasks
    conversation_history: list[dict] = []
    current_url = BASE_URL
    current_snapshot = None

    try:
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Open browser once for the whole session
                await navigate(session, BASE_URL)
                current_snapshot = await get_snapshot(session)

                # Greeting — enables the input on the frontend
                await channel.send(
                    "Hello! I'm Piloteer, your AI assistant to understand your needs.how can I help you today?",
                    "success"
                )

                # ── Multi-turn conversation loop ────────────────────────────
                while True:
                    user_task = await websocket.receive_text()

                    saas_context = get_context(user_task, current_url=current_url)

                    state = initiate_state(
                        user_task=user_task,
                        saas_context=saas_context,
                        channel=channel
                    )
                    state["snapshot"]       = current_snapshot
                    state["current_url"]          = current_url
                    state["conversation_history"] = list(conversation_history)

                    pipeline_task = asyncio.create_task(
                        _run_pipeline(session, state, channel)
                    )

                    # Route incoming WS messages as user replies during pipeline
                    while not pipeline_task.done():
                        try:
                            msg = await asyncio.wait_for(
                                websocket.receive_text(), timeout=0.1
                            )
                            if msg == "__CANCEL__":
                                pipeline_task.cancel()
                                break
                            await channel.receive_reply(msg)
                        except asyncio.TimeoutError:
                            pass

                    try:
                        final_state = await pipeline_task
                    except asyncio.CancelledError:
                        final_state = {
                            "final_message": "Task manually cancelled by user.",
                            "task_status": "cancelled"
                        }
                    except BaseException as e:
                        # Catch ExceptionGroup (TaskGroup errors from anyio/asyncio)
                        # and any other unexpected exception
                        if hasattr(e, 'exceptions'):
                            # ExceptionGroup: log each sub-exception clearly
                            for sub in e.exceptions:
                                print(f"[Server] Sub-exception in pipeline: {type(sub).__name__}: {sub}")
                            error_msg = f"An error occurred in the agent pipeline: {e.exceptions[0]}"
                        else:
                            print(f"[Server] Unexpected error during pipeline: {type(e).__name__}: {e}")
                            error_msg = f"An unexpected error occurred: {e}"
                        await channel.send(error_msg, "error")
                        try:
                            current_snapshot = await get_snapshot(session)
                        except Exception:
                            pass
                        continue

                    # Persist browser location for next task
                    current_url      = final_state.get("current_url", current_url)
                    current_snapshot = final_state.get("snapshot", current_snapshot)

                    # Build and send final message
                    final_message = final_state.get("final_message") or \
                        f"Task completed (status: {final_state.get('task_status', 'unknown')})."

                    conversation_history.append({
                        "user":  user_task,
                        "agent": final_message
                    })

                    # Send as "success" so the frontend re-enables input
                    await channel.send(final_message, "success")

    except WebSocketDisconnect:
        print("[Server] Client disconnected.")
    except Exception as e:
        print(f"[Server] Error: {e}")
        try:
            await channel.send(f"An error occurred: {str(e)}", "error")
        except Exception:
            pass


async def _run_pipeline(session: ClientSession, state: dict, channel: WebSocketChannel):
    app_graph = build_graph(session)
    return await app_graph.ainvoke(state)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("interface.server:app", host="0.0.0.0", port=8000, reload=False)
