"""Cross-OS multi-tool RC boot-smoke harness.

Orchestrates per-tool install + boot + artifact-provisioning smoke checks
(claude-code / codex / opencode) via injected ports (installer, process,
filesystem), producing a ``SmokeResult`` per tool. See ``runner.py`` for the
orchestration order and ``contracts.py`` for the per-tool registry.
"""
