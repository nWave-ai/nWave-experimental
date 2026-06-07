"""Acceptance suite for fix-mandate-9-v2-rollout slice-01.

Slice-01 ships walking-skeleton-first per Sentinel BLOCKER ORDERING-O1:
  (a) `slice_kinds` enum vocabulary in `framework-catalog.yaml`
      including `adapter-integration` as new first-class entry,
  (b) `MandateNineTagMismatch` detector in `carpaccio_slice_gate.py`
      (non-blocking warning on @real-io tag vs mock-only composition mismatch),
  (c) `docs/architecture/at-real-io-audit-2026-05-27.md` retro-audit scaffold
      (5-column schema headers; empty rows acceptable at slice-01),
  (d) `nw-test-design-mandates/SKILL.md` Mandate 9 v2 minimal frame stub.

Slice-02 ships the behavioral skill/agent/reviewer expansions; slice-03 ships
audit closure + gate promotion to blocking.
"""
