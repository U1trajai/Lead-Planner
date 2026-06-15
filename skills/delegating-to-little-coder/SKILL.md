---
name: delegating-to-little-coder
description: Use when you are about to hand an implementation task to little-coder — any creation or change to code or test files. Covers constructing the single-line CLI command and its required flags, the budget little-coder runs under, the six-point pre-send checklist, and how to split work bigger than one component. Load this every time before issuing a little-coder command.
---

# Delegating implementation to little-coder

little-coder is a CLI program you invoke through the **bash** tool — not a tool you call by name. Write the command as **one single physical line** (no backslash line-continuations):

```bash
PI_RETRY_PROVIDER_TIMEOUTMS=3600000 little-coder --provider lmstudio --model qwen/qwen3.5-9B "<prompt>" -p --no-session
```

- `--provider lmstudio` — local LM Studio provider.
- `--model qwen/qwen3.5-9B` — the model.
- `"<prompt>"` — your single-line, requirements-only task description.
- `-p` and `--no-session` — **required; never omit either.** Each invocation is stateless and has no memory of prior runs.

**Context budget — design every prompt around it.** little-coder sees only the prompt you send: roughly 30k of context, with no memory of any earlier run. It cannot see test output, prior reasoning, or files it wrote before. Keep every prompt lean — requirements only, one component, never pasted code, logs, or tracebacks. The smaller and more focused the prompt, the more reliably it succeeds and the easier any failure is to diagnose. Diagnosing failures is YOUR job, because you have the context budget and it does not.

## Pre-send checklist — verify ALL SIX before running any little-coder command
1. **One component.** The prompt implements exactly one cohesive component: one function, OR one small class with all its methods, OR one decorator — plus that component's own tests. A class is ONE component; never split it method-by-method. If the work is more than one component, delegate them one at a time in dependency order, reviewing each result before the next. Never distort the user's design (e.g. turning a requested class into loose functions or global state) just to shrink a prompt.
2. **Requirements, not code.** Describe in plain words what the component is named and what it should do, accept, return, and handle (its edge cases and errors). Never include source code, signatures, skeletons, docstrings, pseudo-code, or prescribed libraries / data structures / algorithms — little-coder makes those choices. State a specific library only if the user explicitly required it.
3. **Tests included, scoped to this component, and deterministic — written but not run.** Ask for unit tests covering this one component only, and tell little-coder to **write the tests but not run them** (running tests is the orchestrator's job, always). Require that they be deterministic and self-contained — no dependence on wall-clock timing, real sleeps, network, filesystem, or unseeded randomness — so a failure is reproducible and diagnosable rather than flaky. (Flaky, nondeterministic tests are the most common cause of failures the model can't discern.) Stating the test must not depend on real time or randomness is a property requirement, not a prescribed implementation, so it is allowed. If you want the tests in their own file, say so up front (this prevents needing a separate "move the tests" step later).
4. **One physical line, no backslashes.** The whole command and the prompt are on a single line. Replace any newlines in the prompt with sentences or semicolons. No `\` anywhere — a dropped continuation is what causes `command not found: -p`.
5. **No shell-special characters in the prompt.** No backticks (the shell would run the backticked word — e.g. `command not found: RateLimiter`), no `$`, no inner double-quotes, no backslashes. Refer to names as plain words (RateLimiter, rate_limit). Parentheses, commas, and apostrophes are fine inside the double-quoted prompt.
6. **Flags present.** The command ends with `-p --no-session`.

## Decomposing work bigger than one component
When a feature needs several components, you break it into an ordered list and delegate one per command, in dependency order, reviewing each before issuing the next. Deliver each component whole in one pass — because `--no-session` means you cannot reliably append to a file an earlier run created.

## Good example (one line, requirements only, no backticks)
```bash
PI_RETRY_PROVIDER_TIMEOUTMS=3600000 little-coder --provider lmstudio --model qwen/qwen3.5-9B "Implement a class named RateLimiter that allows at most a configured number of requests per user within a sliding time window, created with a request limit and a window length defaulting to 10 requests per 60 seconds. Its acquire method takes a user id, records a request, returns whether it is allowed, removes expired requests as it goes, and is safe to call from multiple threads. Raise an error if the limit or window is not positive. Let the implementer choose the data structures. Generate deterministic unit tests in a separate test file that control time through an injected or mockable clock rather than real sleeps, covering normal allowance, hitting the limit, expiry of old requests, and the error cases. Write only this class and its tests, and do not run the tests." -p --no-session
```
Correct because: one component (a class with all its methods), requirements only with no code or prescribed data structures, one line, no backticks, flags present, tests requested in a separate file, required to be deterministic, and explicitly written but not run.

## Over-scoped — split first, then delegate each
- "Build the user authentication system" / "Implement all the CRUD endpoints"
- "A RateLimiter class PLUS a rate_limit decorator PLUS a Redis backend PLUS a full test file PLUS a README" — this bundles several components and a doc. Split into one component per command (the class with its tests; the decorator with its tests; the README as its own documentation command), then delegate each in turn.

After a command returns, move to the **reviewing-and-fixing** skill before issuing the next one.
