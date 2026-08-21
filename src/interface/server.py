"""
Piloteer - FastAPI WebSocket server & Admin API.
Persistent browser session with multi-turn conversation loop.
"""
import sys
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from interface.channel import WebSocketChannel
from utils.rag.retrieve import get_context
from loggings.scripts.schema import get_connection, SCREENS_DIR

app = FastAPI(title="Piloteer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCREENS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=str(SCREENS_DIR)), name="screenshots")

BASE_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"


@app.get("/")
async def root():
    return {"status": "Piloteer FastAPI WebSocket Backend is running"}


# admin Replay API Endpoint

@app.get("/api/admin/traces")
async def get_admin_traces():
    """Returns the list of all recorded missions with metadata and prompt."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                trace_id, 
                MAX(user_task) as user_task,
                MIN(timestamp_start) as start_time,
                MAX(timestamp_end) as end_time,
                COUNT(*) as step_count,
                SUM(duration_ms) as total_duration_ms,
                SUM(gen_ai_input_tokens) as total_input_tokens,
                SUM(gen_ai_output_tokens) as total_output_tokens
            FROM events 
            GROUP BY trace_id 
            ORDER BY MIN(event_id) DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[Admin API] Error fetching traces: {e}")
        return []


@app.get("/api/admin/traces/{trace_id}")
async def get_admin_trace_events(trace_id: str):
    """Returns sequential event steps for a specific trace, with screenshot URLs."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT * FROM events WHERE trace_id = ? ORDER BY event_id ASC
        """, (trace_id,)).fetchall()
        conn.close()

        events = []
        for r in rows:
            item = dict(r)
            if item.get("screenshot"):
                p = Path(item["screenshot"])
                # Extract relative folder and filename e.g. /screenshots/run_xxx/subgoal_xxx.png
                item["screenshot_url"] = f"http://localhost:8000/screenshots/{p.parent.name}/{p.name}"
            else:
                item["screenshot_url"] = None
            events.append(item)
        return events
    except Exception as e:
        print(f"[Admin API] Error fetching events for {trace_id}: {e}")
        return []


@app.get("/api/admin/analytics")
async def get_admin_analytics(trace_id: str = None):
    """Returns aggregated performance analytics for all missions or a specific trace."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if trace_id and trace_id != "all":
            rows = cursor.execute("SELECT * FROM events WHERE trace_id = ? ORDER BY event_id ASC", (trace_id,)).fetchall()
        else:
            rows = cursor.execute("SELECT * FROM events ORDER BY event_id ASC").fetchall()
        conn.close()

        events = [dict(r) for r in rows]
        if not events:
            return {
                "kpis": {
                    "missions_count": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "total_duration_s": 0,
                    "success_rate": 0,
                    "total_steps": 0,
                    "bottleneck_node": "N/A"
                },
                "node_breakdown": [],
                "missions_summary": []
            }

        
        unique_traces = list(set(e["trace_id"] for e in events))
        total_in = sum(e["gen_ai_input_tokens"] or 0 for e in events)
        total_out = sum(e["gen_ai_output_tokens"] or 0 for e in events)
        total_dur_ms = sum(e["duration_ms"] or 0 for e in events)
        successes = sum(1 for e in events if e.get("status") == "success")
        success_rate = round((successes / len(events)) * 100, 1) if events else 0

        # Group by node
        node_stats = {}
        for e in events:
            node = e.get("node_name", "unknown")
            if node not in node_stats:
                node_stats[node] = {
                    "node_name": node,
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "durations": [],
                    "successes": 0
                }
            node_stats[node]["calls"] += 1
            node_stats[node]["input_tokens"] += (e.get("gen_ai_input_tokens") or 0)
            node_stats[node]["output_tokens"] += (e.get("gen_ai_output_tokens") or 0)
            if e.get("duration_ms") is not None:
                node_stats[node]["durations"].append(e["duration_ms"])
            if e.get("status") == "success":
                node_stats[node]["successes"] += 1

        node_breakdown = []
        bottleneck_node = "N/A"
        max_avg_dur = -1

        for node, s in node_stats.items():
            dur_list = s["durations"]
            avg_dur = round(sum(dur_list) / len(dur_list)) if dur_list else 0
            tot_dur = sum(dur_list) if dur_list else 0
            if avg_dur > max_avg_dur:
                max_avg_dur = avg_dur
                bottleneck_node = node

            s_rate = round((s["successes"] / s["calls"]) * 100, 1) if s["calls"] > 0 else 0
            node_breakdown.append({
                "node_name": node,
                "calls": s["calls"],
                "input_tokens": s["input_tokens"],
                "output_tokens": s["output_tokens"],
                "total_tokens": s["input_tokens"] + s["output_tokens"],
                "avg_duration_ms": avg_dur,
                "total_duration_ms": tot_dur,
                "success_rate": s_rate
            })

        # Group by mission
        mission_stats = {}
        for e in events:
            tid = e["trace_id"]
            if tid not in mission_stats:
                mission_stats[tid] = {
                    "trace_id": tid,
                    "user_task": e.get("user_task") or "",
                    "steps": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "durations": [],
                    "successes": 0
                }
            mission_stats[tid]["steps"] += 1
            if not mission_stats[tid]["user_task"] and e.get("user_task"):
                mission_stats[tid]["user_task"] = e["user_task"]
            mission_stats[tid]["input_tokens"] += (e.get("gen_ai_input_tokens") or 0)
            mission_stats[tid]["output_tokens"] += (e.get("gen_ai_output_tokens") or 0)
            if e.get("duration_ms") is not None:
                mission_stats[tid]["durations"].append(e["duration_ms"])
            if e.get("status") == "success":
                mission_stats[tid]["successes"] += 1

        missions_summary = []
        for tid, m in mission_stats.items():
            dur_s = round(sum(m["durations"]) / 1000, 1) if m["durations"] else 0
            s_rate = round((m["successes"] / m["steps"]) * 100, 1) if m["steps"] > 0 else 0
            missions_summary.append({
                "trace_id": tid,
                "user_task": m["user_task"],
                "steps": m["steps"],
                "input_tokens": m["input_tokens"],
                "output_tokens": m["output_tokens"],
                "total_tokens": m["input_tokens"] + m["output_tokens"],
                "duration_s": dur_s,
                "success_rate": s_rate
            })

        return {
            "kpis": {
                "missions_count": len(unique_traces),
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_tokens": total_in + total_out,
                "total_duration_s": round(total_dur_ms / 1000, 1),
                "success_rate": success_rate,
                "total_steps": len(events),
                "bottleneck_node": bottleneck_node
            },
            "node_breakdown": node_breakdown,
            "missions_summary": missions_summary
        }
    except Exception as e:
        print(f"[Admin API] Error computing analytics: {e}")
        return {"error": str(e)}




@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    channel = WebSocketChannel(websocket)

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

                await channel.send(
                    "Hello! I'm Piloteer, the AI assistant for this interface. I can guide you or execute your tasks here. How can I help you today?",
                    "success"
                )

                while True:
                    user_task = await websocket.receive_text()

                    saas_context = get_context(user_task, current_url=current_url)

                    state = initiate_state(
                        user_task=user_task,
                        saas_context=saas_context,
                        channel=channel
                    )
                    state["snapshot"]             = current_snapshot
                    state["current_url"]          = current_url
                    state["conversation_history"] = list(conversation_history)

                    pipeline_task = asyncio.create_task(
                        _run_pipeline(session, state)
                    )

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
                        if hasattr(e, 'exceptions'):
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
                    task_status = final_state.get("task_status", "unknown")
                    if task_status == "cancelled":
                        final_message = "The user cancelled the task"
                        msg_type = "cancelled"
                    else:
                        final_message = final_state.get("final_message") or f"Task completed (status: {task_status})."
                        msg_type = "success"

                    conversation_history.append({
                        "user":  user_task,
                        "agent": final_message
                    })

                    await channel.send(final_message, msg_type)

    except WebSocketDisconnect:
        print("[Server] Client disconnected.")
    except Exception as e:
        print(f"[Server] Error: {e}")
        try:
            await channel.send(f"An error occurred: {str(e)}", "error")
        except Exception:
            pass


async def _run_pipeline(session: ClientSession, state: dict):
    app_graph = build_graph(session)
    return await app_graph.ainvoke(state)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("interface.server:app", host="0.0.0.0", port=8000, reload=False)
