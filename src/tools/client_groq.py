import os
import json
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

# Initialize the Groq client
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

async def ask_groq(
    prompt: str,
    system_prompt: str = "",
    model: str = "llama-3.3-70b-versatile",
    retries: int = 3
) -> dict:
    """
    Sends a prompt to Groq API and returns a parsed JSON dict.
    Compatible drop-in replacement for ask_llm_json.
    """
    for attempt in range(retries):
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            chat_completion = await client.chat.completions.create(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            response_text = chat_completion.choices[0].message.content
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return {}
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate_limit" in msg.lower():
                fallback_model = "llama-3.1-8b-instant" if model == "llama-3.3-70b-versatile" else "llama-3.3-70b-versatile"
                print(f"[LLM] Rate limit hit on {model} — switching to {fallback_model} (attempt {attempt+1}/{retries})...")
                model = fallback_model
            else:
                print(f"Unexpected error in ask_groq: {e}")
                return {}
                
    return {}
