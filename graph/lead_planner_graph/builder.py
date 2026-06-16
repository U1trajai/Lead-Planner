"""Compile a LangGraph ``StateGraph`` from the workflow config + phase files.

This is the bridge: it reads :class:`WorkflowConfig`, wires each node behavior
and each edge/router declared in ``workflow.yaml``, and returns a compiled graph
with a checkpointer (required for interrupts/human-in-the-loop). No phase
wording or topology is written here — it all comes from the files.
"""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .config import WorkflowConfig, load_config
from .llm import LLM
from .nodes import NodeDeps, build_node
from .routers import get_router
from .state import PlannerState


def build_state_graph(
    config: str | Path | WorkflowConfig,
    llm: LLM,
    *,
    deps: NodeDeps | None = None,
) -> StateGraph:
    """Build the **uncompiled** ``StateGraph`` from the workflow config.

    This is the form ``langgraph dev`` / LangGraph Studio wants: the platform
    attaches its own persistence (so interrupts and resume work in the UI) and
    compiles it for you. ``llm`` is any object satisfying the :class:`LLM`
    Protocol; ``deps`` lets tests inject fake command/test runners.
    """
    if not isinstance(config, WorkflowConfig):
        config = load_config(config)
    if deps is None:
        deps = NodeDeps(config=config, llm=llm)

    graph = StateGraph(PlannerState)

    # Nodes
    for node in config.nodes.values():
        graph.add_node(node.id, build_node(node, deps))

    # Entry
    graph.add_edge(START, config.entry)

    # Edges (plain + conditional)
    for source, edge in config.edges.items():
        if edge.is_conditional:
            path_map = {key: (END if dest == "END" else dest) for key, dest in edge.map.items()}
            graph.add_conditional_edges(source, get_router(edge.router), path_map)
        else:
            dest = END if edge.to == "END" else edge.to
            graph.add_edge(source, dest)

    # Terminal nodes with no outgoing edge fall through to END.
    for node in config.nodes.values():
        if node.terminal and node.id not in config.edges:
            graph.add_edge(node.id, END)

    return graph


def build_graph(
    config: str | Path | WorkflowConfig,
    llm: LLM,
    *,
    checkpointer=None,
    deps: NodeDeps | None = None,
):
    """Return a **compiled** LangGraph app — for the standalone CLI runner.

    Attaches a :class:`MemorySaver` by default so the CLI's interrupt/resume
    loop has persistence. When running under ``langgraph dev`` you instead want
    :func:`build_state_graph`, which lets the platform own persistence.
    """
    sg = build_state_graph(config, llm, deps=deps)
    return sg.compile(checkpointer=checkpointer or MemorySaver())
