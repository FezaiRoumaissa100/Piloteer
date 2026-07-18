import aiohttp
import json

async def ask_ollama_json(prompt: str, system_prompt: str = "", model: str = "qwen2.5:7b") -> dict:
    """
    Calls the local Ollama server to generate a JSON response.
    Useful as a fallback when Cloud APIs are rate-limited or unavailable.
    """
    url = "http://127.0.0.1:11434/api/chat"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "format": "json",  # Forces Ollama to return valid JSON
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    print(f"[Ollama] API error {response.status}: {await response.text()}")
                    return {}
                
                result = await response.json()
                content = result.get("message", {}).get("content", "{}")
                return json.loads(content)
    except json.JSONDecodeError:
        print("[Ollama] JSON parsing error in response.")
        return {}
    except aiohttp.ClientConnectorError:
        print("[Ollama] Cannot connect")
        return {}
    except Exception as e:
        print(f"[Ollama] Unexpected error: {e}")
        return {}
