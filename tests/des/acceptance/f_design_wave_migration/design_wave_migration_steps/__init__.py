"""Step package for f-design-wave-migration Gherkin ATs.

UNIQUE package name (``design_wave_migration_steps`` via this nested path) so
pytest-bdd's process-global step registry never shadows another feature's step
bodies (S1 step-text uniqueness). Step bodies delegate to per-slice composition
roots; no business logic lives in the step bindings (Mandate-12 criterion 3).

These ATs are a TEST-FORMAT conversion of the plain-pytest f-design-wave-migration
suite into carpaccio-conformant ``@slice-NN`` Gherkin so the feature becomes
per-slice attestable. The PRODUCTION prose already ships GREEN — this is a format
conversion of passing behaviour, NOT new behaviour. Each scenario remains GENUINE
(mutation-verifiable): perturbing the asserted SKILL.md prose reds the scenario.

Driving surface (Mandate-13 driving-port-only):
  * slice-01/02 (AT-3/4) / 03 / 04 — the filesystem read of the REAL shipped
    skill files (``nWave/skills/nw-distill/SKILL.md`` + ``nw-deliver/SKILL.md``)
    via the shared ``_skill_source`` helper (Mandate-13 prose-surface case).
  * slice-02 AT-6 — the REAL ``DESConfig`` port (a production config port; the
    one permitted ``des.adapters.*`` import, exactly as the original AT-6 drove
    it) against a temp config dir.
"""
