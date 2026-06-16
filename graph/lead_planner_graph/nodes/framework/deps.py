"""``NodeDeps`` — everything a node needs, injected so behaviors stay testable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ...config import WorkflowConfig
from ...llm import LLM
from . import little_coder
from .toolkit import gather_directory

GatherFn = Callable[[str], str]
RunCmdFn = Callable[..., little_coder.DelegationResult]
RunTestsFn = Callable[..., little_coder.DelegationResult]


@dataclass
class NodeDeps:
    """Everything a node needs, injected so behaviors stay testable."""

    config: WorkflowConfig
    llm: LLM
    gather: GatherFn = field(default=None)            # type: ignore[assignment]
    run_command: RunCmdFn = field(default=little_coder.run_command)
    run_tests: RunTestsFn = field(default=little_coder.run_tests)

    def __post_init__(self) -> None:
        if self.gather is None:
            self.gather = gather_directory
