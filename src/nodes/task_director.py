import json
from orchestration.state import SharedState
from tools.client_gemini import ask_llm, ask_llm_json
from prompts.task_director_prompt import (
    understand_task_prompt, revise_subgoal_prompt, finalize_task_prompt,
    UNDERSTAND_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT, FINALIZE_SYSTEM_PROMPT
)
from utils.rag.retrieve import get_context
from loggings.scripts.logger import log_event
import asyncio
from datetime import datetime, timezone

async def task_director_node(state: SharedState) -> dict:
    #logging
    timestamp_start = datetime.now(timezone.utc).isoformat()

    user_task = state["user_task"]
    current_url = state.get("current_url", "")
    
    
    saas_context = state.get("saas_context", "no information")
            
    subgoals = state.get("subgoals", [])
    current_index = state.get("current_subgoal_index", 0)
    task_status = state.get("task_status", "pending")

    
    # --- DEBUG: Print Context for Security Testing ---
    if not subgoals:
        print("\n[TaskDirector] 🛡️ RAG SaaS Context Received:")
        print(saas_context)
        print("-" * 50)
    # -------------------------------------------------

    

    #Mode: Task Completion or Impossibility
    if task_status in ("completed", "task_impossible") or state.get("step_count", 0) >= 30:
        memory = state.get("memory", [])
        prompt = finalize_task_prompt(user_task, subgoals, memory)
        response, usage = await ask_llm_json(
            prompt=prompt,
            system_prompt=FINALIZE_SYSTEM_PROMPT,
            model="gemini-2.5-flash"
        )
        final_message = response.get("final_message", "Task completed.")
       
        asyncio.create_task(log_event(
            state=state, node_name="task_director", phase="finalize",
            timestamp_start=timestamp_start, gen_ai_model=usage.get("model")if isinstance(usage, dict) else None,
            gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
            gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
            payload=response
        ))
        
        return {
            "final_message": final_message,
            "task_status": "finalized"
        }


    #Mode: Initial Understanding
    if not subgoals:
        conversation_history = state.get("conversation_history", [])
        prompt = understand_task_prompt(user_task, saas_context, conversation_history)
        response, usage = await ask_llm_json(
            prompt=prompt,
            system_prompt=UNDERSTAND_SYSTEM_PROMPT,
            model="gemini-2.5-flash"
        )

        mode   = response.get("mode", "EXECUTE").upper()
        reasoning = response.get("reasoning", "No reasoning provided")
        
        print(f"\n[TaskDirector]  Reasoning: {reasoning}")
       

        if mode in ("QUESTION", "IMPOSSIBLE"):
            answer = response.get("answer", "I was unable to process this request.")
            print(f"[TaskDirector]  Final Answer: {answer}\n")
        
            
            asyncio.create_task(log_event(
                state=state, node_name="task_director", phase="understand_fast",
                timestamp_start=timestamp_start, gen_ai_model=usage.get("model") if isinstance(usage, dict) else None,
                gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
                gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
                payload=response
            ))
            
            return {
                "final_message": answer,
                "task_status": "finalized"
            }

    
        channel = state.get("channel")
        if channel:
            if mode == "GUIDE":
                await channel.send(answer or "Of course, I will show you how to do this step by step through an interactive guide.", "agent")
            elif mode == "EXECUTE":
                await channel.send(answer or "Of course, I will execute this task for you.", "agent")

        raw_subgoals = response.get("subgoals", [])
        generated_subgoals = []
        for i, sg in enumerate(raw_subgoals):
            generated_subgoals.append({
                "id": i,
                "description": sg["description"],
                "mini_planner_hints": sg.get("mini_planner_hints", ""),
                "status": "pending",
                "attempts": 0,
                "failure_reason": None
            })

        print("\n[TaskDirector] Generated Subgoals:")
        for sg in generated_subgoals:
            print(f"  - {sg['description']}")
        print("-" * 50)
        asyncio.create_task(log_event(
            state=state, node_name="task_director", phase="understand",
            timestamp_start=timestamp_start, gen_ai_model=usage.get("model") if isinstance(usage, dict) else None,
            gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
            gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
            payload=response
        ))

        return {
            "subgoals": generated_subgoals,
            "current_subgoal_index": 0,
            "task_status": "in_progress",
            "execution_mode": mode   
            
        }


    # Mode 2: Revision on Escalation
    blocked_subgoal = subgoals[current_index]
    completed = [sg for sg in subgoals if sg["status"] == "completed"]
    remaining = [sg for sg in subgoals[current_index + 1:] if sg["status"] == "pending"]

    memory = state.get("memory", [])
    prompt = revise_subgoal_prompt(user_task, completed, blocked_subgoal, remaining, memory)
    
    response, usage = await ask_llm_json(
        prompt=prompt,
        system_prompt=REVISE_SYSTEM_PROMPT,
        model="gemini-3.5-flash"
    )

    new_subgoals_data = response.get("new_subgoals", [])

    if not new_subgoals_data:
        asyncio.create_task(log_event(
            state=state, node_name="task_director", phase="revise_impossible",
            timestamp_start=timestamp_start, gen_ai_model=usage.get("model") if isinstance(usage, dict) else None,
            gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
            gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
            payload=response
        ))
        return {
            "task_status": "task_impossible"
        }
    updated_subgoals = list(subgoals)[:current_index]
    for i, sg in enumerate(new_subgoals_data):
        desc = sg.get("description", str(sg))
        updated_subgoals.append({
            "id": current_index + i,
            "description": desc,
            "mini_planner_hints": sg.get("mini_planner_hints", ""),
            "status": "pending",
            "attempts": 0,
            "failure_reason": None
        })
    
    asyncio.create_task(log_event(
        state=state, node_name="task_director", phase="revise",
        timestamp_start=timestamp_start, gen_ai_model=usage.get("model") if isinstance(usage, dict) else None,
        gen_ai_input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
        gen_ai_output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
        payload=response
    ))

    return {
        "subgoals": updated_subgoals
    }


