"""The ``review`` node type — run the component's tests, let the LLM diagnose,
then record the routing decision (next / fix / done / escalate), enforcing the
``max_fix_attempts`` cap from settings in code."""

from __future__ import annotations

from ..config import NodeConfig
from ..llm import extract_json_block
from ..state import PlannerState
from .framework import NodeDeps, node_type
from .framework.toolkit import _digest, _section, _system


@node_type("review")
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
        if not passed and not diagnosis.strip():
            # Never hand the delegate an empty diagnosis — it would have nothing to
            # act on. The delegate also gets the raw failing test output as a backstop.
            diagnosis = (
                "Tests failed; inspect the attached failing test output and correct "
                "whichever side (implementation or test) is wrong."
            )

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
