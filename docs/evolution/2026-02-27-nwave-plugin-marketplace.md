# nWave Plugin Marketplace — Evolution Record

**Date**: 2026-02-27
**Feature**: nwave-plugin-marketplace (Phase 0.5)
**Wave Sequence**: DISCUSS → DESIGN → DISTILL → DELIVER
**Paradigm**: Functional Programming

## Summary

Implemented the complete plugin build pipeline that packages nWave as a Claude Code plugin for the Anthropic marketplace. The pipeline assembles 23 agents, 98+ skills, 21 commands, DES hooks with import rewriting, and metadata into a standalone plugin directory.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Build pipeline design | Pure function pipeline with frozen dataclasses | FP paradigm, testability, no side effects in domain logic |
| Hook command paths | `${CLAUDE_PLUGIN_ROOT}/scripts` | Plugin portability (not `$HOME` which ties to installer) |
| Hook wrapper | Python script (not bash) | Zero-shell-scripts policy, cross-platform compliance |
| Import rewriting | Regex-based `src.des` → `des` with AST validation | Consistent with existing build_dist.py approach |
| Validation strategy | Report ALL errors, no short-circuit | Better developer experience on build failures |
| Coexistence model | Path disjointness (plugin paths never overlap installer paths) | Side-by-side operation during migration period |

## ADRs Referenced

- ADR-001: Plugin Directory Structure
- ADR-002: DES Import Rewriting Strategy
- ADR-003: Coexistence and Migration Path

## Deliverables

| Artifact | Path | Lines |
|----------|------|-------|
| Build pipeline | `scripts/build_plugin.py` | ~870 |
| Release pipeline | `.github/workflows/release.yml` (2 new jobs) | +113 |
| Migration guide | `docs/guides/plugin-migration-guide.md` | 80 |
| BDD acceptance tests | `tests/build/acceptance/plugin/` (6 features, 5 step files) | ~1700 |
| Roadmap | `docs/feature/nwave-plugin/deliver/roadmap.json` | 108 |

## Test Results

- **69 BDD scenarios passing**, 2 skipped (1 DES runtime, 1 CI simulation)
- **5 Hypothesis property-based tests** — pure function verification (version roundtrip, import idempotency, hook event count)
- **5 coexistence scenarios** — structural contract testing (path disjointness, version consistency, settings isolation)
- **Full suite**: 2066 passed, 0 failed, 7 skipped, 2 xfail
- **Zero regressions** introduced

## Quality Gates

| Gate | Status |
|------|--------|
| Roadmap approved | PASS |
| All steps COMMIT/PASS | PASS (5/5 steps) |
| L1-L4 refactoring | PASS (21 findings, 10 addressed) |
| Adversarial review | PASS (2 security, 4 bugs, 8 testing theater — all fixed) |
| Mutation testing | DEFERRED (per-feature, delegated to CI) |
| Hypothesis PBT | PASS (5 @property scenarios implemented) |
| Coexistence tests | PASS (5 runtime scenarios → structural contracts) |
| Full test suite green | PASS (2066/2066) |

## Key Review Findings (Fixed)

1. **SEC-2**: VERSION interpolated into Python `-c` source code — fixed with env var + semver validation
2. **BUG-1**: `hook_template_override` validated but discarded — fixed to use override entries
3. **BUG-3**: Bash hook wrapper violated zero-shell policy — replaced with Python
4. **BUG-2**: `_cleanup_on_failure` could destroy pre-existing directories — added `created_by_build` guard
5. **TT-1-8**: 8 Testing Theater patterns (assertion-free, conditional, hardcoded) — all fixed

## Scope Boundaries (Phase 0.5)

**In scope**: Single-platform plugin build pipeline (Claude Code only)
**Deferred**: Cross-platform support (OpenCode, Codex CLI, Copilot CLI), DES MCP server, marketplace submission automation

## Next Steps

1. Submit plugin to `claude-plugins-official` marketplace
2. Run mutation testing on `scripts/build_plugin.py` with focused test scope
