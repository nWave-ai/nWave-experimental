# ADR-002: Version Resolution Priority Chain (Floor > CZ > Patch Fallback)

## Status

Accepted

## Context

With Commitizen providing the base version for dev releases (ADR-001), the system needs a clear resolution order when multiple version sources conflict. Three sources can influence the dev version base:

1. **Commitizen output** (`cz bump --get-next`): commit-driven bump level
2. **Version floor** (`[tool.nwave].public_version`): manual override from pyproject.toml
3. **Patch fallback** (`_bump_patch()`): today's hardcoded behavior

The team needs the ability to force a version jump (e.g., 1.x to 2.0.0 for rebranding) regardless of what commits suggest, while also keeping a safety net when CZ fails.

## Decision

Implement a three-level priority chain within `calculate_dev()`:

```
1. Floor override  (highest priority: manual strategic control)
2. CZ base version (primary: commit-driven analysis)
3. _bump_patch     (safety net: fallback when CZ fails)
```

Floor wins over CZ only when `Version(floor) > Version(base)`. This is a "max" operation, not a simple override. If the floor is lower than the CZ-computed version, CZ wins. This prevents the floor from accidentally downgrading the version.

## Alternatives Considered

### Alternative 1: Floor always wins (unconditional override)

**Evaluation**: If floor is set to `1.1.0` (an old value) and CZ says `1.2.0`, the floor would downgrade the version to `1.1.0.dev1`. This would require teams to always keep `public_version` updated after every release.

**Rejection reason**: Foot-gun. Stale floor values would silently produce wrong versions. The "max" semantics are safer: a forgotten low floor is harmless.

### Alternative 2: CZ always wins over floor (floor only as fallback)

**Evaluation**: Floor would only apply when CZ fails. This removes the ability to force a version jump when CZ's commit analysis produces a lower version than the team's strategic intent.

**Rejection reason**: Removes the primary use case for floor: forcing a major version jump (e.g., 2.0.0) when the commit history only shows minor changes. Mike explicitly requested this capability.

### Alternative 3: Separate `--force-version` flag instead of floor

**Evaluation**: A dedicated `--force-version` CLI flag that, when set, unconditionally overrides everything. Would require a new pyproject.toml field or workflow input.

**Rejection reason**: Adds unnecessary complexity. The existing `[tool.nwave].public_version` field already serves this purpose and is already read by `read_toml_field.py`. Reusing it is simpler than introducing a new mechanism.

## Consequences

### Positive
- Floor cannot accidentally downgrade (max semantics)
- Stale floor values are harmless (ignored when lower)
- Pipeline never breaks (patch fallback always available)
- All three sources are independently testable via CLI args
- `_bump_patch` is never removed, preserving backward compatibility

### Negative
- Three-level priority requires clear documentation for operators (which value wins when?)
- Floor override is dev-stage only. If a team expects floor to also affect RC, they will be surprised. This is explicitly documented in US-CZ-04 and the architecture.

### Risks
- A team member may set `public_version = "99.0.0"` as a joke/test and forget to revert. All dev releases would use 99.0.0 as base until reverted. Mitigated by: code review on pyproject.toml changes.
