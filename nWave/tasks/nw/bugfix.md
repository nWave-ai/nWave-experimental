---
description: Resolves one observed defect through the canonical DeliveryContract flow.
argument-hint: --repo-root <ROOT> --delivery-contract <repository-relative-json>
---

# NW-BUGFIX

Load `~/.claude/skills/nw-bugfix/SKILL.md`; it is the sole orchestration owner.
Do not reproduce its workflow in this task.

Require explicit `--repo-root <ROOT>` and `--delivery-contract <PATH>`. The
terminal DISTILL result supplies both, and `PATH` resolves only relative to
`ROOT`. Return WHAT/WHY/HOW for a missing, invalid, stale, ambiguous or escaping
locator; never search the current directory or fall back to a feature artifact.

The skill drives evidence-led RCA, architecture/reuse analysis, an ATD-owned
immutable regression oracle, canonical `/nw-deliver`, applicable source-blind
EXAMINE and one whole-delivery finalization.
