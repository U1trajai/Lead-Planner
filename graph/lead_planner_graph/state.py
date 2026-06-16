"""The state object that flows through the graph.

LangGraph threads one typed dict through every node; each node returns a partial
update that is merged in. This is the single source of truth the routers read to
decide the next hop, so the traversal logic the LLM used to carry in its head now
lives in explicit, inspectable fields here.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class Component(TypedDict, total=False):
    """One implementation unit in the delegation queue."""

    name: str
    summary: str


class PlannerState(TypedDict, total=False):
    # --- input ---
    request: str                 # the original user request
    workdir: str                 # directory the run operates in

    # --- intent phase ---
    context: str                 # read-only snapshot of the working directory
    clarifications: list[dict[str, Any]]   # Q&A gathered via the interrupt
    intent: str                  # resolved, unambiguous statement of intent

    # --- planning phase ---
    plan: str                    # the human-readable planning artifact
    artifact_type: str           # design_doc | todo_list | work_breakdown
    components: list[Component]   # ordered delegation queue
    current_index: int           # which component is being built

    # --- delegate / review loop ---
    fix_attempts: int            # fixes spent on the CURRENT component
    last_prompt: str             # last little-coder prompt text
    last_command: str            # last full validated command
    last_run_output: str         # little-coder stdout/stderr
    last_test_output: str        # pytest output the orchestrator captured
    last_passed: bool            # did the current component's tests pass
    diagnosis: str               # distilled corrected-behavior note for a fix

    # --- routing decision the review node hands to the router ---
    next_action: str             # next | fix | done | escalate

    # --- terminal ---
    report: str                  # final message to the user
    escalated: bool              # True if a fix loop hit the cap

    # --- accumulating trace (append-only) ---
    log: Annotated[list[str], operator.add]
