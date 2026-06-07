"""Acceptance suite for fix-reverify-e1-via-scoped-wrapper.

Closes F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION (PRR D2 blocker). The W5 row of
the reverify E1 decision table (>=2 features sharing @slice-NN, feature-
scoped) -- the row the existing reverify ATs miss -- is witnessed in
slice-02; slice-01 ships the SSOT extraction + thin wrapper that makes
feature-scoped E1 invocation possible without dragging in the atomic
verify-then-record exit gate.
"""
