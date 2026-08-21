import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL = "gemini-3.5-flash-lite"

_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def _build_llm(model: str = DEFAULT_MODEL, json_mode: bool = False) -> ChatGoogleGenerativeAI:
    config: dict = dict(
        model=model,
        google_api_key=_API_KEY,
        max_retries=2,
    )
    if json_mode:
        config["response_mime_type"] = "application/json"

    primary = ChatGoogleGenerativeAI(**config)
    fallback_models = [
        ChatGoogleGenerativeAI(
            model=m,
            google_api_key=_API_KEY,
            max_retries=2,
            **({"response_mime_type": "application/json"} if json_mode else {}),)
        for m in _FALLBACK_MODELS
        if m != model
    ]
    return primary.with_fallbacks(fallback_models) if fallback_models else primary


def _extract_usage(response) -> dict:
    meta = getattr(response, "usage_metadata", None) or {}
    if isinstance(meta, dict):
        input_tokens = meta.get("input_tokens", 0)
        output_tokens = meta.get("output_tokens", 0)
        cached_tokens = meta.get("input_token_details", {}).get("cache_read", 0)
    else:
        input_tokens = getattr(meta, "input_tokens", 0) or 0
        output_tokens = getattr(meta, "output_tokens", 0) or 0
        cached_tokens = 0
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
    }


async def ask_llm_json(prompt: str, system_prompt: str = "", model: str = DEFAULT_MODEL, retries: int = 4) -> tuple:
    models_to_try = [model] + [m for m in _FALLBACK_MODELS if m != model]
    
    for attempt in range(retries):
        current_model = models_to_try[attempt % len(models_to_try)]
        print(f"\n[LLM] Attempt {attempt + 1}/{retries} | Active Model: {current_model}")
        
        llm = ChatGoogleGenerativeAI(
            model=current_model,
            google_api_key=_API_KEY,
            max_retries=1,
            response_mime_type="application/json"
        )
        
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
            
        try:
            response = await llm.ainvoke(messages)
            raw = response.content
            if isinstance(raw, list):
                raw = raw[0].get("text", "") if isinstance(raw[0], dict) else str(raw[0])
            
            data = json.loads(raw)
            usage = _extract_usage(response)
            usage["model"] = current_model
            print(f"[LLM] SUCCESS! Model: {current_model}")
            return data, usage

        except json.JSONDecodeError as e:
            print(f"[LLM] JSON Parse error: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[LLM] API Error: {type(e).__name__} - {e}")
            await asyncio.sleep(3)

    return {}, {}
