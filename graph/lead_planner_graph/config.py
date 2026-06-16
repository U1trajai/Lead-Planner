"""Load and validate ``workflow.yaml`` plus the phase instruction files.

The engine treats the YAML as the source of truth for topology and the phase
``.md`` files as the source of truth for instructions. Nothing about the
workflow shape or wording is hardcoded in Python — it is all read from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class NodeConfig:
    id: str
    type: str                       # agent | delegate | review
    instructions_path: Path
    interrupt: str | None = None    # clarification | approval | None
    terminal: bool = False
    _text: str | None = field(default=None, repr=False)

    @property
    def instructions(self) -> str:
        """Phase instructions, read fresh from disk and cached per process."""
        if self._text is None:
            self._text = self.instructions_path.read_text(encoding="utf-8")
        return self._text


@dataclass
class EdgeConfig:
    source: str
    to: str | None = None                  # plain edge
    router: str | None = None              # named branch function
    map: dict[str, str] = field(default_factory=dict)

    @property
    def is_conditional(self) -> bool:
        return self.router is not None


@dataclass
class WorkflowConfig:
    name: str
    description: str
    root: Path
    system_prompt: str
    entry: str
    settings: dict[str, Any]
    nodes: dict[str, NodeConfig]
    edges: dict[str, EdgeConfig]

    def setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)


_VALID_NODE_TYPES = {"agent", "delegate", "review"}
_VALID_INTERRUPTS = {"clarification", "approval", None}


def load_config(path: str | Path) -> WorkflowConfig:
    """Parse ``workflow.yaml`` into a validated :class:`WorkflowConfig`."""
    path = Path(path).resolve()
    root = path.parent
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if "entry" not in raw or "nodes" not in raw:
        raise ValueError("workflow.yaml must define 'entry' and 'nodes'")

    system_prompt = (root / raw["system_prompt"]).read_text(encoding="utf-8")

    nodes: dict[str, NodeConfig] = {}
    for node_id, spec in raw["nodes"].items():
        ntype = spec.get("type")
        if ntype not in _VALID_NODE_TYPES:
            raise ValueError(
                f"node '{node_id}': type must be one of {sorted(_VALID_NODE_TYPES)}, "
                f"got {ntype!r}"
            )
        interrupt = spec.get("interrupt")
        if interrupt not in _VALID_INTERRUPTS:
            raise ValueError(
                f"node '{node_id}': interrupt must be one of {sorted(x for x in _VALID_INTERRUPTS if x)} "
                f"or omitted, got {interrupt!r}"
            )
        instr = (root / spec["instructions"]).resolve()
        if not instr.is_file():
            raise FileNotFoundError(f"node '{node_id}': instructions file not found: {instr}")
        nodes[node_id] = NodeConfig(
            id=node_id,
            type=ntype,
            instructions_path=instr,
            interrupt=interrupt,
            terminal=bool(spec.get("terminal", False)),
        )

    edges: dict[str, EdgeConfig] = {}
    for source, spec in raw.get("edges", {}).items():
        edge = EdgeConfig(
            source=source,
            to=spec.get("to"),
            router=spec.get("router"),
            map=spec.get("map", {}) or {},
        )
        if edge.to is None and edge.router is None:
            raise ValueError(f"edge from '{source}' must set either 'to' or 'router'")
        edges[source] = edge

    if raw["entry"] not in nodes:
        raise ValueError(f"entry '{raw['entry']}' is not a defined node")

    return WorkflowConfig(
        name=raw.get("name", "workflow"),
        description=raw.get("description", ""),
        root=root,
        system_prompt=system_prompt,
        entry=raw["entry"],
        settings=raw.get("settings", {}) or {},
        nodes=nodes,
        edges=edges,
    )
