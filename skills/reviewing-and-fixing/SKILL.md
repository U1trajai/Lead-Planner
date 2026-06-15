---
name: reviewing-and-fixing
description: Use right after a little-coder command returns, to verify and correct its output before moving on. Covers running the component's tests yourself, the mandatory review gate, the diagnose-then-re-delegate loop for failing tests, telling a malformed-command (shell) error apart from a little-coder error, and never taking over implementation on an error. Load this after every delegation.
---

# After little-coder runs

## Review gate (mandatory, one pass)
First, **run the component's tests yourself** with the bash tool — little-coder writes tests but never runs them, so executing and reading the output is yours exclusively (you have the context budget for it; little-coder does not — see Test failures below). Then review the generated artifacts for correctness, standards, efficiency, and fit to the requirements. List the concrete issues you find. If there is a meaningful improvement, send a new, targeted, single-component prompt to apply it, then review again. Stop when no meaningful improvement remains or the user accepts the result. Only then synthesize the final response.

## Test failures: you run, you diagnose, little-coder re-delivers
This is the single most common place a delegation gets stuck, so handle it deliberately. **Never hand a raw failing test back to little-coder to puzzle out.** It is stateless with ~30k of context; asked to "fix the failing test" it cannot see the run output or recover its earlier reasoning, so it thrashes and the user experience degrades. Instead:

1. **You run the tests** with bash and read the actual output yourself.
2. **You diagnose.** Decide whether the implementation or the test is wrong — you hold the requirements, little-coder is only guessing. Reduce the problem to a one-line statement of the correct behavior and which side must change.
3. **You re-delegate a fresh whole-component prompt.** Because `--no-session` means it cannot patch an existing file, the fix is a full re-delivery of the component and its tests in one pass, with the corrected behavior stated as a requirement. (Construct it per the **delegating-to-little-coder** skill.)
4. **Distill, do not dump.** Never paste a traceback, log, or full file into the prompt — that burns the 30k budget and reintroduces the very confusion you are fixing. Give only the essence: which test failed, the specific expected-vs-actual discrepancy, and the corrected behavior, in one or two plain sentences.
5. **Bound the loop.** Allow at most two fix attempts, each with a more specific diagnosis than the last. If it still fails, STOP — present your own analysis of the likely cause along with the failing output to the user, and ask how to proceed. Getting stuck silently in a retry loop is worse than asking.

## Errors — identify the source first, they need opposite responses
- **Shell / command-syntax error** (e.g. `command not found: -p`, `command not found: RateLimiter`, missing delimiter, unmatched quote): the COMMAND was malformed — almost always a multi-line command, a dropped flag, or a backtick / special character in the prompt. **Fix:** re-emit the whole command on one line, flags intact, with no special characters, and run it again. Never "fix" it by dropping a flag, and never switch to writing the code or files yourself.
- **little-coder error** (it ran but reported failure, produced wrong or incomplete output, or timed out): analyze what went wrong, then act per the path. For failing tests, follow **Test failures** above — you diagnose, then re-delegate a distilled single-component fix, capped at two attempts. For other failures, retry with adjusted requirements, or ask the user. On timeout, keep any partial output and resume the remaining components.

## Never take over implementation on an error
You stay the orchestrator in every error path. If little-coder returned file *contents* instead of writing the files, do not write them yourself — send a follow-up command instructing little-coder to write the files. If a step seems to require you to author, edit, or move code, that is a signal to re-delegate, not to take over.
