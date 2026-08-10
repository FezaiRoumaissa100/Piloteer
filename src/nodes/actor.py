import asyncio
from datetime import datetime, timezone
from mcp import ClientSession
from orchestration.state import SharedState
from tools.mcp_client import get_snapshot, wait_for, evaluate_js, take_screenshot
from utils.guide_mode.spotlight import get_spotlight_js, get_cleanup_js
from loggings.scripts.logger import log_event

# Tools that trigger navigation :need extra wait before snapshot
NAVIGATION_TOOLS = {"browser_click", "browser_navigate", "browser_press_key"}


def make_actor_node(session: ClientSession):
    """
    Factory that captures the MCP session and returns the actor node.
    Called once in graph.py — the session lives for the whole pipeline.
    """

    async def actor_node(state: SharedState) -> dict:
        timestamp_start = datetime.now(timezone.utc).isoformat()
        screenshot_path = None  
        step = state["current_step"]
        task_status = state.get("task_status")

        if not step:
            return {
                "snapshot":           None,
                "last_action_result": "error: no step"
            }

        
        arguments = step.get("arguments", {}).copy()
        if step["tool"] == "browser_finish_subgoal":
            status = arguments.get("status", "success")
            reason = arguments.get("reason", "")

            if status == "impossible":
                task_status = "needs_revision"
                action_result = (
                    f"The Planner has determined this subgoal cannot be achieved.\n"
                    f"Reason: {reason}"
                )
            else:
                action_result = (
                    f"The Planner indicates the current subgoal is complete. "
                    f"Reason: {reason or ' '} "
                    f"Validator, perform a final double-check."
                )
            snapshot = state.get("snapshot", "")
            is_error = False

        elif step["tool"] == "ask_user":
            question = step.get("arguments", {}).get("question", "i need more details about the current task")
            field    = step.get("arguments", {}).get("field", "")
            
            return {
                "pending_question":     question,
                "current_step":         step,
                "snapshot":             state.get("snapshot", ""),
                "last_action_result":   f"Waiting for user input on field: {field}",
                "last_action_is_error": False,
            }

        else:
            from loggings.scripts.screenshot import get_screenshot_path
            trace_id   = state.get("trace_id") or "run_unknown"
            subgoal_id = f"subgoal_{state.get('current_subgoal_index', 0):03d}"
            step_id    = f"step_{state.get('step_count', 0):03d}"
            screenshot_path = get_screenshot_path(trace_id, subgoal_id, step_id, "before")
            await take_screenshot(session, filename=screenshot_path)

            # --- GUIDE MODE VISUAL SPOTLIGHT ---
            cleanup_required = False
            
            if state.get("execution_mode") == "GUIDE" and step["tool"] in ["browser_click", "browser_type", "browser_hover", "browser_select_option"]:
                description = step.get("description", "Action en cours...")
                target_ref = arguments.get("target")
                channel = state.get("channel")
                if channel:
                    await channel.send(description, "agent")
                if target_ref:
                    js_script = get_spotlight_js(description)

                    try:
                        await evaluate_js(session, function=js_script, target=target_ref)
                        cleanup_required = True
                        await asyncio.sleep(4)
                    except Exception as e:
                        print(f"[Actor] Guide Spotlight error: {e}")
            # ------------------------------------

            result = await session.call_tool(
                name=step["tool"],
                arguments=arguments
            )
            
            if cleanup_required:
                try:
                    await evaluate_js(session, function=get_cleanup_js())
                except Exception:
                    pass 
           
            if step["tool"] in NAVIGATION_TOOLS:
                await wait_for(session, time=3)
        
            snapshot = await get_snapshot(session)
            is_error = getattr(result, "isError", False)
            action_result = result.content[0].text if result.content else "Command executed with no text output."


        asyncio.create_task(log_event(
            state=state, node_name="actor",
            timestamp_start=timestamp_start,
            screenshot=screenshot_path,  
            payload={
                "tool_executed": step["tool"],
                "arguments": arguments,
                "result": action_result
            }
        ))

        return {
            "snapshot":              snapshot,
            "last_action_result":    action_result,
            "last_action_is_error":  is_error,
            "task_status":           task_status,
            "timestamp_start":       timestamp_start,
            "screenshot":         screenshot_path,
        }

    return actor_node
