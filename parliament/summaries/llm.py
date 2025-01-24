from typing import Literal

from django.conf import settings

import requests

DEFAULT_MODEL = 'google:gemini-2.0-flash'
# DEFAULT_MODEL = 'gemini-2.0-pro-exp-02-05'

class LLMProviderError(Exception):
    pass

def get_llm_response(instructions: str, text: str, model: str | None = None,
                     chat_history: list[tuple[Literal["user", "model"], str]] = []) -> tuple[str, dict]:
    if model is None:
        model = DEFAULT_MODEL
    provider, model = model.split(':', 1)
    if provider == 'google':
        response_text, metadata = _get_llm_response_google(instructions, text, model, chat_history)
    elif provider == 'or':
        response_text, metadata = _get_llm_response_openrouter(instructions, text, model, chat_history)
    else:
        raise ValueError(f"Unknown provider: {provider}")
    metadata['instructions'] = instructions
    return (response_text, metadata)

def _get_llm_response_google(instructions, text, model, chat_history) -> tuple[str, dict]:
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
