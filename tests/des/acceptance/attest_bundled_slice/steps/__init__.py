"""Step package for f-attest-bundled-slice ATs.

UNIQUE package name (``attest_bundled_slice_steps`` via this nested path) so
pytest-bdd's process-global step registry never shadows another feature's step
bodies (S1 step-text uniqueness). Step bodies delegate to the composition root;
no business logic lives here (Mandate-12 criterion 3).
"""
