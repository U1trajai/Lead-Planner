"""Named branch functions — the graph's decision points.

``workflow.yaml`` references these by name in an edge's ``router:`` field and
maps each return value to a destination node via ``map:``. Keeping them here (and
small) means the *topology* stays editable in YAML while the handful of genuine
decisions stay readable and testable in one place.

A router's job is only to read state and return a key. The substantive work
(running tests, counting attempts against ``max_fix_attempts``) happens in the
nodes and is recorded in state as ``next_action`` — the routers just translate
that into the next hop, so the branch logic and the node logic never drift apart.
"""

from __future__ import annotations

from .state import PlannerState

# name -> callable registry, populated by the @router decorator below.
ROUTERS: dict[str, "callable"] = {}


def router(fn):
    ROUTERS[fn.__name__] = fn
    return fn


@router
def route_after_planning(state: PlannerState) -> str:
    """Skip delegation entirely when the plan has no implementation components."""
    components = state.get("components") or []
    return "delegate" if components else "report"


@router
def route_after_review(state: PlannerState) -> str:
    """Translate the review node's decision into the next node.

    ``next_action`` is one of:
      next     -> advance to the next component            -> delegate
      fix      -> re-deliver the current component as a fix -> delegate
      done     -> queue exhausted, everything passed        -> report
      escalate -> fix cap hit without passing               -> report
    """
    action = state.get("next_action", "done")
    if action in ("next", "fix"):
        return "delegate"
    return "report"


def get_router(name: str):
    try:
        return ROUTERS[name]
    except KeyError:
        raise KeyError(
            f"router '{name}' referenced in workflow.yaml is not defined in routers.py; "
            f"available: {sorted(ROUTERS)}"
        )
