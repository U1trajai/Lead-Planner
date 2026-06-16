"""Branch after review: next component, capped fix re-delivery, or report."""

from __future__ import annotations

from ..state import PlannerState
from .framework import router


@router
def route_after_review(state: PlannerState) -> str:
    """Translate the review node's decision into the next node.

    ``next_action`` is one of:
      next     -> advance to the next component             -> delegate
      fix      -> re-deliver the current component as a fix  -> delegate
      done     -> queue exhausted, everything passed         -> report
      escalate -> fix cap hit without passing                -> report
    """
    action = state.get("next_action", "done")
    if action in ("next", "fix"):
        return "delegate"
    return "report"
