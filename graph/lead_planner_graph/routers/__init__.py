"""Routers — the graph's decision points (branch functions).

The top of this package is only the routers themselves:

  planning.py — route_after_planning
  review.py   — route_after_review

The scaffolding they plug into — the ``@router`` decorator, the ``ROUTERS``
registry, and the ``get_router`` dispatch — lives in ``framework/``. A router
reads state and returns a key that an edge's ``map:`` in workflow.yaml resolves
to the next node.

Importing the router modules below runs their ``@router`` decorators, which is
what populates ``ROUTERS``. The public surface (``get_router``) is unchanged, so
``builder.py`` imports from here exactly as before.
"""

from .framework import ROUTERS, get_router, router

# Import for registration side effects (and to re-export the functions).
from .planning import route_after_planning
from .review import route_after_review

__all__ = [
    "ROUTERS",
    "get_router",
    "router",
    "route_after_planning",
    "route_after_review",
]
