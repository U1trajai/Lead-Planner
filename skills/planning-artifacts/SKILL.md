---
name: planning-artifacts
description: Use when intent is clear and you need to produce planning output before any delegation — user stories, a design document with acceptance criteria, a todo list, or a work breakdown structure. These artifacts are always the orchestrator's own work and are never delegated to little-coder. Load this when turning an understood request into a written plan.
---

# Writing planning artifacts (your job — do these directly, never via little-coder)

Convert requirements into user stories first: **"As a [role], I want [capability], so that [benefit]."**

Pick the artifact that fits the request; produce more than one when a larger effort needs both a design and a breakdown.

- **Design document** — sections: Use Case (who, doing what), Goal (ideal outcome), Acceptance Criteria ("As a [role], the system [action], when [condition], so that [result]"), Edge Cases (what can go wrong and how it's handled), Technical Considerations (dependencies, constraints, performance).
- **Todo list** — atomic checkboxes, each a user story, e.g. `- [ ] As a developer, I want to initialize the git repo, so that version tracking is enabled`.
- **Work breakdown structure** — phases with action-oriented names, one goal each, ordered by dependency; each phase lists sub-task user stories.

Order the work by dependency so it lines up with delegation: each implementation component will be handed to little-coder one at a time, in that order. Present the finished plan to the user and wait for approval before executing.

When approved and ready to implement a component, move to the **delegating-to-little-coder** skill.
