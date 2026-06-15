from collections import deque
from functools import wraps
import time
from typing import Literal

from django.conf import settings

import requests

class llms:
    QUICK = 'or:@preset/op-quick'
    THINKING = 'or:@preset/op-thinking'
    EXPERT = 'google:gemini-2.5-pro'

class LLMProviderError(Exception):
    pass

def get_llm_response(instructions: str, text: str, model: str | None = None,
                     chat_history: list[tuple[Literal["user", "model"], str]] = [],
                     json: bool | dict = False, temperature: float | None = None,
                     top_p: float | None = None) -> tuple[str, dict]:
    if model is None:
        model = llms.QUICK
    provider, model = model.split(':', 1)
    if provider == 'google':
        response_text, metadata = _get_llm_response_google(instructions, text, model, chat_history, json,
                                                            temperature, top_p)
    elif provider == 'or':  
        response_text, metadata = _get_llm_response_openrouter(instructions, text, model, chat_history, json)
    else:
        raise ValueError(f"Unknown provider: {provider}")

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
def _get_llm_response_google(instructions, text, model, chat_history, json,
                             temperature, top_p) -> tuple[str, dict]:
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
        },
        'generationConfig': {}
    }

    if json:
        req['generationConfig']['response_mime_type'] = "application/json"
        if isinstance(json, dict):
            req['generationConfig']['response_schema'] = json

    if temperature:
        req['generationConfig']['temperature'] = temperature
    if top_p:
        req['generationConfig']['topP'] = top_p

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
    if response_json['candidates'][0]['finishReason'] != 'STOP':
        raise LLMProviderError(f"Google responded with finish reason {response_json['candidates'][0]['finishReason']}")
    response_text = response_json['candidates'][0]['content']['parts'][0]['text']
    thought_tokens = response_json['usageMetadata'].get('thoughtsTokenCount', 0)
    metadata = {
        "model": response_json['modelVersion'],
        "provider": "google-gemini",
        "tokens": {
            "request": response_json['usageMetadata']['promptTokenCount'],
            "response": response_json['usageMetadata']['candidatesTokenCount'] - thought_tokens,
            "thought": thought_tokens
        }
    }
    if temperature:
        metadata["temperature"] = temperature
    if top_p:
        metadata["top_p"] = top_p

    return (response_text, metadata)

def _get_llm_response_openrouter(instructions, text, model, chat_history, json) -> tuple[str, dict]:
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
    if json:
        if isinstance(json, dict):
            req['response_format'] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "op-json",
                    "strict": True,
                    "schema": json
                }
            }
        else:
            req['response_format'] = dict(type='json_object')

    resp = requests.post(
      url="https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": "Bearer " + settings.OPENROUTER_API_KEY,
      },
      json=req)

    if resp.status_code != 200:
        try:
            message = resp.json()['error']['message']
        except:
            message = resp.text
        raise LLMProviderError(f"OpenRouter responded with status {resp.status_code}: {message}")

    rj = resp.json()
    if rj.get('error'):
        raise LLMProviderError(f"OpenRouter responded with error: {rj['error']}")
    choice = rj['choices'][0]
    finish_reason = choice.get('finish_reason')
    if finish_reason != 'stop':
        native_finish_reason = choice.get('native_finish_reason')
        error_message = choice.get('error', {}).get('message')
        details = []
        if native_finish_reason and native_finish_reason != finish_reason:
            details.append(f"native finish reason {native_finish_reason}")
        if error_message:
            details.append(error_message)
        detail_suffix = f" ({'; '.join(details)})" if details else ""
        raise LLMProviderError(
            f"OpenRouter responded with finish reason {finish_reason}{detail_suffix}"
        )

    response_text = choice['message']['content']
    metadata = {
        "model": model if model == rj.get('model') else f"{rj.get('model')} (requested: {model})",
        "provider": f"openrouter: {rj.get('provider')}",
        "tokens": {
            "request": rj.get('usage', {}).get('prompt_tokens'),
            "response": rj.get('usage', {}).get('completion_tokens')
        }
    }
    return (response_text, metadata)
