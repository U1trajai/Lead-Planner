"""Branch after planning: go build, or skip straight to the report."""

from __future__ import annotations

from ..state import PlannerState
from .framework import router


@router
def route_after_planning(state: PlannerState) -> str:
    """Skip delegation entirely when the plan has no implementation components."""
    components = state.get("components") or []
    return "delegate" if components else "report"
