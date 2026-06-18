"""Textual TUI front-end for the lead-planner LangGraph workflow.

This is a thin wrapper around the same graph driven by ``run.py`` — it does not
touch any graph or node code. It renders the conversation in a scrollable log,
reads input from a single-line box pinned to the bottom, and services the
graph's human-in-the-loop interrupts (clarification / approval) interactively.

Usage:
  python -m lead_planner_graph.tui            # talk to LM Studio
  python -m lead_planner_graph.tui --demo     # built-in FakeLLM, no servers
"""

from __future__ import annotations

import argparse
import json
import queue
import uuid
from pathlib import Path

from langgraph.types import Command
from rich.markdown import Markdown
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Header, Input, LoadingIndicator, RichLog

from .builder import build_graph
from .config import load_config
from .llm import LMStudioAdapter
from .run import DEFAULT_WORKFLOW

# Fallback model ids if neither the saved sidecar nor workflow.yaml has them.
_DEFAULT_ORCHESTRATOR = "openai/gpt-oss-20b"
_DEFAULT_WORKER = "qwen/qwen3.5-9B"
# Default OpenAI-compatible endpoint (LM Studio's local default). Configurable.
_DEFAULT_BASE_URL = "http://localhost:1234/v1"


def _models_file(workflow: str | Path) -> Path:
    """Sidecar that remembers the user's model choices, next to workflow.yaml."""
    return Path(workflow).resolve().parent / ".tui_models.json"


def _load_saved_models(workflow: str | Path) -> dict:
    """Return persisted model selections, or an empty dict if none/unreadable."""
    path = _models_file(workflow)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _save_settings(workflow: str | Path, orchestrator: str, worker: str, base_url: str) -> None:
    """Persist the current model/endpoint selections so they survive restarts."""
    path = _models_file(workflow)
    try:
        path.write_text(
            json.dumps(
                {
                    "orchestrator_model": orchestrator,
                    "worker_model": worker,
                    "base_url": base_url,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _fetch_lmstudio_models(base_url: str = _DEFAULT_BASE_URL) -> list[str]:
    """Ask the endpoint for its loaded models; return [] if it's unreachable."""
    try:
        import httpx

        resp = httpx.get(f"{base_url.rstrip('/')}/models", timeout=3.0)
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", []) if m.get("id")]
    except Exception:
        return []


class LeadPlannerTUI(App):
    """A chat-style terminal UI over the lead-planner graph."""

    CSS = """
    #settings {
        height: 3;
        margin: 0 1;
        align: left middle;
    }
    #settings Input {
        width: 1fr;
        margin: 0 1 0 0;
    }
    #conversation {
        height: 1fr;
        border: round $accent;
        padding: 0 1;
        margin: 0 1;
    }
    #loading {
        height: 1;
        margin: 0 1;
        display: none;
    }
    #loading.running {
        display: block;
    }
    #prompt {
        dock: bottom;
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", priority=True),
    ]

    def __init__(self, *, workflow=DEFAULT_WORKFLOW, workdir=".", demo=False):
        super().__init__()
        self._workflow = workflow
        self._workdir = workdir
        self._demo = demo

        self._app = None  # compiled graph, rebuilt at the start of each run
        self._llm = None  # the live orchestrator adapter (model is mutable on the fly)
        # Thread/session config is created once and reused across resumes so the
        # graph's checkpointer keeps the conversation on a single thread.
        self._thread = {"configurable": {"thread_id": uuid.uuid4().hex}}

        self._run_active = False  # a graph run (incl. its interrupts) is in flight
        self._awaiting = False  # worker is blocked waiting for user input
        self._input_q: "queue.Queue[str]" = queue.Queue()

        # Selections: workflow.yaml defaults, overridden by the saved sidecar.
        (
            self._orchestrator_model,
            self._worker_model,
            self._base_url,
        ) = self._initial_settings()

    def _initial_settings(self) -> tuple[str, str, str]:
        orch, worker = _DEFAULT_ORCHESTRATOR, _DEFAULT_WORKER
        try:
            cfg = load_config(self._workflow)
            orch = cfg.setting("orchestrator_model", orch)
            worker = cfg.setting("worker_model", worker)
        except Exception:
            pass
        saved = _load_saved_models(self._workflow)
        return (
            saved.get("orchestrator_model", orch),
            saved.get("worker_model", worker),
            saved.get("base_url", _DEFAULT_BASE_URL),
        )

    # ----- layout -------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container():
            with Horizontal(id="settings"):
                yield Input(
                    value=self._base_url,
                    placeholder="Endpoint URL",
                    id="endpoint_input",
                )
                yield Input(
                    value=self._orchestrator_model,
                    placeholder="Orchestrator model",
                    id="orch_input",
                )
                yield Input(
                    value=self._worker_model,
                    placeholder="Worker model",
                    id="worker_input",
                )
            yield RichLog(id="conversation", wrap=True, markup=True, highlight=True)
            yield LoadingIndicator(id="loading")
            yield Input(
                id="prompt",
                placeholder="Describe what to plan and build, then press Enter…",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Lead Planner"
        self._refresh_subtitle()
        log = self.query_one("#conversation", RichLog)
        log.write(
            Markdown(
                "### Lead Planner\n"
                "Type a request below to start. I'll ask clarifying questions and "
                "show a plan for your approval before building.\n\n"
                "Set the **endpoint URL** and the **orchestrator** / **worker** "
                "models in the boxes above (press Enter in a box to apply). Choices "
                "are saved and reused next time. The endpoint and orchestrator model "
                "take effect immediately, even mid-run; a new worker model applies to "
                "the next run. Models available at the endpoint are listed for "
                "reference.\n\n"
                "_Press Ctrl+Q to quit._"
            )
        )
        self.query_one("#prompt", Input).focus()
        if not self._demo:
            self._load_lmstudio_models()  # list available models from the live server

    def _refresh_subtitle(self) -> None:
        if self._demo:
            self.sub_title = "demo (FakeLLM)"
        else:
            self.sub_title = (
                f"{self._base_url}  •  orch: {self._orchestrator_model}"
                f"  •  worker: {self._worker_model}"
            )

    @work(thread=True, exclusive=False, group="model_fetch")
    def _load_lmstudio_models(self) -> None:
        """List models the endpoint reports, as a copyable reference for the boxes."""
        models = _fetch_lmstudio_models(self._base_url)
        if models:
            listing = "\n".join(f"- `{m}`" for m in models)
            self.call_from_thread(
                self._write_md,
                f"**Models available at `{self._base_url}`:**\n{listing}",
            )
        else:
            self.call_from_thread(
                self._write_md,
                f"_⚠️ Couldn't reach `{self._base_url}` to list models. You can still "
                "type any model id in the boxes; fix the endpoint and press Enter to retry._",
            )

    def _apply_orchestrator(self, model: str) -> None:
        model = model.strip()
        if not model or model == self._orchestrator_model:
            return
        self._orchestrator_model = model
        if self._llm is not None:  # live: affects the in-flight run's next LLM call
            self._llm.model = model
        self._save()
        self._refresh_subtitle()
        self._write_md(f"_🧠 Orchestrator model → `{model}` (applies now)._")

    def _apply_worker(self, model: str) -> None:
        model = model.strip()
        if not model or model == self._worker_model:
            return
        self._worker_model = model
        self._save()
        self._refresh_subtitle()
        self._write_md(f"_🔧 Worker model → `{model}` (applies on next run)._")

    def _save(self) -> None:
        _save_settings(
            self._workflow, self._orchestrator_model, self._worker_model, self._base_url
        )

    def _apply_endpoint(self, url: str) -> None:
        url = url.rstrip("/") or _DEFAULT_BASE_URL
        self.query_one("#endpoint_input", Input).value = url
        if url == self._base_url and not self._demo:
            self._load_lmstudio_models()  # same URL: just retry the fetch
            return
        self._base_url = url
        if self._llm is not None and not self._demo:  # live: affects the in-flight run
            self._llm.base_url = url
        self._save()
        self._refresh_subtitle()
        self._write_md(f"_🔌 Endpoint → `{url}` (applies now; refreshing models)._")
        if not self._demo:
            self._load_lmstudio_models()

    # ----- helpers (main thread) ---------------------------------------
    def _write_user(self, text: str) -> None:
        log = self.query_one("#conversation", RichLog)
        log.write(Text.assemble(("You: ", "bold cyan"), (text, "cyan")))

    def _write_md(self, text: str) -> None:
        self.query_one("#conversation", RichLog).write(Markdown(text))

    def _set_loading(self, on: bool) -> None:
        self.query_one("#loading", LoadingIndicator).set_class(on, "running")

    # ----- input handling ----------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "endpoint_input":
            self._apply_endpoint(event.value.strip())
            return
        if event.input.id == "orch_input":
            self._apply_orchestrator(event.value)
            return
        if event.input.id == "worker_input":
            self._apply_worker(event.value)
            return

        value = event.value.strip()
        event.input.value = ""
        if not value:
            return
        self._write_user(value)

        if self._awaiting:
            # The driver worker is blocked waiting for this answer.
            self._awaiting = False
            self._input_q.put(value)
        elif not self._run_active:
            # Fresh request — kick off a graph run.
            self._run_active = True
            self._drive(value)
        else:
            self._write_md("_⏳ Still working — hold on a moment._")

    # ----- the driver (background thread) ------------------------------
    def _prompt_user(self) -> str:
        """Block the worker until the user submits the next line of input."""
        self.call_from_thread(self._set_loading, False)
        self._awaiting = True
        value = self._input_q.get()
        self.call_from_thread(self._set_loading, True)
        return value

    def _render_clarification(self, payload: dict) -> dict:
        self.call_from_thread(
            self._write_md, "**🟡 Clarifying questions** — answer each below:"
        )
        answers = {}
        for q in payload.get("questions", []):
            question = q.get("question", "?")
            opts = q.get("options") or []
            opt_str = f"  \n_options: {', '.join(opts)}_" if opts else ""
            self.call_from_thread(self._write_md, f"**Q:** {question}{opt_str}")
            answers[question] = self._prompt_user()
        return answers

    def _render_approval(self, payload: dict) -> str:
        lines = ["**📋 Plan for approval**", "", payload.get("plan", "")]
        comps = payload.get("components", [])
        lines.append(f"\n**Components queued ({len(comps)}):**")
        for i, c in enumerate(comps):
            lines.append(f"{i + 1}. **{c.get('name', '?')}** — {c.get('summary', '')}")
        lines.append("\n_Type `approve` to proceed, or type revision feedback._")
        self.call_from_thread(self._write_md, "\n".join(lines))
        return self._prompt_user()

    def _service_interrupt(self, payload):
        if isinstance(payload, dict) and payload.get("type") == "clarification":
            return self._render_clarification(payload)
        if isinstance(payload, dict) and payload.get("type") == "approval":
            return self._render_approval(payload)
        self.call_from_thread(self._write_md, f"**Input required:** {payload}")
        return self._prompt_user()

    # ----- per-node status surfacing -----------------------------------
    @staticmethod
    def _fence(text: str, limit: int | None = None) -> str:
        text = text.strip()
        if limit and len(text) > limit:
            text = "…(truncated)…\n" + text[-limit:]
        return "```\n" + (text or "(empty)") + "\n```"

    def _format_status(self, node_id: str, update: dict) -> str | None:
        """Turn one node's state update into a status block, or None to skip.

        Delegate and review — the steps with the least visibility — get rich
        sections (the exact message handed to the worker, the command, and the
        test/diagnosis result). Every other node falls back to the one-line trace
        it already appends to ``state['log']``.
        """
        if node_id == "delegate":
            parts = ["**🔧 Delegate — message sent to the worker LLM:**", ""]
            parts.append(self._fence(update.get("last_prompt") or ""))
            command = (update.get("last_command") or "").strip()
            if command:
                parts.append(f"**Command:** `{command}`")
            out = (update.get("last_run_output") or "").strip()
            if out:
                parts.append("**Worker output (tail):**")
                parts.append(self._fence(out, limit=1200))
            return "\n".join(parts)

        if node_id == "review":
            passed = update.get("last_passed")
            status = "✅ tests passed" if passed else "❌ tests failed"
            action = update.get("next_action", "?")
            lines = [f"**🔎 Review** — {status} · next: `{action}`"]
            for ln in update.get("log") or []:  # carries the fix-attempt counter
                lines.append(f"_{ln}_")
            diagnosis = (update.get("diagnosis") or update.get("review_notes") or "").strip()
            if diagnosis:
                lines.append(f"**Diagnosis:** {diagnosis}")
            test_out = (update.get("last_test_output") or "").strip()
            if test_out:
                lines.append("**Test output (tail):**")
                lines.append(self._fence(test_out, limit=1200))
            return "\n".join(lines)

        # Everything else: just surface the node's own one-line trace.
        lines = update.get("log") or []
        return "  \n".join(f"_{ln}_" for ln in lines) or None

    def _run_segment(self, graph_input):
        """Stream the graph until it pauses or ends, surfacing each node update.

        Returns the interrupt payload if the segment paused for input, else None.
        """
        for chunk in self._app.stream(graph_input, self._thread, stream_mode="updates"):
            if "__interrupt__" in chunk:  # paused — hand the payload back to the loop
                intr = chunk["__interrupt__"][0]
                return getattr(intr, "value", intr)
            for node_id, update in chunk.items():
                status = self._format_status(node_id, update)
                if status:
                    self.call_from_thread(self._write_md, status)
        return None

    @work(thread=True, exclusive=True)
    def _drive(self, request: str) -> None:
        try:
            # Rebuild each run so the latest model selections take effect. The
            # worker model is read at build time (delegate node), and a fresh
            # orchestrator adapter is created from the current selection.
            config = load_config(self._workflow)
            config.settings["orchestrator_model"] = self._orchestrator_model
            config.settings["worker_model"] = self._worker_model
            if self._demo:
                from .llm import FakeLLM

                self._llm = FakeLLM()
            else:
                self._llm = LMStudioAdapter(
                    model=self._orchestrator_model, base_url=self._base_url
                )
            self._app = build_graph(config, self._llm)

            self.call_from_thread(self._set_loading, True)
            payload = self._run_segment({"request": request, "workdir": self._workdir})
            while payload is not None:
                answer = self._service_interrupt(payload)
                self.call_from_thread(self._set_loading, True)
                payload = self._run_segment(Command(resume=answer))

            final = self._app.get_state(self._thread).values
            report = final.get("report") or "_(no report produced)_"
            self.call_from_thread(self._write_md, "### ✅ Report\n\n" + report)
        except Exception as exc:  # surface failures in the log rather than crash
            self.call_from_thread(
                self._write_md, f"**⚠️ Error:** `{type(exc).__name__}: {exc}`"
            )
        finally:
            self.call_from_thread(self._set_loading, False)
            self._run_active = False
            self._awaiting = False
            self.call_from_thread(
                self._write_md, "_Done. Enter a new request to start again._"
            )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Textual TUI for the lead-planner workflow.")
    p.add_argument("--workdir", default=".", help="directory the run operates in")
    p.add_argument("--workflow", default=str(DEFAULT_WORKFLOW), help="path to workflow.yaml")
    p.add_argument("--demo", action="store_true", help="use the built-in FakeLLM (no servers)")
    args = p.parse_args(argv)

    LeadPlannerTUI(workflow=args.workflow, workdir=args.workdir, demo=args.demo).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
