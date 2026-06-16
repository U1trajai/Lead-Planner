"""lead_planner_graph — a config-driven LangGraph engine for the lead-planner.

The workflow (phase sequence, branches, loops, retry cap, human pauses) is
defined in ``workflow.yaml`` and the per-phase instructions in ``phases/``.
This package is the generic engine that reads those files and builds a LangGraph
``StateGraph`` from them. You change workflows by editing the files, not the
code.
"""

from .builder import build_graph, build_state_graph
from .config import WorkflowConfig, load_config
from .llm import LLM, LMStudioAdapter
from .state import PlannerState

__all__ = [
    "build_graph",
    "build_state_graph",
    "WorkflowConfig",
    "load_config",
    "LLM",
    "LMStudioAdapter",
    "PlannerState",
]
