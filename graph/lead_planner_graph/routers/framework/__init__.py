"""The router framework — the scaffolding routers plug into.

The ``@router`` decorator, the ``ROUTERS`` registry, and the ``get_router``
dispatch. Depends on nothing but stdlib typing, and never on a router module —
the dependency runs one way: routers -> framework.
"""

from .registry import ROUTERS, get_router, router

__all__ = ["ROUTERS", "get_router", "router"]
