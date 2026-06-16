"""Node behaviors — the work each phase does.

There are three node *types*, referenced by name from ``workflow.yaml``:

  agent    — an LLM reasoning step. Used by intent (gathers a read-only dir
             snapshot, then asks clarifying questions via a LangGraph interrupt),
             planning (produces the artifact + component queue, then interrupts
             for approval), and report (terminal prose).
  delegate — turns the current component into a validated little-coder command
             and runs it.
  review   — runs the component's tests, lets the LLM diagnose, then records the
             routing decision (next / fix / done / escalate), enforcing the
             ``max_fix_attempts`` cap from settings in code.

Behavior is selected by config flags (``interrupt``, ``terminal``), never by
hardcoded node ids — so renaming a node in the YAML changes nothing here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from langgraph.types import interrupt

from . import little_coder
from .config import NodeConfig, WorkflowConfig
from .llm import LLM, extract_json_block
from .state import PlannerState

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


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def gather_directory(workdir: str, *, max_entries: int = 200, readme_chars: int = 2000) -> str:
    """Read-only snapshot of the working directory (tree + README head)."""
    lines: list[str] = [f"Working directory: {workdir}"]
    count = 0
    for base, dirs, files in os.walk(workdir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        rel = os.path.relpath(base, workdir)
        prefix = "" if rel == "." else rel + "/"
        for f in sorted(files):
            lines.append(f"  {prefix}{f}")
            count += 1
            if count >= max_entries:
                lines.append("  ... (truncated)")
                break
        if count >= max_entries:
            break
    for name in ("README.md", "README.rst", "README.txt"):
        p = os.path.join(workdir, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                lines.append(f"\n--- {name} (first {readme_chars} chars) ---")
                lines.append(fh.read(readme_chars))
            break
    return "\n".join(lines)


def _system(node: NodeConfig, config: WorkflowConfig) -> str:
    return f"{config.system_prompt}\n\n---\n\n# Current phase: {node.id}\n\n{node.instructions}"


def _section(label: str, value: Any) -> str:
    return f"## {label}\n{value}\n" if value else ""


def _strip_last_json_fence(text: str) -> str:
    """Return the prose before the trailing ```json contract block."""
    marker = "```json"
    idx = text.rfind(marker)
    return text[:idx].rstrip() if idx != -1 else text.strip()


def _digest(state: PlannerState, parts: list[str]) -> str:
    """Assemble a user message from the named state fields that are present."""
    labels = {
        "request": "Original request",
        "context": "Working-directory snapshot (read-only)",
        "intent": "Resolved intent",
        "clarifications": "User answers to clarifying questions",
        "plan": "Approved plan",
        "component": "Current component to build",
        "diagnosis": "Distilled fix diagnosis (corrected behavior required)",
        "last_run_output": "little-coder output",
        "last_test_output": "Test output the orchestrator captured",
    }
    out: list[str] = []
    for key in parts:
        if key == "component":
            comps = state.get("components") or []
            i = state.get("current_index", 0)
            if 0 <= i < len(comps):
                c = comps[i]
                out.append(_section(labels[key], f"{c.get('name','?')}: {c.get('summary','')}"))
            continue
        out.append(_section(labels.get(key, key), state.get(key)))
    return "\n".join(s for s in out if s).strip()


# --------------------------------------------------------------------------- #
# agent node (intent / planning / report)
# --------------------------------------------------------------------------- #
def make_agent_node(node: NodeConfig, deps: NodeDeps):
    system = _system(node, deps.config)

    def _intent(state: PlannerState) -> dict:
        workdir = state.get("workdir", ".")
        context = state.get("context") or deps.gather(workdir)
        user = _digest({**state, "context": context}, ["request", "context"])
        data = extract_json_block(deps.llm.complete(system, user))
        questions = data.get("questions") or []
        clarifications: list[dict] = []
        if questions:
            # LangGraph interrupt: graph pauses, the runner asks the user, then
            # resumes — this same node re-runs from the top with the answers
            # returned here. (Re-running the read-only gather is harmless.)
            answers = interrupt({"type": "clarification", "questions": questions})
            clarifications = _normalize_answers(answers, questions)
            user2 = user + "\n\n" + _section("User answers", _format_answers(clarifications))
            data = extract_json_block(deps.llm.complete(system, user2))
        intent = data.get("intent") or "(intent could not be parsed; see request)"
        return {
            "context": context,
            "clarifications": clarifications,
            "intent": intent,
            "log": [f"[intent] resolved; {len(clarifications)} clarification(s)"],
        }

    def _planning(state: PlannerState) -> dict:
        user = _digest(state, ["request", "intent", "context"])
        raw = deps.llm.complete(system, user)
        data = extract_json_block(raw)
        plan = _strip_last_json_fence(raw)
        components = data.get("components") or []
        decision = interrupt({"type": "approval", "plan": plan, "components": components})
        if _is_revision(decision):
            user2 = user + "\n\n" + _section("User feedback on the plan", decision) + \
                "\nRevise the plan accordingly."
            raw = deps.llm.complete(system, user2)
            data = extract_json_block(raw)
            plan = _strip_last_json_fence(raw)
            components = data.get("components") or components
        return {
            "plan": plan,
            "artifact_type": data.get("artifact_type", ""),
            "components": components,
            "current_index": 0,
            "fix_attempts": 0,
            "log": [f"[planning] approved; {len(components)} component(s) queued"],
        }

    def _report(state: PlannerState) -> dict:
        user = _digest(
            state,
            ["request", "intent", "plan", "last_test_output", "diagnosis"],
        )
        if state.get("escalated"):
            user += "\n\nNote: a fix loop hit the cap without passing. Surface this and ask how to proceed."
        report = deps.llm.complete(system, user)
        return {"report": report, "log": ["[report] final response composed"]}

    if node.interrupt == "clarification":
        return _intent
    if node.interrupt == "approval":
        return _planning
    return _report


# --------------------------------------------------------------------------- #
# delegate node
# --------------------------------------------------------------------------- #
def make_delegate_node(node: NodeConfig, deps: NodeDeps):
    system = _system(node, deps.config)
    model = deps.config.setting("worker_model", "qwen/qwen3.5-9B")
    provider = deps.config.setting("worker_provider", "lmstudio")

    def _node(state: PlannerState) -> dict:
        workdir = state.get("workdir", ".")
        is_fix = state.get("next_action") == "fix"
        parts = ["intent", "plan", "component"]
        if is_fix:
            parts.append("diagnosis")
        user = _digest(state, parts)
        if is_fix:
            user += "\n\nThis is a FIX re-delivery: re-deliver the whole component and its tests in one pass, folding in the corrected behavior above."

        prompt = (extract_json_block(deps.llm.complete(system, user)).get("prompt") or "").strip()
        try:
            command = little_coder.build_command(prompt, model=model, provider=provider)
        except little_coder.PromptValidationError as exc:
            # Engine never mangles the prompt itself — it hands the violation back
            # to the LLM to rewrite (one retry), then validates again.
            retry = user + f"\n\nThe previous prompt was rejected: {exc}. " \
                           "Rewrite it as a single line with no backticks, dollar signs, " \
                           "inner double-quotes, or backslashes."
            prompt = (extract_json_block(deps.llm.complete(system, retry)).get("prompt") or "").strip()
            command = little_coder.build_command(prompt, model=model, provider=provider)

        result = deps.run_command(command, workdir=workdir)
        comp = (state.get("components") or [{}])[state.get("current_index", 0)]
        tag = "fix" if is_fix else "build"
        return {
            "last_prompt": prompt,
            "last_command": command,
            "last_run_output": result.output,
            "log": [f"[delegate] {tag} {comp.get('name','?')} -> rc={result.returncode}"],
        }

    return _node


# --------------------------------------------------------------------------- #
# review node
# --------------------------------------------------------------------------- #
def make_review_node(node: NodeConfig, deps: NodeDeps):
    system = _system(node, deps.config)
    max_fix = int(deps.config.setting("max_fix_attempts", 2))

    def _node(state: PlannerState) -> dict:
        workdir = state.get("workdir", ".")
        test_res = deps.run_tests(workdir)
        passed = test_res.ok  # the engine owns the truth about pass/fail

        user = _digest(state, ["intent", "component", "last_run_output"])
        user += "\n\n" + _section("Test output (orchestrator-run)", test_res.output[-4000:])
        data = extract_json_block(deps.llm.complete(system, user))
        notes = data.get("notes", "")
        diagnosis = data.get("diagnosis", "") or notes

        i = state.get("current_index", 0)
        n = len(state.get("components") or [])
        attempts = state.get("fix_attempts", 0)
        update: dict = {
            "last_test_output": test_res.output,
            "last_passed": passed,
            "review_notes": notes,
        }
        if passed:
            if i + 1 < n:
                update.update(next_action="next", current_index=i + 1, fix_attempts=0, diagnosis="")
                update["log"] = [f"[review] component {i} passed; advancing to {i + 1}"]
            else:
                update.update(next_action="done")
                update["log"] = [f"[review] component {i} passed; queue complete"]
        else:
            if attempts < max_fix:
                update.update(next_action="fix", fix_attempts=attempts + 1, diagnosis=diagnosis)
                update["log"] = [f"[review] component {i} failed; fix attempt {attempts + 1}/{max_fix}"]
            else:
                update.update(next_action="escalate", escalated=True, diagnosis=diagnosis)
                update["log"] = [f"[review] component {i} still failing after {max_fix} fixes; escalating"]
        return update

    return _node


# --------------------------------------------------------------------------- #
# dispatch + interrupt-answer helpers
# --------------------------------------------------------------------------- #
NODE_BUILDERS = {
    "agent": make_agent_node,
    "delegate": make_delegate_node,
    "review": make_review_node,
}


def build_node(node: NodeConfig, deps: NodeDeps):
    try:
        return NODE_BUILDERS[node.type](node, deps)
    except KeyError:
        raise KeyError(f"unknown node type {node.type!r}; known: {sorted(NODE_BUILDERS)}")


def _normalize_answers(answers: Any, questions: list[dict]) -> list[dict]:
    """Accept a few resume shapes and normalize to [{question, answer}]."""
    if isinstance(answers, dict):
        return [{"question": k, "answer": v} for k, v in answers.items()]
    if isinstance(answers, list):
        out = []
        for q, a in zip(questions, answers):
            out.append({"question": q.get("question", ""), "answer": a})
        return out
    return [{"question": q.get("question", ""), "answer": answers} for q in questions[:1]]


def _format_answers(clarifications: list[dict]) -> str:
    return "\n".join(f"- {c['question']}: {c['answer']}" for c in clarifications)


def _is_revision(decision: Any) -> bool:
    """A resume value asking for changes (anything that isn't a plain approval)."""
    if not isinstance(decision, str):
        return False
    return decision.strip().lower() not in {"", "approve", "approved", "yes", "y", "ok", "lgtm"}
