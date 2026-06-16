"""Entrypoint for ``langgraph dev`` / LangGraph Studio.

``langgraph.json`` points at the ``graph`` object below. It is the **uncompiled**
StateGraph on purpose: the LangGraph dev server attaches its own persistence
(so the clarification/approval interrupts pause and resume in the Studio UI) and
compiles it for you. Nothing about the workflow is defined here — it is read from
``workflow.yaml`` and ``phases/`` exactly like the CLI runner.

Configuration comes from the environment (see ``.env.example``) so you never
edit code to point at a different LM Studio server or model.
"""

from __future__ import annotations

import os
from pathlib import Path

from lead_planner_graph.builder import build_state_graph
from lead_planner_graph.config import load_config
from lead_planner_graph.llm import LMStudioAdapter

_WORKFLOW = Path(__file__).resolve().parent.parent / "workflow.yaml"
_config = load_config(_WORKFLOW)

# The orchestrator's reasoning model (distinct from the worker model little-coder
# drives, which is set in workflow.yaml as worker_model).
_llm = LMStudioAdapter(
    model=os.getenv("ORCHESTRATOR_MODEL", _config.setting("orchestrator_model", "qwen/qwen3.5-9B")),
    base_url=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
)

# The variable langgraph.json resolves. Uncompiled so the platform owns persistence.
graph = build_state_graph(_config, _llm)
