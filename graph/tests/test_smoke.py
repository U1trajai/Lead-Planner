"""End-to-end smoke tests driven by FakeLLM and injected fake runners.

These verify that LangGraph — not the model — owns the traversal: the phase
sequence, the human-in-the-loop interrupts, the delegate/review loop, and the
``max_fix_attempts`` cap. No LM Studio server or little-coder CLI is needed.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from langgraph.types import Command

from lead_planner_graph.builder import build_graph
from lead_planner_graph.config import load_config
from lead_planner_graph.llm import FakeLLM
from lead_planner_graph.nodes.framework.little_coder import (
    DelegationResult,
    PromptValidationError,
    build_command,
    validate_prompt,
)
from lead_planner_graph.nodes import NodeDeps

WORKFLOW = Path(__file__).resolve().parent.parent / "workflow.yaml"


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
def fake_gather(workdir: str) -> str:
    return f"(fake snapshot of {workdir})"


def make_run_command():
    def _run(command, *, workdir, timeout=3600.0):
        assert "-p --no-session" in command  # engine always appends the flags
        return DelegationResult(command=command, returncode=0, stdout="wrote files", stderr="")
    return _run


def make_run_tests(results):
    """results: list of booleans (pass/fail) consumed in order; last repeats."""
    state = {"i": 0}

    def _run(workdir, *, target=None, timeout=600.0):
        idx = min(state["i"], len(results) - 1)
        ok = results[idx]
        state["i"] += 1
        rc = 0 if ok else 1
        out = "1 passed" if ok else "1 failed: AssertionError"
        return DelegationResult(command="pytest", returncode=rc, stdout=out, stderr="")
    return _run


def build_app(run_tests):
    config = load_config(WORKFLOW)
    llm = FakeLLM()
    deps = NodeDeps(
        config=config,
        llm=llm,
        gather=fake_gather,
        run_command=make_run_command(),
        run_tests=run_tests,
    )
    return build_graph(config, llm, deps=deps)


def drive(app):
    """Run to completion, auto-servicing interrupts the way the CLI would."""
    thread = {"configurable": {"thread_id": uuid.uuid4().hex}}
    result = app.invoke({"request": "Build a rate limiter", "workdir": "/tmp/proj"}, thread)
    seen_interrupts = []
    while isinstance(result, dict) and result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        seen_interrupts.append(payload.get("type"))
        if payload.get("type") == "clarification":
            answer = {"window": "Sliding"}
        else:  # approval
            answer = "approve"
        result = app.invoke(Command(resume=answer), thread)
    return app.get_state(thread).values, seen_interrupts


# --------------------------------------------------------------------------- #
# command validation (the ported shell-safety checklist)
# --------------------------------------------------------------------------- #
def test_validate_rejects_backtick():
    with pytest.raises(PromptValidationError):
        validate_prompt("make a `RateLimiter` class")


def test_validate_rejects_newline_and_backslash():
    with pytest.raises(PromptValidationError):
        validate_prompt("line one\nline two")
    with pytest.raises(PromptValidationError):
        validate_prompt("a prompt with a backslash \\ in it")


def test_build_command_appends_flags_and_env():
    cmd = build_command("Implement a class named RateLimiter", model="qwen/x")
    assert cmd.endswith("-p --no-session")
    assert "PI_RETRY_PROVIDER_TIMEOUTMS=3600000" in cmd
    assert "--provider lmstudio" in cmd


# --------------------------------------------------------------------------- #
# full traversal
# --------------------------------------------------------------------------- #
def test_happy_path_with_one_fix():
    # tests fail once, then pass -> exactly one fix, then done.
    app = build_app(make_run_tests([False, True]))
    final, interrupts = drive(app)

    assert interrupts == ["clarification", "approval"]  # both human gates fired
    assert final["intent"]                              # intent resolved
    assert len(final["components"]) == 1
    assert final["fix_attempts"] == 1                   # one fix happened
    assert final["last_passed"] is True
    assert final.get("escalated") in (None, False)
    assert final["report"]                              # report produced


def test_escalates_after_cap():
    # tests always fail -> engine caps at max_fix_attempts (2) then escalates.
    app = build_app(make_run_tests([False]))
    final, _ = drive(app)

    assert final["fix_attempts"] == 2                   # capped, not infinite
    assert final["escalated"] is True
    assert final["last_passed"] is False
    assert final["report"]                              # still reports, with escalation


def test_no_components_skips_to_report():
    # planning router sends an empty queue straight to report (no delegation).
    config = load_config(WORKFLOW)

    class NoCompLLM(FakeLLM):
        def complete(self, system, user):
            if self._phase(system) == "planning":
                return '# Plan\nNothing to build.\n```json\n{"artifact_type":"design_doc","components":[]}\n```'
            return super().complete(system, user)

    llm = NoCompLLM()
    deps = NodeDeps(config=config, llm=llm, gather=fake_gather,
                    run_command=make_run_command(), run_tests=make_run_tests([True]))
    app = build_graph(config, llm, deps=deps)

    thread = {"configurable": {"thread_id": uuid.uuid4().hex}}
    result = app.invoke({"request": "Just plan it", "workdir": "/tmp/proj"}, thread)
    while isinstance(result, dict) and result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        result = app.invoke(Command(resume={"x": "y"} if payload.get("type") == "clarification" else "approve"), thread)
    final = app.get_state(thread).values

    assert final["components"] == []
    assert "delegate" not in " ".join(final.get("log", []))   # delegation never ran
    assert final["report"]
