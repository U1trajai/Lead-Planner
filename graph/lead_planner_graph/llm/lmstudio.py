"""LM Studio adapter — a local OpenAI-compatible server.

Satisfies the ``LLM`` Protocol structurally (no import needed). LM Studio exposes
``POST /v1/chat/completions`` at ``http://localhost:1234`` by default. Keeps
dependencies light by using ``httpx`` (already pulled in by langgraph) and never
imports a provider SDK.
"""

from __future__ import annotations


class LMStudioAdapter:
    """Talks to an LM Studio local server over its OpenAI-compatible API."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:1234/v1",
        temperature: float = 0.3,
        timeout: float = 600.0,
        api_key: str = "lm-studio",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.api_key = api_key

    def complete(self, system: str, user: str) -> str:
        import httpx  # imported lazily so tests with FakeLLM need no network stack

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
