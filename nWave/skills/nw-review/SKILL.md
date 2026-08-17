---
name: nw-review
description: Dispatches an independent reviewer for a durable authority, immutable oracle, candidate diff, charter set, or operational artifact.
user-invocable: true
argument-hint: '[owner] [repository-relative artifact or diff identity]'
---

# NW-REVIEW

Select the reviewer that owns the artifact class. Give it the actual
repository-relative artifact or candidate identity, not copied prose.

Reviews are read-only and adversarial. Every finding cites a file/line,
terminal command or exhibited counterexample. `APPROVE` requires the artifact
to survive every applicable check; missing or stale evidence is
`INDETERMINATE`, not approval.

Review durable product/design authority at its owner, acceptance oracles with
the acceptance-designer reviewer, implementation diffs with the crafter
reviewer, charters with the PO reviewer, and platform artifacts with the
platform reviewer. A reviewer may veto but never silently repair the artifact.

Return the verdict, reviewed identity, findings and the single upstream owner
for each required correction.
