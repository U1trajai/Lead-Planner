"""Node-authoring toolkit — the shared helpers every node builds on.

This is scaffolding, not a node: directory gathering, per-node system-prompt
assembly, the state-to-user-message digest, and the small helpers that normalize
interrupt resume values. Node modules import these; nothing here imports a node.
"""

from __future__ import annotations

import os
from typing import Any

from ...config import NodeConfig, WorkflowConfig
from ...state import PlannerState


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
