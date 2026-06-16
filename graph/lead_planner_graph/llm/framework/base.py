"""The LLM contract every adapter implements.

The engine never talks to a specific provider directly — it talks to this
``LLM`` Protocol. Anything with a ``complete(system, user) -> str`` method
satisfies it (structural typing), so the project stays model-agnostic and
adapters don't even need to import this.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLM(Protocol):
    """Minimal contract every adapter must satisfy."""

    def complete(self, system: str, user: str) -> str:
        """Return the model's text completion for a system + user prompt."""
        ...
