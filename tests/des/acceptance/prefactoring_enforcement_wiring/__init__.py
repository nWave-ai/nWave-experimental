"""Regression package: wire the Prefactoring Assessment validator into the
TWO enforcement surfaces that consult it today only via a `--flag`, never
automatically -- `des verify-readiness-pre-dispatch` (a hard REFUSING
invariant) and `des dispatch` (a proactive advisory, GDP-1/2).

The pure validator `validate_prefactoring_assessment_content` and the
`--require-prefactoring-assessment` CLI flag shipped already
(`src/des/cli/validate_feature_delta.py`, commits
8fd3f2b40/beff813fe/6818e71b3) but NO gate consulted them -- catalogued, not
wired.
"""
