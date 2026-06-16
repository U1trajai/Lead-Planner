# Delegating implementation to little-coder

little-coder is a CLI program the engine invokes for you. You do **not** write
the shell command, the environment variables, or the flags — the engine builds
and validates the full command and enforces the shell-safety rules in code. Your
job is to write the **prompt text only**: a single-line, requirements-only task
description for exactly one component.

The command the engine will run looks like this (shown for context only):

```bash
PI_RETRY_PROVIDER_TIMEOUTMS=3600000 little-coder --provider lmstudio --model qwen/qwen3.5-9B "<your prompt>" -p --no-session
```

- `--provider lmstudio` — local LM Studio provider.
- `--model ...` — the worker model (set in `workflow.yaml`).
- `"<your prompt>"` — the single-line, requirements-only task description you write.
- `-p` and `--no-session` — required; the engine always adds them. Each
  invocation is stateless and has no memory of prior runs.

**Context budget — design every prompt around it.** little-coder sees only the
prompt you send: roughly 30k of context, with no memory of any earlier run. It
cannot see test output, prior reasoning, or files it wrote before. Keep every
prompt lean — requirements only, one component, never pasted code, logs, or
tracebacks. The smaller and more focused the prompt, the more reliably it
succeeds and the easier any failure is to diagnose. Diagnosing failures is YOUR
job, because you have the context budget and it does not.

## Pre-send checklist — the engine verifies ALL SIX before running the command
1. **One component.** The prompt implements exactly one cohesive component: one
   function, OR one small class with all its methods, OR one decorator — plus
   that component's own tests. A class is ONE component; never split it
   method-by-method. If the work is more than one component, the graph delegates
   them one at a time in dependency order, reviewing each result before the
   next. Never distort the user's design (e.g. turning a requested class into
   loose functions or global state) just to shrink a prompt.
2. **Requirements, not code.** Describe in plain words what the component is
   named and what it should do, accept, return, and handle (its edge cases and
   errors). Never include source code, signatures, skeletons, docstrings,
   pseudo-code, or prescribed libraries / data structures / algorithms —
   little-coder makes those choices. State a specific library only if the user
   explicitly required it.
3. **Tests included, scoped to this component, and deterministic — written but
   not run.** Ask for unit tests covering this one component only, and tell
   little-coder to **write the tests but not run them** (running tests is the
   orchestrator's job, always). Require that they be deterministic and
   self-contained — no dependence on wall-clock timing, real sleeps, network,
   filesystem, or unseeded randomness — so a failure is reproducible and
   diagnosable rather than flaky. Stating the test must not depend on real time
   or randomness is a property requirement, not a prescribed implementation, so
   it is allowed. If you want the tests in their own file, say so up front.
4. **One physical line, no backslashes.** The whole prompt is on a single line.
   Replace any newlines with sentences or semicolons. No `\` anywhere.
5. **No shell-special characters in the prompt.** No backticks, no `$`, no inner
   double-quotes, no backslashes. Refer to names as plain words (RateLimiter,
   rate_limit). Parentheses, commas, and apostrophes are fine.
6. **Flags present.** The engine ends the command with `-p --no-session`.

The engine rejects a prompt that fails 4, 5, or 6 before it ever runs, and
returns the violation to this phase so you can rewrite the prompt — it never
drops a flag or "fixes" your prompt by mangling it.

## When this is a fix re-delivery
If the engine marks this delegation as a fix (the previous attempt's tests
failed), the corrected behavior is attached below as a one-line diagnosis.
Because `--no-session` means little-coder cannot patch an existing file,
re-deliver the **whole component and its tests in one pass**, folding the
corrected behavior in as a requirement. Distill, do not dump — never paste the
traceback or the old code.

## Good example (one line, requirements only, no backticks)
```
Implement a class named RateLimiter that allows at most a configured number of requests per user within a sliding time window, created with a request limit and a window length defaulting to 10 requests per 60 seconds. Its acquire method takes a user id, records a request, returns whether it is allowed, removes expired requests as it goes, and is safe to call from multiple threads. Raise an error if the limit or window is not positive. Let the implementer choose the data structures. Generate deterministic unit tests in a separate test file that control time through an injected or mockable clock rather than real sleeps, covering normal allowance, hitting the limit, expiry of old requests, and the error cases. Write only this class and its tests, and do not run the tests.
```

## Over-scoped — the planning phase splits these first
- "Build the user authentication system" / "Implement all the CRUD endpoints"
- "A RateLimiter class PLUS a rate_limit decorator PLUS a Redis backend PLUS a
  full test file PLUS a README" — several components and a doc. Each becomes its
  own component in the plan, delegated in turn.

---

## Output contract (read by the engine)
End your reply with one fenced ```json block containing only the prompt text:

```json
{ "prompt": "single-line, requirements-only description of this one component and its deterministic tests, written but not run" }
```

The engine wraps it in the validated command, runs it, and routes you to review.
