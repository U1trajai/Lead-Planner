"""The ``agent`` node type — an LLM reasoning step.

Used by three phases, selected by the node's ``interrupt``/``terminal`` flags:
intent (gathers a read-only dir snapshot, then asks clarifying questions via a
LangGraph interrupt), planning (produces the artifact + component queue, then
interrupts for approval), and report (terminal prose).
"""

from __future__ import annotations

from langgraph.types import interrupt

from ..config import NodeConfig
from ..llm import extract_json_block
from ..state import PlannerState
from .framework import NodeDeps, node_type
from .framework.toolkit import (
    _digest,
    _format_answers,
    _is_revision,
    _normalize_answers,
    _section,
    _strip_last_json_fence,
    _system,
)


@node_type("agent")
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
