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

## Design-review question set

Structure (algebra) and time (protocol) questions that make a design review
adversarial instead of confirmatory. Finds structural incoherence, never
temporal holes -- a temporal gap needs the model checker (T5), not this list.

**Structure (algebra):**

- **S1** [INSPECTIVE] -- for every finite sum type, list the cases and pair
  each with its domain meaning; flag any case with no meaning and any
  meaning split across cases.
- **S2** [MECHANICAL] -- for every pair of invariants mentioning the same
  field, construct a state satisfying the first and check the second,
  delegated to a property test; "I couldn't find one" is not evidence.
- **S3** [MECHANICAL] -- for every invariant proven under an added
  hypothesis, remove the hypothesis and verify a counterexample still
  exists; if none exists the hypothesis was decorative, and the
  conditional theorem was the signal a type was needed.
- **S4** [INSPECTIVE] -- every unreachable arm of a total function must be
  made unreachable by the type, never by a comment.

**Time (protocol):**

- **T5** [MECHANICAL] -- for every safety property, exhibit the do-nothing
  behaviour and verify a liveness property excludes it, via a model checker.
- **T6** [INSPECTIVE] -- list every fairness assumption used and where the
  real system guarantees it.
- **T7** [JUDGEMENT] -- list every model step and name the real code
  mechanism guaranteeing its atomicity; the answer must be a code
  reference, never prose. If it cannot be named, the review returns the
  QUESTION to the human, not a verdict.

**Marking rule (three values, load-bearing):** MECHANICAL = a tool answers,
the outcome is a fact -- if the tool was not executed, the review is
INCOMPLETE BY CONSTRUCTION, never approvable. INSPECTIVE = no tool, but the
answer is a fact readable on the artifact. JUDGEMENT = the answer is a
question returned to the human, never a verdict.
