---
name: nw-devops-environment-inventory
description: "DEVOPS mandatory environment-inventory deliverable — produce environments.yaml (target environments, coexistence matrix, platform coverage, deployment assumptions) that DISTILL parses to parametrize acceptance scenarios over target environments (Mandate 4 / Environmental Realism). Run BEFORE completing the DEVOPS wave."
user-invocable: false
disable-model-invocation: true
---

# DEVOPS Environment Inventory (PROCEDURE)

**Kind**: PROCEDURE | **One job**: produce the environment inventory deliverable | **One trigger**: the DEVOPS wave is about to complete and `environments.yaml` has not yet been produced.

Composed by `nw-devops`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Mandatory Deliverable: Environment Inventory

BEFORE completing the DEVOPS wave, produce the environment inventory:

1. **Create file** — Write `docs/feature/{feature-id}/devops/environments.yaml` with the structure below. Gate: file written.
2. **Populate target environments** — List all deployment environments with name, description, platform, and preconditions. Gate: at least one environment entry present.
3. **Define coexistence matrix** — List tools that must not break alongside the deployment (e.g., pre-commit, husky). Gate: matrix present.
4. **Specify platform coverage** — List OS/platform versions to support. Gate: coverage table complete.
5. **Document deployment assumptions** — List idempotency, uninstall safety, and hook coexistence requirements. Gate: assumptions enumerated.

```yaml
# environments.yaml — consumed by DISTILL for Mandate 4 (Environmental Realism)
target_environments:
  - name: clean
    description: "Fresh install, no prior state"
    platform: [linux, macos, wsl]
    preconditions: []
  - name: with-pre-commit
    description: "Pre-commit hooks installed and active"
    platform: [linux, macos, wsl]
    preconditions: ["pre-commit installed", "core.hooksPath set to .git/hooks"]
  - name: with-stale-config
    description: "Outdated configuration from prior version"
    platform: [linux, macos]
    preconditions: ["legacy config present", "version mismatch"]

coexistence_matrix:
  - tool: pre-commit
    must_not_break: true
  - tool: husky
    must_not_break: true

platform_coverage:
  macOS: [12.x, 13.x, 14.x]
  Linux: [Ubuntu 22.04, Ubuntu 24.04]
  WSL: [WSL2]
  CI: [GitHub Actions ubuntu-latest]

deployment_assumptions:
  - "Installation MUST be idempotent (safe to run twice)"
  - "Uninstall MUST remove only nWave artifacts"
  - "Hooks MUST survive alongside existing hook managers"
```

For features that do NOT install into systems (pure business logic), the environment inventory contains only `target_environments: [{name: clean, platform: [linux, macos]}]`.

DISTILL reads this file to parametrize acceptance scenarios over target environments. If this file is missing, DISTILL uses defaults (clean, with-pre-commit, with-stale-config) — but coverage gaps are the PA's responsibility.
