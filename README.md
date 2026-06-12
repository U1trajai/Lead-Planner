# Lead-Planner

System-prompt definitions for **lead-planner**, a primary planning-and-orchestration agent. It reads a request, breaks it into tasks, writes the planning artifacts itself (user stories, design docs, todos, work breakdowns), and delegates **all implementation** to **little-coder** — a local coding model invoked as a CLI through `bash` (LM Studio, model `qwen/qwen3.5-9B`). The planner thinks and coordinates; little-coder writes the code.

This repo holds three iterations of that prompt. Each one fixed real failures seen in use. Use **`lead-planner-v2-COMPACT.md`** in production; the other two are kept for reference and history.

## Getting set up
 
Running any version of this agent needs three pieces working together:
 
1. **[LM Studio](https://lmstudio.ai/)** — runs the local model that powers little-coder. Install it, download a small model (this prompt targets `qwen/qwen3.5-9B`), and start its local server so little-coder can reach it.
2. **[OpenCode](https://opencode.ai/)** — the terminal AI-agent harness that runs `lead-planner` as a primary agent. These `.md` files use OpenCode's agent format (the `mode: primary`, `temperature`, and `description` frontmatter). Install it, then add the prompt as an agent.
3. **[little-coder](https://github.com/itayinbarr/little-coder)** — the CLI the planner delegates all implementation to. It's a coding agent tuned for small local models, with a built-in LM Studio provider. Follow the install steps in its README, then confirm a call like the one below runs against your LM Studio server.

With all three in place, point OpenCode at `lead-planner-v2-COMPACT.md` and start planning.

## Versions at a glance

| File | Lines | Role |
|------|------:|------|
| `lead-planner.md` | 266 | v1 — original baseline |
| `lead-planner-v2.md` | 425 | v2 — fully hardened, all fixes layered in |
| `lead-planner-v2-COMPACT.md` | 95 | v2 consolidated — same behavior, de-duplicated **(recommended)** |

## v1 — `lead-planner.md` (original baseline)

Establishes the core concept: a planning agent that delegates implementation to little-coder via `bash` and writes planning artifacts directly.

Limitations that later versions fixed:

- **Malformed frontmatter** — the "Your Role" section was wedged inside the YAML block, ahead of `name`/`description`/`mode`/`temperature`, so the agent config could fail to parse or be silently dropped.
- **Redundant and contradictory** — the "never delegate planning" rule appeared roughly six times, and the emphasis skewed so hard toward "don't delegate / do it yourself" that the agent could stop delegating implementation altogether.
- **No delegation discipline** — nothing constrained prompt scope (prompts could balloon into whole modules), no "requirements vs. code" rule, no shell-safety rules for the command, and no distinction between a malformed-command error and a little-coder failure.

## v2 — `lead-planner-v2.md` (fully hardened)

Same overall structure as v1, with every behavioral fix found in testing added as explicit rules. Improvements over v1:

- **Valid frontmatter** — YAML block fixed; the role section moved into the document body.
- **Affirmative routing rule** — planning → the agent, implementation → little-coder, stated as *equally binding*, so the agent neither refuses to delegate nor takes the work over itself.
- **Component-level scoping** — one cohesive component per prompt (a single function, a small class *with all its methods*, or a decorator). A class is one unit and is never split method-by-method, and the agent must not distort the user's design (e.g. turn a requested class into loose functions) just to shrink a prompt.
- **Requirements, not code** — prompts describe what to build in plain words; no source code, signatures, skeletons, docstrings, pseudo-code, or prescribed libraries/data structures. little-coder makes the implementation choices.
- **Shell-safe commands** — the command must be a single physical line (no `\` continuations, which caused `command not found: -p`), the prompt must contain no backticks/`$`/inner quotes/backslashes (backticks caused `command not found: RateLimiter`), and `-p --no-session` must always be present.
- **Editing existing code is implementation** — moving tests between files, splitting, refactoring, and renaming all get delegated; the agent never opens a file to edit code itself.
- **Source-aware error handling** — distinguishes a malformed-command shell error (fix the command and re-run, never drop a flag) from a little-coder failure (retry/clarify), and forbids taking over implementation on any error.

Trade-off: thorough but long and repetitive, with several overlapping sections that could compete with one another.

## v2-COMPACT — `lead-planner-v2-COMPACT.md` (consolidated, recommended)

Same behavior as v2, restructured so the rules are easier to follow — and easier for a small local model to obey reliably. Improvements over v2:

- **~95 lines, down from 425**, with none of the rules lost.
- **One routing rule + one six-point pre-send checklist** serve as the single source of truth, replacing roughly five overlapping sections. Before any command the agent checks: one component; requirements not code; tests scoped to the component; one line, no backslashes; no shell-special characters; flags present.
- **Repetition removed** — the "never delegate planning" warnings collapse into a single statement.
- **Contradictions removed** — earlier versions had rules that quietly disagreed (e.g. "one method per prompt" vs. "a class is one component," "include the signature" vs. "no code"), which made the agent reason *against* its own instructions. Those seams are gone.
- **Quick-reference block** at the end restates the checklist compactly.

## Lessons Learned

- **Agent file size matters** — Compact instruction files give models too much room to drift. More detailed files provide better anchoring; optimal size depends on the model.

- **Multi-model review improves results** — Having separate models independently tackle a problem and combining their outputs surfaces blind spots a single model would miss.

- **Temperature controls determinism** — Lower temperatures produce more consistent, predictable outputs. Use higher temperatures only when exploration is the goal.

- **Less context can be better** — Flooding a model with context can hurt focus and reliability. Limiting the context window often makes smaller models behave more predictably.

- **Ambiguity gets exploited** — Models will find and use any gap in instructions. Clear, explicit language in agent files is not optional — it is the foundation of reliable behavior.
