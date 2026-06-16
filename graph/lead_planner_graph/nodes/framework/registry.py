"""Node-type dispatch — the wiring that turns a ``type`` from workflow.yaml into
a built node.

The framework is deliberately node-agnostic: it never imports ``agent``,
``delegate``, or ``review``. Instead each node module decorates its builder with
``@node_type("...")`` and registers itself (the same pattern as ``@router`` in
routers.py). Adding a new node type is just a new file with the decorator — no
edit here.
"""

from __future__ import annotations

from typing import Callable

from ...config import NodeConfig
from .deps import NodeDeps

# type name (from workflow.yaml) -> builder(node, deps) -> node callable
NODE_BUILDERS: dict[str, Callable] = {}


def node_type(name: str):
    """Register the decorated builder under a workflow node ``type`` name."""

    def register(builder: Callable) -> Callable:
        NODE_BUILDERS[name] = builder
        return builder

    return register


def build_node(node: NodeConfig, deps: NodeDeps):
    try:
        return NODE_BUILDERS[node.type](node, deps)
    except KeyError:
        raise KeyError(f"unknown node type {node.type!r}; known: {sorted(NODE_BUILDERS)}")
