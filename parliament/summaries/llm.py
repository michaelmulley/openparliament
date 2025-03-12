from collections import deque
from functools import wraps
import time
from typing import Literal

from django.conf import settings

import requests

DEFAULT_MODEL = 'google:gemini-2.0-flash'
# DEFAULT_MODEL = 'gemini-2.0-pro-exp-02-05'

class LLMProviderError(Exception):
    pass

def get_llm_response(instructions: str, text: str, model: str | None = None,
                     chat_history: list[tuple[Literal["user", "model"], str]] = [],
                     json_schema: dict = {}) -> tuple[str, dict]:
    if model is None:
        model = DEFAULT_MODEL
    provider, model = model.split(':', 1)
    if provider == 'google':
        response_text, metadata = _get_llm_response_google(instructions, text, model, chat_history, json_schema)
    elif provider == 'or':
        if json_schema:
            raise NotImplementedError
        response_text, metadata = _get_llm_response_openrouter(instructions, text, model, chat_history)
    else:
        raise ValueError(f"Unknown provider: {provider}")
    metadata['instructions'] = instructions
    return (response_text, metadata)

def rate_limit(n_calls: int, per: int):
    """
    A decorator that limits the rate of function calls to n_calls every per seconds..
    If the function is called more frequently, the decorator will make the caller
    sleep until the rate limit allows another call.
    """
    def decorator(func):
        call_timestamps = deque()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            
            while call_timestamps and current_time - call_timestamps[0] > per:
                call_timestamps.popleft()
            
            # If we've reached the limit, sleep until we can make another call
            if len(call_timestamps) >= n_calls:
                oldest_timestamp = call_timestamps[0]
                sleep_time = per - (current_time - oldest_timestamp)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    current_time = time.time()
            
            call_timestamps.append(current_time)
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

@rate_limit(n_calls=15, per=75)
def _get_llm_response_google(instructions, text, model, chat_history, json_schema) -> tuple[str, dict]:
    api_key = settings.GEMINI_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    contents = chat_history + [("user", text)]

    req = {
        "contents": [{
            "role": "user" if c[0] == "user" else "model",
            "parts": {
                "text": c[1]
            }
        } for c in contents],
        "system_instruction": {
            "parts": {"text": instructions}
        }
    }

    if json_schema:
        req['generationConfig'] = {
            "response_mime_type": "application/json",
            "response_schema": json_schema
        }

    response = requests.post(url, json=req, params=dict(key=api_key), headers={
        "Content-Type": "application/json",
    })
    if response.status_code != 200:
        try:
            message = response.json()['error']['message']
        except:
            message = response.text
        raise LLMProviderError(f"Google responded with status {response.status_code}: {message}")
    response_json = response.json()
    response_text = response_json['candidates'][0]['content']['parts'][0]['text']
    metadata = {
        "model": response_json['modelVersion'],
        "provider": "google-gemini",
        "tokens": {
            "request": response_json['usageMetadata']['promptTokenCount'],
            "response": response_json['usageMetadata']['candidatesTokenCount']
        }
    }
    return (response_text, metadata)

def _get_llm_response_openrouter(instructions, text, model, chat_history) -> tuple[str, dict]:
    messages = [("system", instructions)] + chat_history + [("user", text)]
    req = {
        "model": model, 
        "messages": [
          {
            "role": dict(user="user", system="system", model="assistant")[m[0]],
            "content": m[1]
          } for m in messages
        ],
        "provider": {"allow_fallbacks": False}
    }
    resp = requests.post(
      url="https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": "Bearer " + settings.OPENROUTER_API_KEY,
      },
      json=req)

    try:
        resp.raise_for_status()
        rj = resp.json()
        response_text = rj['choices'][0]['message']['content']
    except Exception as e:
        raise LLMProviderError(f"OpenRouter responded with status {resp.status_code}: {resp.text}")
    metadata = {
        "model": model if model == rj.get('model') else f"{rj.get('model')} (requested: {model})",
        "provider": f"openrouter: {rj.get('provider')}",
        "tokens": {
            "request": rj.get('usage', {}).get('prompt_tokens'),
            "response": rj.get('usage', {}).get('completion_tokens')
        }
    }
    return (response_text, metadata)
