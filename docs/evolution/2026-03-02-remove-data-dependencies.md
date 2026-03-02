# Remove nWave/data/ Dependencies — Evolution Record

**Date**: 2026-03-02
**Feature ID**: remove-data-dependencies
**Issue**: #16

## Summary

Made nWave skills fully self-contained by removing all dependencies on `nWave/data/`. Trusted source config moved to project-level `.nwave/` with auto-seeding. Shared rules moved to `nWave/skills/common/`. Orphaned methodologies and research archives cleaned up.

## Changes

### Part 1: Trusted Sources (config/trusted-source-domains.yaml)

- **Before**: Researcher agent/skills referenced `nWave/data/config/trusted-source-domains.yaml` via file path
- **After**: `research.md` command reads from `.nwave/trusted-source-domains.yaml` at orchestration time, seeds defaults if missing, embeds inline in agent prompt
- **Impact**: 4 files updated (agent, 3 skill files), 2 commands rewritten (research.md, document.md)

### Part 2: Wizard Shared Rules (wizard-shared-rules.md)

- **Before**: `nWave/data/wizard-shared-rules.md` referenced by 3 wizard commands
- **After**: `nWave/skills/common/wizard-shared-rules.md` — same content with YAML frontmatter
- **Impact**: 3 wizard commands updated, docgen.py updated for `common/` skill directory

### Part 3: Cleanup

- Deleted `nWave/data/` entirely (13 files)
- Archived `nWave/data/research/` to `docs/analysis/` (7 files)
- Removed `nWave/data` from wheel force-include in release script

### Part 4: Validation

- Created `scripts/validation/validate_no_data_refs.py` — scans framework files for stale references
- 8 tests covering all bad patterns and clean codebase integration
- Zero remaining references confirmed via grep + validation script

### Review Fixes

- Removed dead allow-pattern logic from validation script (testing theater detection)
- Fixed stale `nWave/data/methodologies/` references in acceptance README
- Aligned researcher agent/skills to installed path `~/.claude/skills/nw/`

## Metrics

| Metric | Value |
|--------|-------|
| Roadmap steps | 9 (4 phases) |
| Files modified | 13 |
| Files created | 4 (skill, script, tests, init) |
| Files deleted | 13 (entire nWave/data/) |
| Files moved | 7 (research archives) |
| Tests added | 8 |
| Test suite | 2090 passed, 0 failed |

## Decisions

1. **No wizard mode for trusted sources** — Cut during principles/fallacies analysis. Over-engineering for a non-problem (editing YAML directly is simpler).
2. **Skills/common/ over inlining** — PO reviewer flagged DRY violation. Single source in `skills/common/` satisfies both self-containment and DRY.
3. **Auto-seed over migration** — Nirvana fallacy avoidance. Simple default seeding beats complex migration logic.
4. **No allow-pattern in validation** — Adversarial review caught that `docs/research/` allow pattern was dead code. Removed for simplicity.

## Commits

- `3916ce6c` — Move wizard-shared-rules, update wizard commands, fix docgen
- `2234a4a7` — Replace file path refs with prompt context in researcher
- `1bc0b33b` — Rewrite research.md with auto-seed orchestration
- `796da0d1` — Update document.md and command-design-patterns
- `de6cfd8b` — Update release script and test file
- `c2344fab` — Create validate_no_data_refs.py
- `d0ac1aa7` — Delete nWave/data/, archive research to docs/analysis/
- `9e8e3c8b` — Address adversarial review findings D1-D4
