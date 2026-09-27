---
name: nw-review
description: Dispatches an independent reviewer for a durable authority, immutable oracle, candidate diff, charter set, or operational artifact.
user-invocable: true
argument-hint: '[owner] [repository-relative artifact or diff identity]'
---

# NW-REVIEW

Before diagnosing or assigning corrections, load `nw-cross-cutting-invariants`
and apply `delivery:trustworthy-baseline-and-repair-scope`. A blocking observation
requires attention; it does not alone authorize an independent repair.


Select the reviewer that owns the artifact class. Give it the actual
repository-relative artifact or actual diff, not copied prose.

Read `~/.claude/skills/nw-role-invocation/SKILL.md`. Invoke the exact installed
reviewer/examiner role natively, or `des prepare-role` then `des invoke-role`
(exact flags from `--help`). A tools-empty role cannot read paths: put the
actual evidence bytes in its prompt.

Reviews are read-only and adversarial. Every finding cites a file/line,
terminal command or exhibited counterexample. `APPROVE` requires the artifact
to survive every applicable check; missing or stale evidence is
`INDETERMINATE`, not approval.

Review durable product/design authority at its owner, acceptance oracles with
the acceptance-designer reviewer, implementation diffs with the crafter
reviewer, charters with the PO reviewer, and platform artifacts with the
platform reviewer. A reviewer may veto but never silently repair the artifact.

Return the verdict, reviewed artifact or diff, findings and the single upstream
owner for each required correction.

## Convergence

A review converges only against a CLOSED criterion set. Four rules, all binding.

- **Declared before, not chosen during.** The dispatcher states the original agreed
  value and the closed criteria in the dispatch. The reviewer first checks that the
  criteria preserve that value, then judges the declared set. Where an executable
  reference model exists, the set is "the surface agrees with the model" plus the
  named suites; anything outside it is not review material. A criterion the reviewer
  invents mid-review is out of scope, however true it is.
- **Classify against the request.** Judge agreed behavior, required quality and
  delivery obligations, and regressions caused by the request's work. Apply the
  shared repair-scope clause to safety-net failures and uncertain relevance.
  Independent improvements are notes, not automatic same-slice corrections.
- **Preserve the safety net.** A required failure cannot be waived. Its owner
  diagnoses and restores the required verification within the existing authority;
  independent redesign requires a scope decision, not an implicit repair chain.
  For public behavior corrections, compare existing coverage with the counterexample;
  invoke ATD only for uncovered behavior. Retain normal independent review after
  corrections; notes alone do not require another review round.
- **Precise instruction repair is allowed.** Change the smallest instruction bytes
  that remove a proven contradiction. State measurable claims in executable checks
  where one exists; prose may state role boundaries, ownership, or remediation.

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

- **T5** [MECHANICAL] -- declared progress/liveness: show do-nothing;
  model-check liveness excludes it; safety-only: `NOT_APPLICABLE`.
- **T6** [INSPECTIVE] -- name every fairness assumption's real guarantor,
  monitor, and violation consequence.
- **T7** [JUDGEMENT] -- list every model step and name the real code
  mechanism guaranteeing its atomicity; the answer must be a code
  reference, never prose. If it cannot be named, the review returns the
  QUESTION to the human, not a verdict.

**Marking rule (three values, load-bearing):** MECHANICAL = a tool answers,
the outcome is a fact -- if the tool was not executed, the review is
INCOMPLETE BY CONSTRUCTION, never approvable. INSPECTIVE = no tool, but the
answer is a fact readable on the artifact. JUDGEMENT = the answer is a
question returned to the human, never a verdict.
