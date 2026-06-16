# lead-planner on LangGraph

This directory replaces **LLM-managed traversal** with a **LangGraph DAG**. In
the v3 spine the model itself decided when intent was clear, when to loop from
delegate to review, when to retry a failing component, when to stop, and when to
report. That control flow now lives in a `StateGraph`: the model only does the
work *inside* each phase, and the graph decides what runs next.

Nothing about the workflow is hardcoded in Python. The shape of the DAG lives in
[`workflow.yaml`](workflow.yaml) and the per-phase instructions live in
[`phases/`](phases/). Edit those files to change how the agent behaves — the
engine in [`lead_planner_graph/`](lead_planner_graph/) is generic and reads them
at runtime.

## The graph

```
        START
          │
        intent ──(interrupt: clarifying questions)
          │
       planning ──(interrupt: plan approval)
          │
   route_after_planning ── no components ─────────────┐
          │ has components                            │
          ▼                                           │
       delegate ◄───────────────────┐                 │
          │                         │                 │
        review                      │                 │
          │                         │                 │
   route_after_review               │                 │
     ├─ next  → delegate (next component)              │
     ├─ fix   → delegate (re-deliver, capped) ─────────┘
     ├─ done  → report                                 │
     └─ escalate → report ◄─────────────────────────────
          │
        report → END
```

- **Phases are nodes.** `intent`, `planning`, `delegate`, `review`, `report`.
- **Traversal is edges + routers.** Plain edges for the linear hops; two named
  routers (`route_after_planning`, `route_after_review`) for the branches.
- **The fix loop is a real cycle** delegate → review → delegate, **bounded in
  code** by `settings.max_fix_attempts`. The model no longer counts attempts.
- **Human-in-the-loop is built in.** The two pause points (clarifying questions,
  plan approval) are LangGraph `interrupt()` calls; a checkpointer persists state
  while the graph waits, and `Command(resume=...)` continues it.

## What lives where

| File | Role |
|------|------|
| `langgraph.json` | Manifest `langgraph dev` reads; points at the graph entrypoint. |
| `lead_planner_graph/app.py` | The entrypoint Studio loads — builds the uncompiled graph from env + config. |
| `pyproject.toml` / `.env.example` | Packaging (incl. the `[dev]` extra) and the LM Studio env settings. |
| `workflow-graph.md` | The rendered Mermaid DAG (regenerable). |
| `workflow.yaml` | The DAG: nodes, edges, routers, interrupts, and tunable `settings`. **Edit this to reshape the workflow.** |
| `phases/system.md` | Identity + routing rule + invariants, prepended to every node. |
| `phases/*.md` | One instruction file per phase (the former skills), each ending with a small JSON output contract the engine parses. **Edit these to change phase behavior.** |
| `lead_planner_graph/config.py` | Loads and validates the YAML + phase files. |
| `lead_planner_graph/state.py` | The typed `PlannerState` threaded through the graph. |
| `lead_planner_graph/llm.py` | Pluggable `LLM` Protocol + `LMStudioAdapter`. |
| `lead_planner_graph/little_coder.py` | Builds/validates/runs the little-coder command; runs tests. The shell-safety checklist is enforced here. |
| `lead_planner_graph/nodes.py` | The three node behaviors: `agent`, `delegate`, `review`. |
| `lead_planner_graph/routers.py` | The named branch functions. |
| `lead_planner_graph/builder.py` | Compiles the `StateGraph` from the config. |
| `lead_planner_graph/run.py` | CLI runner that services interrupts from stdin. |
| `lead_planner_graph/fake_llm.py` | Deterministic LLM for tests / `--demo`. |
| `tests/test_smoke.py` | End-to-end tests (no servers needed). |

## Model-agnostic by design

The engine talks only to the `LLM` Protocol (`complete(system, user) -> str`).
`LMStudioAdapter` ships for the local LM Studio server, and `FakeLLM` satisfies
the same contract for tests. Point the orchestrator at any model by writing a
~15-line adapter; the worker model little-coder drives is set in
`workflow.yaml` (`settings.worker_model` / `worker_provider`).

## The dev interface (recommended — replaces the OpenCode TUI)

The clean dev experience is **LangGraph Studio via `langgraph dev`** — a visual
graph debugger that runs locally and offline against your LM Studio. No cloud
account is needed for local dev.

```bash
pip install -e ".[dev]"     # engine + langgraph-cli[inmem] + pytest
cp .env.example .env        # point at your LM Studio server / model (optional)
langgraph dev               # starts the local server and opens Studio in the browser
```

`langgraph.json` is the manifest; it loads `lead_planner_graph/app.py:graph`
(the uncompiled `StateGraph`, so the dev server owns persistence). In Studio you
get:

- the flowchart above as a live, clickable graph;
- step-through execution with the full `PlannerState` visible (and editable) at
  every node;
- **the two interrupts handled in the UI** — answer clarifying questions and
  approve/revise the plan in a panel instead of at a prompt;
- time-travel: fork from any past checkpoint and re-run.

Hot reload is on, so editing `workflow.yaml` or a `phases/*.md` file updates the
running graph.

### Troubleshooting `langgraph dev`

**`AttributeError: module 'langgraph_api.config' has no attribute 'LSD_PROM_METRICS_ENABLED'`** (or a similar missing-attribute crash during server startup). The dev server is two rolling `.dev` packages — `langgraph-api` and `langgraph-runtime-inmem` — and you've landed a `runtime-inmem` newer than the `langgraph-api` beside it. Realign them:

```bash
pip install -U "langgraph-cli[inmem]" langgraph-api langgraph-runtime-inmem
# still crashing? the runtime is ahead of the api — pick one:
pip install -U --pre langgraph-api                 # bring the api forward
pip install --pre "langgraph-runtime-inmem<0.31"   # or hold the runtime back
```

**Root cause is often Python 3.14.** These platform server packages don't reliably ship stable wheels for 3.14 yet, so pip falls back to mismatched pre-releases. Use a venv on 3.12/3.13 for the dev server:

```bash
python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

The core engine (`langgraph` 1.2.5) and the headless CLI runner are fine on 3.14 — only the visual dev server is sensitive. Confirm the graph itself with `python -m lead_planner_graph.run --demo`.

## Run it headless (CLI / CI)

```bash
pip install -r requirements.txt

# Real run (needs LM Studio serving the orchestrator model + little-coder on PATH):
python -m lead_planner_graph.run --request "Build a thread-safe rate limiter" --workdir /path/to/project

# Offline demo (FakeLLM, no servers) — exercises interrupts + the fix loop:
python -m lead_planner_graph.run --demo

# Tests:
python -m pytest tests/ -q
```

When run headless the runner prints the clarifying questions or the plan and
reads your answer from stdin, then resumes exactly where it left off.

## How a phase talks to the engine

Each `phases/*.md` ends with a JSON output contract. A phase does its reasoning
in prose, then emits one fenced ```json block the node parses:

- **intent** → `{ "intent": "...", "questions": [...] }` — non-empty `questions`
  triggers the clarification interrupt.
- **planning** → `{ "artifact_type": "...", "components": [...] }` — the
  components become the delegation queue; the prose above is the approved plan.
- **delegate** → `{ "prompt": "..." }` — the engine validates it against the
  shell-safety rules and wraps it in the full command.
- **review** → `{ "passed": bool, "notes": "...", "diagnosis": "..." }` — the
  engine trusts the *actual* pytest result for pass/fail and uses `diagnosis`
  for a capped fix re-delivery.

Want a different contract or a new phase? Add a `phases/*.md` file and a node
entry in `workflow.yaml`. Only a genuinely new *kind* of work needs new Python
(a node type in `nodes.py` or a router in `routers.py`).
