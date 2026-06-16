"""CLI runner: drive the compiled graph and service its human-in-the-loop pauses.

Usage:
  python -m lead_planner_graph.run --request "Build a thread-safe rate limiter" \
      --workdir /path/to/project

  python -m lead_planner_graph.run --demo        # no LM Studio / little-coder needed

The runner invokes the graph; whenever a node raises a LangGraph interrupt it
collects the user's input from stdin and resumes with ``Command(resume=...)`` —
the resume value becomes the return value of ``interrupt()`` inside the node.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from langgraph.types import Command

from .builder import build_graph
from .config import load_config
from .llm import LMStudioAdapter

DEFAULT_WORKFLOW = Path(__file__).resolve().parent.parent / "workflow.yaml"


def _get_interrupt(result: dict):
    """Return the interrupt payload if the last step paused, else None."""
    intr = result.get("__interrupt__") if isinstance(result, dict) else None
    if not intr:
        return None
    first = intr[0]
    return getattr(first, "value", first)


def _ask_clarification(payload: dict) -> dict:
    print("\n=== Clarifying questions ===")
    answers = {}
    for q in payload.get("questions", []):
        opts = q.get("options") or []
        opt_str = f" (options: {', '.join(opts)})" if opts else ""
        ans = input(f"  {q.get('question','?')}{opt_str}\n  > ").strip()
        answers[q.get("question", "?")] = ans
    return answers


def _ask_approval(payload: dict) -> str:
    print("\n=== Plan for approval ===")
    print(payload.get("plan", ""))
    comps = payload.get("components", [])
    print(f"\nComponents queued ({len(comps)}):")
    for i, c in enumerate(comps):
        print(f"  {i + 1}. {c.get('name','?')}: {c.get('summary','')}")
    return input("\nApprove? (enter 'approve', or type revision feedback)\n  > ").strip()


def _service_interrupt(payload):
    if isinstance(payload, dict) and payload.get("type") == "clarification":
        return _ask_clarification(payload)
    if isinstance(payload, dict) and payload.get("type") == "approval":
        return _ask_approval(payload)
    # Unknown interrupt shape — show it and pass through a raw line.
    return input(f"Input required: {payload}\n  > ").strip()


def run(request: str, workdir: str, *, workflow=DEFAULT_WORKFLOW, llm=None, verbose=True) -> dict:
    config = load_config(workflow)
    if llm is None:
        llm = LMStudioAdapter(model=config.setting("orchestrator_model", "openai/gpt-oss-20b"))
    app = build_graph(config, llm)
    thread = {"configurable": {"thread_id": uuid.uuid4().hex}}

    result = app.invoke({"request": request, "workdir": workdir}, thread)
    while (payload := _get_interrupt(result)) is not None:
        answer = _service_interrupt(payload)
        result = app.invoke(Command(resume=answer), thread)

    final = app.get_state(thread).values
    if verbose:
        print("\n=== Trace ===")
        for line in final.get("log", []):
            print(" ", line)
        print("\n=== Report ===")
        print(final.get("report", "(no report produced)"))
    return final


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run the lead-planner LangGraph workflow.")
    p.add_argument("--request", help="the user request to plan and build")
    p.add_argument("--workdir", default=".", help="directory the run operates in")
    p.add_argument("--workflow", default=str(DEFAULT_WORKFLOW), help="path to workflow.yaml")
    p.add_argument("--demo", action="store_true", help="run with the built-in FakeLLM (no servers)")
    args = p.parse_args(argv)

    llm = None
    if args.demo:
        from .llm import FakeLLM

        llm = FakeLLM()
        request = args.request or "Build a thread-safe rate limiter with deterministic tests"
    else:
        if not args.request:
            print("error: --request is required (or use --demo)", file=sys.stderr)
            return 2
        request = args.request

    run(request, args.workdir, workflow=args.workflow, llm=llm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
