"""Node behaviors — the work each phase does.

The top of this package is *only* the nodes themselves:

  agent.py     — an LLM reasoning step (intent / planning / report)
  delegate.py  — builds + validates + runs the little-coder command
  review.py    — runs tests, diagnoses, records the routing decision

All the scaffolding they plug into — dependency injection, the shared authoring
toolkit, and the node-type dispatch — lives in ``framework/``. Behavior is
selected by config flags (``interrupt``, ``terminal``), never by hardcoded node
ids, so renaming a node in the YAML changes nothing here.

Importing the node modules below runs their ``@node_type`` decorators, which is
what populates ``NODE_BUILDERS``. The public surface (``NodeDeps``,
``build_node``) is unchanged, so ``builder.py`` and the tests import from here
exactly as before.
"""

from .framework import (
    NODE_BUILDERS,
    GatherFn,
    NodeDeps,
    RunCmdFn,
    RunTestsFn,
    build_node,
    gather_directory,
    node_type,
)

# Import for registration side effects (and to re-export the builders).
from .agent import make_agent_node
from .delegate import make_delegate_node
from .review import make_review_node

__all__ = [
    "NodeDeps",
    "GatherFn",
    "RunCmdFn",
    "RunTestsFn",
    "gather_directory",
    "node_type",
    "make_agent_node",
    "make_delegate_node",
    "make_review_node",
    "NODE_BUILDERS",
    "build_node",
]
