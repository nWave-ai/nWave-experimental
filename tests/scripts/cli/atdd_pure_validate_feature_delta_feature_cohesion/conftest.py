"""pytest-bdd configuration for the discuss-epic-mode slice-03 acceptance set.

atdd_pure (the path): this AT set is authored JIT for slice-03 -- the
feature-granularity cohesion-MECC witness. Per ADR-GV-001 D6 there is NO
``@skip`` / ``@xfail`` markering and NO ``pytest_bdd_apply_tag`` translation hook
here -- the scenarios are active.

WITNESS-GREEN note (HONEST, escalated to the orchestrator): the slice-03
behaviour -- an all-@infrastructure Feature Plan returns ``rejected-infra-only``
with a feature-mode detail, a mixed plan returns ``accepted`` -- already ships on
the current tip. It landed in slice-01's commit ``e4e5e6b02`` as a NECESSARY
consequence of building the shared generic ``_validate_plan_content`` core: the
core calls ``_classify_slice_cohesion(data_rows, spec.row_noun)`` for BOTH plan
modes, and the feature spec carries ``row_noun="feature"``. The slice-03 seam is
therefore WIRED (a real call-site reached from the real entry point) but, before
this suite, UNWITNESSED by any acceptance test. These ATs are the witness; they
go GREEN against already-correct production. Fabricating a RED here would be the
false-RED / Fixture-Theater anti-pattern (the fail-for-the-right-reason gate
exists to block exactly that). See the slice-03 red-classification doc for the
full reasoning + escalation.
"""

from __future__ import annotations
