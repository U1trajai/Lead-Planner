"""Pluggable LLM layer.

The engine never talks to a specific provider directly — it talks to the ``LLM``
Protocol. Anything with a ``complete(system, user) -> str`` method satisfies it,
so the project stays model-agnostic (per the repo README). An LM Studio adapter
is shipped so the graph runs out of the box against a local server, and
``fake_llm.FakeLLM`` implements the same Protocol for tests and demos.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLM(Protocol):
    """Minimal contract every adapter must satisfy."""

    def complete(self, system: str, user: str) -> str:
        """Return the model's text completion for a system + user prompt."""
        ...


class LMStudioAdapter:
    """Talks to an LM Studio local server over its OpenAI-compatible API.

    LM Studio exposes ``POST /v1/chat/completions`` at ``http://localhost:1234``
    by default. This adapter keeps dependencies light by using ``httpx`` (already
    pulled in by langgraph) and never imports a provider SDK.
    """

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


def extract_json_block(text: str) -> dict:
    """Pull the LAST fenced ```json block out of an LLM reply.

    Every phase file ends with a small JSON output contract; the node behaviors
    parse it with this helper. Falls back to scanning for the last balanced
    object so a model that forgets the fence still works when it emits raw JSON.
    Returns ``{}`` when nothing parseable is found.
    """
    fence = "```"
    blocks: list[str] = []
    idx = 0
    while True:
        start = text.find(fence + "json", idx)
        if start == -1:
            break
        body_start = text.find("\n", start)
        if body_start == -1:
            break
        end = text.find(fence, body_start)
        if end == -1:
            break
        blocks.append(text[body_start + 1 : end])
        idx = end + len(fence)

    candidates = list(reversed(blocks))
    # Fallback: any fenced block, then the last {...} span.
    if not candidates and fence in text:
        parts = text.split(fence)
        candidates = [p for i, p in enumerate(parts) if i % 2 == 1]
        candidates.reverse()
    if not candidates:
        last_open = text.rfind("{")
        last_close = text.rfind("}")
        if last_open != -1 and last_close > last_open:
            candidates = [text[last_open : last_close + 1]]

    for block in candidates:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    return {}
