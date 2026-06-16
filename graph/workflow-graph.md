# lead-planner workflow graph

Rendered from `workflow.yaml` (`app.get_graph().draw_mermaid()`). Solid arrows
are plain edges; dotted arrows are router branches. Regenerate with:

```bash
python -c "from lead_planner_graph.config import load_config; from lead_planner_graph.builder import build_graph; from lead_planner_graph.fake_llm import FakeLLM; print(build_graph(load_config('workflow.yaml'), FakeLLM()).get_graph().draw_mermaid())"
```

```mermaid
graph TD;
	__start__([__start__]):::first
	intent(intent)
	planning(planning)
	delegate(delegate)
	review(review)
	report(report)
	__end__([__end__]):::last
	__start__ --> intent;
	delegate --> review;
	intent --> planning;
	planning -.-> delegate;
	planning -.-> report;
	review -.-> delegate;
	review -.-> report;
	report --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

Reading the branches:

- `planning -.-> delegate` / `planning -.-> report` — `route_after_planning`: go
  build if the plan has components, else skip straight to the report.
- `review -.-> delegate` — `route_after_review`: advance to the next component,
  **or** re-deliver the current one as a fix (bounded by
  `settings.max_fix_attempts`).
- `review -.-> report` — queue exhausted (everything passed) or the fix cap was
  hit (escalate).
