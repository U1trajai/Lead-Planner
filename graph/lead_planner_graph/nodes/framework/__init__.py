"""The node framework — the scaffolding nodes plug into.

Dependency injection (``NodeDeps``), the shared authoring toolkit, the
little-coder CLI integration, and the node-type dispatch (``@node_type`` /
``build_node``). This package depends on config / llm / state, but never on a
node module — the dependency runs one way: nodes -> framework.
"""

from . import little_coder, toolkit
from .deps import GatherFn, NodeDeps, RunCmdFn, RunTestsFn
from .registry import NODE_BUILDERS, build_node, node_type
from .toolkit import gather_directory

__all__ = [
    "toolkit",
    "little_coder",
    "NodeDeps",
    "GatherFn",
    "RunCmdFn",
    "RunTestsFn",
    "NODE_BUILDERS",
    "build_node",
    "node_type",
    "gather_directory",
]
