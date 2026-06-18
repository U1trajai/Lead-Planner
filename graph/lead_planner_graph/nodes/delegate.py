"""The ``delegate`` node type — turn the current component into a validated
little-coder command and run it."""

from __future__ import annotations

from ..config import NodeConfig
from ..llm import extract_json_block
from ..state import PlannerState
from .framework import NodeDeps, little_coder, node_type
from .framework.toolkit import _digest, _section, _system


@node_type("delegate")
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
            user += (
                "\n\nThis is a TARGETED FIX, not a re-delivery. The component's files are "
                "already on disk from the previous attempt and little-coder can read and edit "
                "them. Write a prompt that tells little-coder to open the existing file(s) below "
                "and apply ONLY the corrected behavior, leaving the rest of the component and any "
                "already-passing tests unchanged. Do not regenerate or re-deliver the whole "
                "component, and do not run the tests. You are non-interactive: never ask the user "
                "questions — name the file and change yourself from the failure below and output "
                "the prompt."
            )
            # The orchestrator has the context budget; give it the real failure so
            # it can name the file and the change even when the diagnosis is thin.
            user += "\n\n" + _section("Files currently on disk", deps.gather(workdir))
            test_out = (state.get("last_test_output") or "")[-3000:]
            user += "\n" + _section("Failing test output (orchestrator-run)", test_out)

        prompt = (extract_json_block(deps.llm.complete(system, user)).get("prompt") or "").strip()
        try:
            command = little_coder.build_command(prompt, model=model, provider=provider)
        except little_coder.PromptValidationError as exc:
            # Engine never mangles the prompt itself — it hands the violation back
            # to the LLM to rewrite (one retry), then validates again.
            retry = user + f"\n\nThe previous reply was rejected: {exc}. You are " \
                           "non-interactive — do not ask the user anything and do not explain. " \
                           "Output the JSON contract with a non-empty single-line prompt, with no " \
                           "backticks, dollar signs, inner double-quotes, or backslashes."
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
