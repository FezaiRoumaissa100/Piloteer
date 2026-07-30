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
) -> list:
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
            return json.loads(response.text)

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
                await asyncio.sleep(2)
                continue
    return []


