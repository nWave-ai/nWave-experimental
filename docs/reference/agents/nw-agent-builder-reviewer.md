# nw-agent-builder-reviewer

Use for review and critique tasks - Agent design and quality review specialist. Runs on Haiku for cost efficiency.

**Wave:** Other
**Model:** haiku
**Max turns:** 20
**Tools:** Read, Glob, Grep, Bash, Task

## Preloaded skills

- [nw-ab-anti-patterns](../skills/nw-ab-anti-patterns.md) — KNOWLEDGE — agent/skill/command anti-pattern catalog with fixes. Reference scanned by validate-spec; no sequence.
- [nw-ab-validation-checklist](../skills/nw-ab-validation-checklist.md) — KNOWLEDGE (data) — the 19-item agent-spec validation checklist. The item definitions the validate-spec / todoify procedures RUN against. No sequence of its own.
- [nw-abr-critique-dimensions](../skills/nw-abr-critique-dimensions.md) — Review dimensions for validating agent quality - template compliance, safety, testing, and priority validation
- [nw-cross-cutting-invariants](../skills/nw-cross-cutting-invariants.md) — Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..9, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
- [nw-review-workflow](../skills/nw-review-workflow.md) — Detailed review process, v2 validation checklist, and scoring methodology for agent definition reviews
