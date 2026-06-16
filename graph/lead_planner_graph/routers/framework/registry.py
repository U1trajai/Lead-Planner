"""Router dispatch — the wiring that maps a router name to its function.

The framework is router-agnostic: it never imports a specific ``route_*``
function. Each router module decorates its function with ``@router`` to
self-register (the same pattern as ``@node_type`` in nodes/framework). Adding a
branch point is just a new file with the decorator — no edit here.

``workflow.yaml`` references a router by name in an edge's ``router:`` field;
``get_router`` looks it up, and the edge's ``map:`` resolves the returned key to
the next node.
"""

from __future__ import annotations

from typing import Callable

# router name -> fn(state) -> next-node key
ROUTERS: dict[str, Callable] = {}


def router(fn: Callable) -> Callable:
    """Register the decorated function under its own name."""
    ROUTERS[fn.__name__] = fn
    return fn


def get_router(name: str) -> Callable:
    try:
        return ROUTERS[name]
    except KeyError:
        raise KeyError(
            f"router '{name}' referenced in workflow.yaml is not defined; "
            f"available: {sorted(ROUTERS)}"
        )
