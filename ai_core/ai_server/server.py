"""
Piloteer - FastAPI WebSocket server & Admin API.
Persistent browser session with multi-turn conversation loop.
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from pathlib import Path

import os
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from ai_server.channel import WebSocketChannel
from rag.retrieve import get_context
from loggings.scripts.schema import get_connection, SCREENS_DIR

from contextlib import asynccontextmanager

BASE_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"

global_mcp_session = None
global_mcp_ctx = None
global_current_url = BASE_URL
global_current_snapshot = None
global_conversation_history = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_mcp_session, global_mcp_ctx, global_current_snapshot
    print("[Server] Starting browser (MCP) in the background...")
    try:
        global_mcp_ctx = stdio_client(SERVER_PARAMS)
        read, write = await global_mcp_ctx.__aenter__()
        global_mcp_session = ClientSession(read, write)
        await global_mcp_session.__aenter__()
        
        await global_mcp_session.initialize()
        await navigate(global_mcp_session, BASE_URL)
        global_current_snapshot = await get_snapshot(global_mcp_session)
        print("[Server] Browser ready!")
    except Exception as e:
        print(f"[Server] Error starting the browser: {e}")
        
    yield
    
    print("[Server] Closing browser...")
    if global_mcp_session:
        await global_mcp_session.__aexit__(None, None, None)
    if global_mcp_ctx:
        await global_mcp_ctx.__aexit__(None, None, None)

GEMINI_VOICE_MODEL  = "gemini-3.1-flash-live-preview"
GEMINI_VOICE_NAME   = "Leda"
EMPTY_TRANSCRIPT_REPLY = "Sorry, I didn't hear you clearly. Could you repeat what you said?"

app = FastAPI(title="Piloteer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCREENS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=str(SCREENS_DIR)), name="screenshots")


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
    global global_current_url, global_current_snapshot, global_conversation_history, global_mcp_session
    await websocket.accept()
    channel = WebSocketChannel(websocket)

    # Only one reader has receive_text(). When the graph is in
    # channel.ask(), incoming messages are passed to receive_reply().
    # When no graph is running, they become new tasks.
    incoming_tasks: asyncio.Queue = asyncio.Queue()
    pipeline_active = False

    async def route_incoming_messages():
        nonlocal pipeline_active
        try:
            while True:
                text = await websocket.receive_text()

                if pipeline_active:
                    await channel.receive_reply(text)
                elif text != "__CANCEL__":
                    await incoming_tasks.put(text)
        except WebSocketDisconnect:
            channel._disconnected = True
            # Unblock channel.ask() if the browser disconnects during
            # an ask_user/HITL question.
            if pipeline_active:
                await channel.receive_reply("")
            await incoming_tasks.put(None)
        except Exception as error:
            print(f"[Server] WebSocket reader error: {error}")
            channel._disconnected = True
            if pipeline_active:
                await channel.receive_reply("")
            await incoming_tasks.put(None)

    reader_task = asyncio.create_task(route_incoming_messages())

    try:
        while True:
            user_task = await incoming_tasks.get()
            if user_task is None:
                break

            saas_context = get_context(user_task, current_url=global_current_url)

            state = initiate_state(
                user_task=user_task,
                saas_context=saas_context,
                channel=channel
            )
            state["snapshot"] = global_current_snapshot
            state["current_url"] = global_current_url
            state["conversation_history"] = list(global_conversation_history)

            pipeline_active = True
            try:
                final_state = await _run_pipeline(global_mcp_session, state)
            except BaseException as e:
                print(f"[Server] Pipeline error: {e}")
                await channel.send(f"An error occurred: {e}", "error")
                try:
                    global_current_snapshot = await get_snapshot(global_mcp_session)
                except Exception:
                    pass
                continue
            finally:
                pipeline_active = False

            global_current_url = final_state.get("current_url", global_current_url)
            global_current_snapshot = final_state.get("snapshot", global_current_snapshot)

            task_status = final_state.get("task_status", "unknown")
            final_message = final_state.get("final_message") or f"Task completed (status: {task_status})."

            global_conversation_history.append({
                "user": user_task,
                "agent": final_message
            })

            await channel.send(final_message, "success")

    except WebSocketDisconnect:
        print("[Server] Client disconnected.")
    except Exception as e:
        print(f"[Server] Error: {e}")
    finally:
        reader_task.cancel()
        await asyncio.gather(reader_task, return_exceptions=True)


async def _run_pipeline(session: ClientSession, state: dict):
    app_graph = build_graph(session)
    return await app_graph.ainvoke(state)


@app.websocket("/ws/voice")
async def voice_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()
    print("[Voice] Widget connected.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        await browser_ws.send_text(json.dumps({"type": "error", "content": "GEMINI_API_KEY missing"}))
        await browser_ws.close()
        return

    gemini_client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1alpha"},
    )

    gemini_config_stt = {
        "response_modalities": ["AUDIO"],
        "system_instruction": (
            "You are exclusively a speech transcription module. "
            "Never answer the user and never produce a spoken response. "
            "Only return input audio transcription events."
        ),
        "input_audio_transcription": {},
    }

    gemini_config_tts = {
        "response_modalities": ["AUDIO"],
        "system_instruction": (
            "You are exclusively the Piloteer Text-To-Speech module. "
            "You receive text prefixed with READ:. Read it naturally and exactly. "
            "Do not add comments, explanations, or extra content."
        ),
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": GEMINI_VOICE_NAME}
            }
        },
    }

    active_tasks: set[asyncio.Task] = set()

    try:
        async with websockets.connect(
            "ws://localhost:8000/ws",
            # The internal channel stays local and can wait a long time in channel.ask().
            # No application ping is needed; this avoids the 1011
            # keepalive ping timeout while waiting for human response.
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
        ) as piloteer_ws:
            print("[Voice] Connected to internal Piloteer channel.")

            piloteer_busy = False
            waiting_for_user_input = False
            stt_active = False
            tts_task_active = False
            stt_audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
            tts_queue: asyncio.Queue[tuple[str, bool]] = asyncio.Queue()

            def track_task(coro):
                task = asyncio.create_task(coro)
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)
                return task

            async def start_tts_worker_if_needed():
                nonlocal tts_task_active
                if not tts_task_active:
                    tts_task_active = True
                    track_task(process_tts_task())

            async def process_tts_task():
                nonlocal piloteer_busy, tts_task_active, waiting_for_user_input

                try:
                    while True:
                        content, is_final = await tts_queue.get()

                        try:
                            if content.strip():
                                print("[Voice] Opening temporary TTS session...")
                                speaking_signal_sent = False

                                async with gemini_client.aio.live.connect(
                                    model=GEMINI_VOICE_MODEL,
                                    config=gemini_config_tts,
                                ) as session:
                                    await session.send_client_content(
                                        turns=[
                                            {
                                                "role": "user",
                                                "parts": [{"text": f"READ: {content}"}],
                                            }
                                        ],
                                        turn_complete=True,
                                    )

                                    async for msg in session.receive():
                                        server_content = getattr(msg, "server_content", None)
                                        model_turn = getattr(server_content, "model_turn", None)

                                        if model_turn:
                                            for part in model_turn.parts:
                                                inline_data = getattr(part, "inline_data", None)
                                                if inline_data and inline_data.data:
                                                    # The widget switches to speaking mode only
                                                    # at the first real TTS audio packet.
                                                    if not speaking_signal_sent:
                                                        await browser_ws.send_text(
                                                            json.dumps(
                                                                {
                                                                    "type": "state",
                                                                    "content": "speaking",
                                                                }
                                                            )
                                                        )
                                                        speaking_signal_sent = True
                                                    await browser_ws.send_bytes(inline_data.data)

                                        if getattr(server_content, "turn_complete", False):
                                            break

                        except Exception as error:
                            print(f"[Voice] TTS error during playback: {error}")
                            await browser_ws.send_text(
                                json.dumps(
                                    {
                                        "type": "error",
                                        "content": "Error during voice playback.",
                                    }
                                )
                            )

                        tts_queue.task_done()

                        if is_final:
                            print("[Voice] Voice response completed.")
                            await browser_ws.send_text(
                                json.dumps({"type": "state", "content": "idle"})
                            )
                            piloteer_busy = False
                            tts_task_active = False
                            break

                        next_state = (
                            "awaiting_user" if waiting_for_user_input else "processing"
                        )
                        await browser_ws.send_text(
                            json.dumps({"type": "state", "content": next_state})
                        )

                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    tts_task_active = False
                    print(f"[Voice] Global TTS error: {error}")

            async def run_stt_session():
                nonlocal piloteer_busy, stt_active, waiting_for_user_input
                accumulated_transcript = ""

                try:
                    print("[Voice] Opening STT session...")
                    async with gemini_client.aio.live.connect(
                        model=GEMINI_VOICE_MODEL,
                        config=gemini_config_stt,
                    ) as session:
                        # The widget switches to recording only after
                        # the Gemini STT session is successfully opened.
                        await browser_ws.send_text(
                            json.dumps({"type": "state", "content": "listening"})
                        )

                        async def receive_loop():
                            nonlocal accumulated_transcript
                            try:
                                async for msg in session.receive():
                                    server_content = getattr(msg, "server_content", None)
                                    transcription = getattr(
                                        server_content, "input_transcription", None
                                    )
                                    text = getattr(transcription, "text", None)

                                    if text and text not in accumulated_transcript:
                                        accumulated_transcript += f"{text} "
                            except asyncio.CancelledError:
                                raise

                        recv_task = asyncio.create_task(receive_loop())

                        while True:
                            chunk = await stt_audio_queue.get()
                            try:
                                if chunk == b"END":
                                    break
                                await session.send_realtime_input(
                                    audio={
                                        "mime_type": "audio/pcm;rate=16000",
                                        "data": chunk,
                                    }
                                )
                            finally:
                                stt_audio_queue.task_done()

                        await session.send_client_content(turn_complete=True)

                        # Let Gemini send the final transcription before closing.
                        for _ in range(20):
                            if recv_task.done():
                                break
                            await asyncio.sleep(0.1)

                        if not recv_task.done():
                            recv_task.cancel()
                            await asyncio.gather(recv_task, return_exceptions=True)

                        final_text = accumulated_transcript.strip()

                        if final_text:
                            print(f"[Voice] Final transcription: {final_text}")
                            piloteer_busy = True
                            await browser_ws.send_text(
                                json.dumps({"type": "transcript", "content": final_text})
                            )
                            await browser_ws.send_text(
                                json.dumps({"type": "state", "content": "processing"})
                            )
                            if waiting_for_user_input:
                                waiting_for_user_input = False
                            await piloteer_ws.send(final_text)
                        else:
                            # An empty phrase is no longer silently cancelled.
                            # We use the same TTS channel as Piloteer reports.
                            print("[Voice] No transcription: asking to repeat.")
                            await browser_ws.send_text(
                                json.dumps(
                                    {
                                        "type": "transcript",
                                        "content": "No speech detected.",
                                    }
                                )
                            )
                            await browser_ws.send_text(
                                json.dumps({"type": "state", "content": "processing"})
                            )
                            await tts_queue.put((EMPTY_TRANSCRIPT_REPLY, not waiting_for_user_input))
                            await start_tts_worker_if_needed()

                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    print(f"[Voice] STT error: {error}")
                    await browser_ws.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "content": "Voice transcription error.",
                            }
                        )
                    )
                finally:
                    stt_active = False

            async def handle_piloteer():
                nonlocal tts_task_active, waiting_for_user_input
                input_request_types = {
                    "ask_user",
                    "hitl",
                    "interrupt",
                    "human_input",
                    "approval_required",
                    "confirmation_required",
                    "human_approval",
                    "approval",
                    "confirmation",
                    "human_review",
                    "resume_required",
                }
                try:
                    while True:
                        raw = await piloteer_ws.recv()
                        data = json.loads(raw)
                        msg_type = data.get("type", "")
                        content = data.get("content", "")
                        is_final = msg_type in {"success", "error", "finished", "cancelled"}

                        if msg_type in input_request_types:
                            waiting_for_user_input = True

                        if msg_type == "system":
                            continue

                        if content or is_final:
                            # Strip the HITL: prefix so the TTS voice reads the
                            # natural sentence without the protocol prefix.
                            tts_content = content
                            if isinstance(tts_content, str) and tts_content.startswith("HITL:"):
                                tts_content = tts_content[len("HITL:"):].strip()
                                tts_content += " Please answer allow or deny."
                            print(f"[Voice → Piloteer {msg_type}] : {tts_content}")
                            await tts_queue.put((tts_content, is_final))
                            await start_tts_worker_if_needed()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    print(f"[Voice] Piloteer recv error: {error}")

            track_task(handle_piloteer())

            while True:
                message = await browser_ws.receive()

                if "text" in message:
                    data = json.loads(message["text"])
                    message_type = data.get("type")

                    if message_type == "start":
                        if not stt_active and (not piloteer_busy or waiting_for_user_input):
                            print("[Voice] STT start requested")
                            stt_active = True
                            while not stt_audio_queue.empty():
                                stt_audio_queue.get_nowait()
                            track_task(run_stt_session())

                    elif message_type == "speech_end":
                        if stt_active:
                            print("[Voice] Speech end requested by button")
                            await stt_audio_queue.put(b"END")

                elif "bytes" in message and stt_active:
                    await stt_audio_queue.put(message["bytes"])

    except WebSocketDisconnect:
        print("[Voice] Widget disconnected.")
    except Exception as error:
        print(f"[Voice] Main loop error: {error}")
    finally:
        for task in active_tasks:
            task.cancel()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ai_server.server:app", host="0.0.0.0", port=8000, reload=False)
