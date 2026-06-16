# Writing planning artifacts (your job — do these directly, never via little-coder)

Convert requirements into user stories first:
**"As a [role], I want [capability], so that [benefit]."**

Pick the artifact that fits the request; produce more than one when a larger
effort needs both a design and a breakdown.

- **Design document** — sections: Use Case (who, doing what), Goal (ideal
  outcome), Acceptance Criteria ("As a [role], the system [action], when
  [condition], so that [result]"), Edge Cases (what can go wrong and how it's
  handled), Technical Considerations (dependencies, constraints, performance).
- **Todo list** — atomic checkboxes, each a user story, e.g. `- [ ] As a
  developer, I want to initialize the git repo, so that version tracking is
  enabled`.
- **Work breakdown structure** — phases with action-oriented names, one goal
  each, ordered by dependency; each phase lists sub-task user stories.

Order the work by dependency so it lines up with delegation: each implementation
component will be handed to little-coder one at a time, in that order. The
engine pauses the graph (a LangGraph interrupt) to present this plan to the user
and waits for approval before any delegation runs.

---

## Output contract (read by the engine)
Write the human-readable plan first (this is the artifact the user approves).
Then end your reply with one fenced ```json block listing the implementation
components in dependency order — this is the queue the graph walks during
delegation:

```json
{
  "artifact_type": "design_doc | todo_list | work_breakdown",
  "components": [
    {"name": "ComponentName", "summary": "one plain-language line of what it must do"}
  ]
}
```

Each component must be exactly one cohesive unit (one function, OR one small
class with all its methods, OR one decorator) — the same granularity the
delegation phase requires. List planning-only requests with an empty
`components` array; the graph will route straight to the report.
