"""Parse the JSON output contract out of an LLM reply.

Every phase file ends with a small fenced ```json block; node behaviors call
``extract_json_block`` to read it. This is scaffolding shared by consumers of
any adapter, so it lives in the framework rather than in a specific adapter.
"""

from __future__ import annotations

import json


def extract_json_block(text: str) -> dict:
    """Pull the LAST fenced ```json block out of an LLM reply.

    Falls back to scanning for the last balanced object so a model that forgets
    the fence still works when it emits raw JSON. Returns ``{}`` when nothing
    parseable is found.
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
