"""A deterministic LLM adapter for the test suite and ``run.py --demo``.

Satisfies the ``LLM`` Protocol structurally. Lets the whole graph — including
interrupts and the delegate/review loop — run without a live LM Studio server or
the little-coder CLI. Picks a reply by detecting the current phase from the
system prompt (``# Current phase: <id>``).
"""

from __future__ import annotations

import json
import re


class FakeLLM:
    def __init__(self, component_name: str = "RateLimiter") -> None:
        self.component_name = component_name
        self.calls: list[str] = []

    @staticmethod
    def _phase(system: str) -> str:
        m = re.search(r"# Current phase: (\w+)", system)
        return m.group(1) if m else "unknown"

    def complete(self, system: str, user: str) -> str:
        phase = self._phase(system)
        self.calls.append(phase)

        if phase == "intent":
            if "User answers" in user:
                return (
                    "Intent is now clear.\n"
                    '```json\n'
                    + json.dumps(
                        {
                            "intent": f"Build a thread-safe {self.component_name} with deterministic tests.",
                            "questions": [],
                        }
                    )
                    + "\n```"
                )
            return (
                "I need one clarification.\n"
                '```json\n'
                + json.dumps(
                    {
                        "intent": "User wants a rate limiter; one detail is ambiguous.",
                        "questions": [
                            {
                                "header": "Window kind",
                                "question": "Sliding or fixed window?",
                                "options": ["Sliding", "Fixed"],
                            }
                        ],
                    }
                )
                + "\n```"
            )

        if phase == "planning":
            return (
                f"# Plan\nUser story: As a developer, I want a {self.component_name}.\n\n"
                '```json\n'
                + json.dumps(
                    {
                        "artifact_type": "design_doc",
                        "components": [
                            {
                                "name": self.component_name,
                                "summary": "thread-safe sliding-window limiter with deterministic tests",
                            }
                        ],
                    }
                )
                + "\n```"
            )

        if phase == "delegate":
            return (
                '```json\n'
                + json.dumps(
                    {
                        "prompt": (
                            f"Implement a class named {self.component_name} that allows at most a "
                            "configured number of requests per user within a sliding time window. "
                            "Generate deterministic unit tests in a separate file using an injected "
                            "clock, and do not run the tests."
                        )
                    }
                )
                + "\n```"
            )

        if phase == "review":
            return (
                "Reviewed.\n"
                '```json\n'
                + json.dumps({"passed": True, "notes": "looks correct", "diagnosis": ""})
                + "\n```"
            )

        # report
        return f"Done. Built {self.component_name} and its tests; all tests pass."
