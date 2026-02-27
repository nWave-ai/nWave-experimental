# Test Scenarios: nWave Plugin Marketplace

**Date**: 2026-02-27
**Feature**: nwave-plugin-marketplace
**Total scenarios**: 59
**Error/edge ratio**: 46% (27 error+edge out of 59)

---

## Scenario Summary by Milestone

### Walking Skeleton (3 scenarios)

| # | Scenario | Type | Tag |
|---|----------|------|-----|
| 1 | Simplest plugin build produces a directory with metadata | Happy | @walking_skeleton |
| 2 | Developer verifies a freshly built plugin is structurally complete | Happy | @walking_skeleton |
| 3 | Built plugin includes DES enforcement hooks | Happy | @walking_skeleton @skip |

### Milestone 1: Plugin Assembler (18 scenarios)

| # | Scenario | Type | Tag |
|---|----------|------|-----|
| 4 | Plugin metadata includes version from project configuration | Happy | @skip |
| 5 | Plugin metadata includes required marketplace fields | Happy | @skip |
| 6 | All agent definitions are included in the plugin | Happy | @skip |
| 7 | Agent files are copied without modification | Happy | @skip |
| 8 | All skill files are included preserving directory structure | Happy | @skip |
| 9 | Skill files are copied as-is without renaming | Happy | @skip |
| 10 | All command definitions are included in the plugin | Happy | @skip |
| 11 | Command files support the nw namespace for slash commands | Happy | @skip |
| 12 | Version flows from single source of truth | Happy | @skip |
| 13 | Build fails when source tree is missing agents directory | Error | @skip |
| 14 | Build fails when source tree is missing skills directory | Error | @skip |
| 15 | Build fails when project version cannot be read | Error | @skip |
| 16 | Build fails when source tree is missing commands directory | Error | @skip |
| 17 | Build succeeds with minimum viable source tree | Edge | @skip |
| 18 | Build handles agent files with special characters in names | Edge | @skip |
| 19 | Every source agent appears exactly once in the plugin | Property | @skip @property |
| 20 | Plugin version always matches source version | Property | @skip @property |

### Milestone 2: DES Bundle (14 scenarios)

| # | Scenario | Type | Tag |
|---|----------|------|-----|
| 21 | DES module is importable from the plugin directory | Happy | @skip |
| 22 | DES imports are rewritten for standalone operation | Happy | @skip |
| 23 | DES module requires only standard library | Happy | @skip |
| 24 | Hook registrations cover all DES enforcement events | Happy | @skip |
| 25 | Hook commands use plugin-relative paths | Happy | @skip |
| 26 | DES runtime templates are bundled in the plugin | Happy | @skip |
| 27 | Build fails when DES source directory is missing | Error | @skip |
| 28 | Build fails when import rewriting produces invalid syntax | Error | @skip |
| 29 | Build fails when hook template references are invalid | Error | @skip |
| 30 | DES bytecode cache is cleared in the plugin output | Edge | @skip |
| 31 | Every DES source file has its imports rewritten correctly | Property | @skip @property |
| 32 | Hook configuration always contains all required event types | Property | @skip @property |

### Milestone 3: Plugin Validation (12 scenarios)

| # | Scenario | Type | Tag |
|---|----------|------|-----|
| 33 | Valid plugin passes all structural checks | Happy | @skip |
| 34 | Validation confirms all required plugin sections exist | Happy | @skip |
| 35 | Validation confirms hook configuration is well-formed | Happy | @skip |
| 36 | Validation counts match expected component totals | Happy | @skip |
| 37 | Validation fails when metadata file is missing | Error | @skip |
| 38 | Validation fails when agents directory is empty | Error | @skip |
| 39 | Validation fails when hooks configuration is missing | Error | @skip |
| 40 | Validation fails when DES module is absent | Error | @skip |
| 41 | Validation reports all errors at once rather than stopping at first | Error | @skip |
| 42 | Validation succeeds with minimum viable plugin | Edge | @skip |
| 43 | Validation is a pure function with no side effects | Property | @skip @property |

### Milestone 4: Release Pipeline (7 scenarios)

| # | Scenario | Type | Tag |
|---|----------|------|-----|
| 44 | Plugin build integrates into existing release workflow | Happy | @skip |
| 45 | Plugin version matches the release version | Happy | @skip |
| 46 | Plugin directory is ready for repository publication | Happy | @skip |
| 47 | Marketplace manifest is generated for self-hosted distribution | Happy | @skip |
| 48 | Release pipeline fails gracefully when plugin build fails | Error | @skip |
| 49 | Release pipeline detects version mismatch between tag and metadata | Error | @skip |
| 50 | Plugin build is idempotent across repeated runs | Edge | @skip |

### Milestone 5: Coexistence (10 scenarios)

| # | Scenario | Type | Tag |
|---|----------|------|-----|
| 51 | Plugin installs to a different location than custom installer | Happy | @skip |
| 52 | Plugin operates independently when custom installer is absent | Happy | @skip |
| 53 | Custom installer operates independently when plugin is absent | Happy | @skip |
| 54 | Both plugin and custom installer active without conflicts | Happy | @skip |
| 55 | No duplicate hook registrations when both are active | Happy | @skip |
| 56 | Conflicting versions between plugin and custom installer are detected | Error | @skip |
| 57 | Removing custom installer does not corrupt plugin installation | Error | @skip |
| 58 | Removing plugin does not corrupt custom installer | Error | @skip |
| 59 | Plugin and custom installer paths never overlap | Property | @skip @property |

---

## Coverage Analysis

### By Type

| Type | Count | Percentage |
|------|-------|------------|
| Happy path | 30 | 51% |
| Error path | 16 | 27% |
| Edge case | 6 | 10% |
| Property | 7 | 12% |
| **Error+Edge+Property** | **29** | **49%** |

Error path ratio: 49% (exceeds 40% target)

### By Roadmap Step

| Step | AC Count | Scenario Count | Coverage |
|------|----------|----------------|----------|
| 01-01 Plugin Assembler | 4 | 18 | Full |
| 01-02 DES Bundle | 4 | 14 | Full |
| 01-03 Plugin Validation | 3 | 12 | Full |
| 02-01 Release Pipeline | 3 | 7 | Full |
| 02-02 Coexistence | 4 | 10 | Full |

### Property-Shaped Scenarios (@property tag)

7 scenarios tagged `@property` for the DELIVER wave crafter to implement as property-based tests:
1. Every source agent appears exactly once in the plugin
2. Plugin version always matches source version
3. Every DES source file has its imports rewritten correctly
4. Hook configuration always contains all required event types
5. Validation is a pure function with no side effects
6. Plugin and custom installer paths never overlap
7. (implicit in idempotency scenario)

---

## Implementation Sequence

Enable scenarios in this order (one at a time):

1. WS-1: Simplest plugin build (FIRST -- already enabled)
2. WS-2: Plugin validation walking skeleton
3. WS-3: DES hooks walking skeleton
4. M1-1: Plugin metadata includes version
5. M1-2: All agents included
6. M1-3: All skills included
7. M1-4: All commands included
8. M1-5 through M1-9: Remaining happy paths
9. M1-10 through M1-13: Error paths
10. M2 scenarios (DES bundle)
11. M3 scenarios (validation)
12. M4 scenarios (release pipeline)
13. M5 scenarios (coexistence)

---

## Driving Ports (Entry Points)

All scenarios invoke through these driving ports only:

| Port | Module | Responsibility |
|------|--------|---------------|
| `PluginAssembler.build(config)` | `scripts/build_plugin.py` | Main build pipeline |
| `PluginValidator.validate(dir)` | `scripts/build_plugin.py` | Structural validation |
| `ContentTransformer.rewrite_imports(content)` | `scripts/build_plugin.py` | DES import rewriting |
| `HooksGenerator.generate(config)` | `scripts/build_plugin.py` | hooks.json generation |
| `MetadataGenerator.generate(version, config)` | `scripts/build_plugin.py` | plugin.json generation |
