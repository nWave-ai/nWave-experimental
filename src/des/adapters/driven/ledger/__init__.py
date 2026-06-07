"""Coverage-map signoff ledger writer (F-DISTILL-HUMAN-SIGNOFF slice-04).

Hard architectural boundary (G5, two-layer): the only callers of
``write_coverage_map_signed_off()`` MUST live in this package or in the
whitelisted set of ``src/des/`` engine modules declared in
``coverage_map_signoff_writer._ENGINE_CALLER_ALLOWLIST``. An LLM-agent
dispatch path that reaches this writer is a P0 architecture violation.
"""
