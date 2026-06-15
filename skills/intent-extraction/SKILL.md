---
name: intent-extraction
description: Use at the very start of a request, before planning, to work out what the user actually wants. Covers gathering context by exploring the working directory read-only, then asking the user clarifying questions through the question tool for ambiguity that exploration could not resolve. Load this whenever a request is new, vague, or could be read more than one way.
---

# Intent extraction: gather first, then ask

Before you plan anything, extract what the user actually wants. A request is rarely complete on its face, so resolve it in two ordered phases — **investigate on your own first, then ask the user only about what you genuinely cannot determine.** Skipping straight to a plan on a vague request is how the whole effort goes the wrong direction.

## Phase 1 — Gather (answer your own questions before troubling the user)
Explore the working directory to build context and settle as many of your open questions as you can on your own. This is **read-only inspection** — listing the tree, reading code, tests, configs, docs, and project metadata with the **bash** tool (e.g. `ls`, `find`, `cat`, `grep`). Reading files to understand them is not implementation; *editing* them would be a routing violation, so never modify anything here. Use the pass to learn things like:
- What kind of project this is — language, layout, dependencies, conventions (read the README, manifests, and config).
- What already exists that bears on the request — relevant modules, existing tests, naming and structure to match.
- The current state of the thing the user mentioned — already present, partially built, or absent.

Every question you answer from the directory is one you don't have to ask the user.

## Phase 2 — Ask (only the genuine ambiguity that gathering left behind)
After gathering you will often still have gaps the directory cannot close — decisions only the user can make: scope, which target, preferences, tradeoffs, intended behavior. **Do not guess these.** Filling a real gap with a plausible-sounding assumption is the exact failure to avoid: a single wrong assumption propagates into the plan and every component you delegate. When a gap genuinely affects what gets built, ask.

Ask through the **question** tool — not as free-form prose in your reply. Each question carries a short header, the question text, and a list of options the user can choose from (they can also type their own answer), and you may pose several at once. Keep them:
- **Material** — ask only what actually changes the plan or the implementation. Never ask what you could have looked up or reasonably inferred in Phase 1.
- **Concrete** — offer real options grounded in what you found while gathering, so the user is selecting, not composing from scratch.
- **Batched and few** — pose the genuinely necessary questions together and resolve ambiguity in as few rounds as possible, rather than drip-feeding one at a time.

If the request is already unambiguous once you have gathered, skip Phase 2 and go straight to planning. The goal is a correct plan, not a questionnaire — gather to shrink the questions, ask to kill the assumptions.

When intent is clear, move to the **planning-artifacts** skill.
