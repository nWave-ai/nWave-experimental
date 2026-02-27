# Shared Artifacts Registry: nw-rigor

**Epic**: nw-rigor
**Last updated**: 2026-02-25

---

## Primary Artifacts (produced by /nw:rigor)

| Artifact | Type | Source | Consumers | Format | Storage |
|----------|------|--------|-----------|--------|---------|
| `rigor.profile` | string | /nw:rigor save step | All /nw:* commands, DES orchestrator | `lean\|standard\|thorough\|exhaustive\|inherit` | `.nwave/des-config.json` |
| `rigor.agent_model` | string | Derived from profile | Task tool invocations, agent frontmatter | `haiku\|sonnet\|opus\|inherit` | `.nwave/des-config.json` |
| `rigor.reviewer_model` | string | Derived from profile | /nw:review, /nw:deliver Phase 4 | `skip\|haiku\|sonnet\|opus` | `.nwave/des-config.json` |
| `rigor.tdd_phases` | array | Derived from profile | DES TDD cycle enforcement, /nw:execute | Phase name strings | `.nwave/des-config.json` |
| `rigor.review_enabled` | boolean | Derived from profile | /nw:deliver Phase 4, /nw:design | `true\|false` | `.nwave/des-config.json` |
| `rigor.mutation_enabled` | boolean | Derived from profile | /nw:deliver Phase 5 | `true\|false` | `.nwave/des-config.json` |
| `rigor.double_review` | boolean | Derived from profile | /nw:deliver Phase 4 | `true\|false` | `.nwave/des-config.json` |
| `rigor.refactor_pass` | boolean | Derived from profile | /nw:deliver Phase 3 | `true\|false` | `.nwave/des-config.json` |

## Profile-to-Artifact Mapping

| Artifact | lean | standard | thorough | exhaustive | inherit |
|----------|------|----------|----------|------------|---------|
| `agent_model` | haiku | sonnet | opus | opus | inherit |
| `reviewer_model` | skip | haiku | sonnet | opus | haiku |
| `tdd_phases` | [RED_UNIT, GREEN] | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT] | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT] | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT] | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT] |
| `review_enabled` | false | true | true | true | true |
| `double_review` | false | false | true | true | false |
| `mutation_enabled` | false | false | false | true | false |
| `refactor_pass` | false | true | true | true | true |

## Config Schema (des-config.json)

```json
{
  "audit_logging_enabled": true,
  "skill_tracking": "disabled",
  "rigor": {
    "profile": "standard",
    "agent_model": "sonnet",
    "reviewer_model": "haiku",
    "tdd_phases": ["PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN", "COMMIT"],
    "review_enabled": true,
    "double_review": false,
    "mutation_enabled": false,
    "refactor_pass": true
  }
}
```

## Existing Artifacts (not modified by /nw:rigor)

| Artifact | Owner | Relationship |
|----------|-------|-------------|
| `audit_logging_enabled` | DES config | Independent -- rigor does not affect audit logging |
| `skill_tracking` | DES config | Independent -- rigor does not affect skill tracking |
| `deliver-session.json` | /nw:deliver | Consumer -- reads rigor profile at session start |
| `execution-log.yaml` | DES | Consumer -- TDD phases logged are determined by rigor |

## Integration Checkpoints

| ID | Between | Validates | Failure |
|----|---------|-----------|---------|
| IC-R1 | /nw:rigor save -> des-config.json | Valid JSON, rigor key present | Config write error |
| IC-R2 | des-config.json -> /nw:deliver | Deliver reads rigor before dispatching agents | Falls back to standard |
| IC-R3 | des-config.json -> /nw:execute | Execute reads tdd_phases for cycle enforcement | Falls back to 5-phase |
| IC-R4 | des-config.json -> /nw:review | Review reads reviewer_model and review_enabled | Falls back to haiku + enabled |
| IC-R5 | rigor.agent_model -> Task tool | Task invocation uses correct model parameter | Falls back to session model |
| IC-R6 | rigor.mutation_enabled -> /nw:deliver Phase 5 | Deliver skips or runs mutation based on flag | Falls back to per-feature strategy |

## Default Behavior (no profile set)

When no rigor profile is configured in des-config.json:
- All wave commands behave as if `standard` is selected
- No prompt is shown -- commands proceed with defaults
- `/nw:rigor` without a profile set shows "Current profile: none set (using standard defaults)"
