import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def ask_llm(prompt: str, system_prompt: str = "", model: str = "gemini-2.0-flash", retries: int = 3) -> str:
    "Send the prompt to Gemini and return the response — waits on 429 before retrying"
    for attempt in range(retries):
        try:
            config = types.GenerateContentConfig()
            if system_prompt:
                config.system_instruction = system_prompt

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            msg = str(e)
            if "429" in msg or "503" in msg:
                fallbacks = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
                if model in fallbacks:
                    current_idx = fallbacks.index(model)
                    if current_idx < len(fallbacks) - 1:
                        next_model = fallbacks[current_idx + 1]
                        print(f"[LLM] Error {msg[:20]} on {model} — falling back to {next_model} for attempt {attempt+1}/{retries}...")
                        model = next_model
                        continue

                print(f"[LLM] Rate limit hit on {model} — no more fallbacks available. Giving up.")
                return "Error : rate limit and no fallbacks"
            else:
                print(f"Unexpected error : {e}")
                return "Error : " + str(e)
    return "Error : max retries exceeded"




def ask_vision(image_path: str, prompt: str, model : str = "gemini-2.0-flash") -> str:
    "Send the image and the prompt to Gemini and return the response"
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
        response=client.models.generate_content(
            model=model,
            contents=[{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_bytes}}
            ]
        }]
        )
        return response.text
    except Exception as e:
        print(f"Unexpected error : {e}")
        return "Error : " + str(e)


async def ask_llm_json(
    prompt: str,
    system_prompt: str = "",
    cache_name: str = None,
    model: str = "gemini-2.0-flash",
    retries: int = 4
) -> tuple:
    for attempt in range(retries):
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            if system_prompt:
                config.system_instruction = system_prompt

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            data = json.loads(response.text)

            # Track cached tokens (filled automatically by Gemini 2.5+ implicit caching)
            cached_tokens = 0
            if getattr(response, "usage_metadata", None):
                cached_tokens = getattr(response.usage_metadata, "cached_content_token_count", 0) or 0

            usage = {
                "model":         model,
                "input_tokens":  response.usage_metadata.prompt_token_count if getattr(response, "usage_metadata", None) else 0,
                "output_tokens": response.usage_metadata.candidates_token_count if getattr(response, "usage_metadata", None) else 0,
                "cached_tokens": cached_tokens,
            }

            if cached_tokens:
                print(f"[Cache] Implicit cache hit — {cached_tokens} tokens from cache (75% cheaper)")

            return data, usage

        except json.JSONDecodeError as e:
            print(f"JSON parsing error (attempt {attempt+1}/{retries}): {e}")
            continue
        except Exception as e:
            msg = str(e)
            is_rate_limit = "429" in msg or "503" in msg
            if is_rate_limit:
                fallbacks = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
                if model in fallbacks:
                    current_idx = fallbacks.index(model)
                    if current_idx < len(fallbacks) - 1:
                        next_model = fallbacks[current_idx + 1]
                        print(f"[LLM] Error {msg[:20]} on {model} — falling back to {next_model} for attempt {attempt+1}/{retries}...")
                        model = next_model
                        continue

                print(f"[LLM] Rate limit hit on {model} — no more fallbacks available. Giving up.")
                break
            else:
                print(f"Unexpected error in ask_json (attempt {attempt+1}/{retries}): {e}")
                import asyncio
                await asyncio.sleep(2)
                continue
    return {}, {}




async def ask_judge_text(
    task: dict,
    final_message: str,
    current_url: str,
    task_status: str,
    snapshot: str,
    memory: list,
    model: str = "gemini-2.0-flash",
    retries: int = 3
) -> dict:
    """
    Spécialement conçu pour le Juge IA.
    Prend toutes les données (mémoire, message, arbre d'accessibilité) et retourne un JSON.
    """
    import asyncio
    
    # Format the memory into a readable trajectory
    trajectory = ""
    for i, m in enumerate(memory):
        step_status = "SUCCESS" if m.get("success") else "FAILED"
        entry = m.get("memory_entry", "No description")
        trajectory += f"Step {i+1} [{step_status}]: {entry}\n"
        
    if not trajectory:
        trajectory = "No actions taken."

    prompt_text = f"""
You are an expert Evaluator Judge for Autonomous Web Agents, specialized in HR SaaS platforms (OrangeHRM).
Your role is to determine if the agent successfully completed the requested task.

--- TASK DESCRIPTION ---
Goal: {task.get('prompt', '')}
Category: {task.get('category', '')}

--- IMPORTANT EVALUATION CONTEXT ---
{task.get('judge_context', 'No specific context provided. Use your best judgment.')}

--- AGENT EXECUTION TRACE (Memory) ---
{trajectory}

--- AGENT FINAL STATUS & MESSAGE ---
LangGraph Task Status: {task_status}
Agent Final Message to User: {final_message}
Current Final URL: {current_url}

--- FINAL ACCESSIBILITY TREE ---
{snapshot}

=== PHASE 1 — CHAIN-OF-THOUGHT (Reasoning) ===
Reason step by step before giving your first verdict:

Step 1 — UNDERSTAND THE GOAL:
What exactly was the agent asked to do? What would unambiguous SUCCESS look like?

Step 2 — ANALYZE THE TRACE:
Walk through each step in the execution trace. Did the agent navigate correctly, fill forms, submit data, or correctly identify a blocker?

Step 3 — VERIFY THE FINAL STATE:
Look at the final URL and the accessibility tree. Does the current browser state match the expected success state?

Step 4 — APPLY EVALUATION CONTEXT:
Re-read the IMPORTANT EVALUATION CONTEXT. Are there special conditions (interactive task, platform constraint, resilience test)? Does the agent's behavior align with those expectations?

Step 5 — INITIAL VERDICT:
Based on Steps 1-4, write your first verdict: SUCCESS or FAILED, and why in one sentence.

=== PHASE 2 — CHAIN-OF-VERIFICATION (Self-Correction) ===
Now challenge your own verdict by answering these critical questions honestly:

Q1 — Did I correctly consider the judge_context special rules?
(e.g., for interactive tasks, did I accept that pausing to ask_user is SUCCESS?)

Q2 — Could the trace prove success even if the final accessibility tree doesn't clearly show it?
(e.g., a save confirmation appeared briefly, then the page changed)

Q3 — Am I being too strict or too lenient?
(e.g., failing because of a minor UI detail that doesn't affect task completion)

Q4 — Is my initial verdict consistent with all the evidence (trace + URL + tree + context)?

Step 6 — FINAL CORRECTED VERDICT:
After answering Q1-Q4, confirm or correct your verdict. Write the definitive conclusion.

=== OUTPUT FORMAT ===
You MUST return ONLY a valid JSON object (no markdown, no code blocks):
{{
  "step1_goal": "What the agent had to do.",
  "step2_trace_analysis": "Summary of what the agent did in its trace.",
  "step3_final_state": "What the final URL/accessibility tree shows.",
  "step4_context_check": "How special context conditions apply to this result.",
  "step5_initial_verdict": "Your first verdict before self-correction.",
  "cov_q1": "Answer to Q1 (judge_context rules).",
  "cov_q2": "Answer to Q2 (trace vs accessibility tree).",
  "cov_q3": "Answer to Q3 (too strict / too lenient).",
  "cov_q4": "Answer to Q4 (consistency check).",
  "success": true or false,
  "reason": "A single, clear sentence explaining the FINAL corrected verdict."
}}
"""

    for attempt in range(retries):
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )

            contents = []
            parts = [{"text": prompt_text}]
            
            contents.append({
                "role": "user",
                "parts": parts
            })

            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            return json.loads(response.text)

        except json.JSONDecodeError as e:
            print(f"[Judge] JSON parsing error (attempt {attempt+1}/{retries}): {e}")
            continue
        except Exception as e:
            msg = str(e)
            is_rate_limit = "429" in msg or "503" in msg
            if is_rate_limit:
                fallbacks = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
                if model in fallbacks:
                    current_idx = fallbacks.index(model)
                    if current_idx < len(fallbacks) - 1:
                        next_model = fallbacks[current_idx + 1]
                        print(f"[Judge LLM] Error {msg[:20]} on {model} — falling back to {next_model} for attempt {attempt+1}/{retries}...")
                        model = next_model
                        continue 
                
                print(f"[Judge LLM] Rate limit hit on {model} — no more fallbacks available. Giving up.")
                break
            else:
                print(f"[Judge] Unexpected error (attempt {attempt+1}/{retries}): {e}")
                await asyncio.sleep(2)
                continue
    
    return {"success": False, "reason": "Evaluation failed due to LLM errors."}
