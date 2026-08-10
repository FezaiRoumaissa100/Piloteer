import json
import asyncio
from datetime import datetime, timezone

from loggings.scripts.schema import get_connection

def _write_event(row: dict) -> None:
    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO events (
                trace_id, subgoal_id, step_id,
                node_name, phase, status,
                timestamp_start, timestamp_end, duration_ms,
                gen_ai_model, gen_ai_input_tokens, gen_ai_output_tokens,
                payload, screenshot
            ) VALUES (
                :trace_id, :subgoal_id, :step_id,
                :node_name, :phase, :status,
                :timestamp_start, :timestamp_end, :duration_ms,
                :gen_ai_model, :gen_ai_input_tokens, :gen_ai_output_tokens,
                :payload, :screenshot
            )
        """, row)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Logger] Write error: {e}")

async def log_event(
    state: dict,
    node_name: str,
    phase: str = None,
    status: str = "success",
    timestamp_start: str = None,
    gen_ai_model: str = None,
    gen_ai_input_tokens: int = None,
    gen_ai_output_tokens: int = None,
    payload: dict = None,
    screenshot: str = None,
    # Legacy aliases kept for backward compatibility — ignored
    screenshot_before: str = None,
    screenshot_after: str = None,
) -> None:
    # Accept old callers passing screenshot_before
    if screenshot is None and screenshot_before is not None:
        screenshot = screenshot_before

    trace_id = state.get("trace_id", "unknown_trace")
    subgoal_id = f"subgoal_{state.get('current_subgoal_index', 0):03d}"
    step_id = f"{subgoal_id}_step_{state.get('step_count', 0):03d}"

    timestamp_end = datetime.now(timezone.utc).isoformat()
    duration_ms = None
    if timestamp_start:
        try:
            ts_start = datetime.fromisoformat(timestamp_start)
            ts_end = datetime.fromisoformat(timestamp_end)
            duration_ms = int((ts_end - ts_start).total_seconds() * 1000)
        except:
            pass

    payload_str = json.dumps(payload or {}, ensure_ascii=False)

    row = {
        "trace_id": trace_id,
        "subgoal_id": subgoal_id,
        "step_id": step_id,
        "node_name": node_name,
        "phase": phase,
        "status": status,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "duration_ms": duration_ms,
        "gen_ai_model": gen_ai_model,
        "gen_ai_input_tokens": gen_ai_input_tokens,
        "gen_ai_output_tokens": gen_ai_output_tokens,
        "payload": payload_str,
        "screenshot": screenshot,
    }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _write_event, row)