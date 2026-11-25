"""Is each LLM key working? Sends one tiny question straight to every provider.

    uv run python scripts/llm_ping.py

There is no gateway here on purpose: this is the raw HTTP call, so you see what a provider
really sends back. Keys and model names come from .env (GEMINI_API_KEY, GROQ_API_KEY ...).
"""

import sys
import time

import httpx

from rti_mate.config import get_settings

HINTS = {
    400: "the request or the API key is wrong: read the provider's message below",
    401: "the API key is wrong or was deleted: copy it again into .env",
    403: "this key is not allowed to use this model",
    404: "no such model: check the model name in .env against the provider's model list",
    429: "rate limit: wait a minute (free tiers are small), then try again",
}


def ping(name: str, base_url: str, key: str, model: str) -> bool:
    if not key:
        print(f"{name:7} NO KEY   add it to .env")
        return False
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with one word: pong"}],
        "temperature": 0,
    }
    started = time.perf_counter()
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=30,
        )
    except httpx.TransportError as exc:
        print(f"{name:7} FAILED   {type(exc).__name__}: is the internet working?")
        return False
    ms = int((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        hint = HINTS.get(response.status_code, "the provider has a problem: try again later")
        print(f"{name:7} FAILED   HTTP {response.status_code}: {hint}")
        print("        ", response.text[:300].replace("\n", " "))
        return False
    data = response.json()
    answer = (data["choices"][0]["message"].get("content") or "").strip()
    usage = data.get("usage") or {}
    print(
        f"{name:7} OK       {model} said {answer!r} in {ms} ms, "
        f"tokens in={usage.get('prompt_tokens', '?')} out={usage.get('completion_tokens', '?')}"
    )
    return True


def main() -> int:
    s = get_settings()
    results = [
        ping("gemini", s.llm_primary_base_url, s.gemini_api_key, s.llm_primary_model),
        ping("groq", s.llm_fallback_base_url, s.groq_api_key, s.llm_fallback_model),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
