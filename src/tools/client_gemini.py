import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def ask_llm(prompt: str, system_prompt: str = "", model: str = "gemini-2.5-flash-lite", retries: int = 3) -> str:
    "Send the prompt to Gemini and return the response — retries on 429"
    import time, re
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
            if "429" in msg:
                fallback_model = "gemini-2.5-flash-lite" if model == "gemini-2.5-flash" else "gemini-2.5-flash"
                print(f"[LLM] Rate limit hit on {model} — switching to {fallback_model} (attempt {attempt+1}/{retries})...")
                model = fallback_model
            else:
                print(f"Unexpected error : {e}")
                return "Error : " + str(e)
    return "Error : max retries exceeded"




def ask_vision(image_path: str, prompt: str, model : str = "gemini-2.5-flash") -> str:
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
    model: str = "gemini-2.5-flash",
    retries: int = 3
) -> list:
    """
    Sends a prompt to Gemini and returns a parsed JSON list.
    Used by the Validator to get structured feedback.
    """
    import time, re
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
            print(f"JSON parsing error: {e}")
            return []
        except Exception as e:
            msg = str(e)
            if "429" in msg:
                fallback_model = "gemini-2.5-flash-lite" if model == "gemini-2.5-flash" else "gemini-2.5-flash"
                print(f"[LLM] Rate limit hit on {model} — switching to {fallback_model} (attempt {attempt+1}/{retries})...")
                model = fallback_model
            else:
                print(f"Unexpected error in ask_json: {e}")
                return []
    return []
