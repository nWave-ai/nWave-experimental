# Technology Stack: nWave Plugin Marketplace

**Date**: 2026-02-27

---

## Stack Summary

| Component | Technology | Version | License | Rationale |
|-----------|-----------|---------|---------|-----------|
| Build script | Python | >= 3.10 | PSF | Existing codebase language, reuses `build_dist.py` patterns |
| Import rewriting | Python `re` (stdlib) | stdlib | PSF | Already implemented in `des_plugin.py`, proven approach |
| JSON generation | Python `json` (stdlib) | stdlib | PSF | plugin.json and hooks.json are simple JSON |
| Version reading | `tomllib` (stdlib 3.11+) / `tomli` | >= 2.0.0 | MIT | Already in dependencies, reads pyproject.toml |
| File operations | `shutil`, `pathlib` (stdlib) | stdlib | PSF | Sufficient for copy operations, no external deps needed |
| CI/CD | GitHub Actions | N/A | N/A | Existing CI/CD platform, extend release.yml |
| Plugin metadata | Claude Code Plugin Spec | v1 | N/A | Target platform's native format |
| Testing | pytest | >= 8.0.0 | MIT | Existing test framework |

## Key Decision: No New Dependencies

The plugin build pipeline requires **zero new dependencies**. Every operation (file copying, JSON generation, import rewriting, version reading) uses Python stdlib or existing project dependencies.

This is deliberate: the build script must run in CI without additional setup, and adding dependencies for file manipulation would be resume-driven development.

## Technology NOT Selected

| Technology | Why Rejected |
|-----------|-------------|
| Jinja2 templates for hooks.json | hooks.json is 30 lines of static JSON with 3 variable substitutions. String formatting suffices. |
| Makefile / shell build | Zero shell scripts policy. Python build script is cross-platform and testable. |
| Docker for build isolation | Overkill for a file-copy build. No compilation, no environment-specific artifacts. |
| Custom CLI framework for build | `argparse` (already used in `build_dist.py`) is sufficient. No interactive prompts needed. |

## Existing Code Reuse

| Existing Code | Location | Reuse in Plugin Build |
|---------------|----------|----------------------|
| Import rewriting logic | `des_plugin.py:_rewrite_import_paths()` | Extract to shared module or inline (same regex patterns) |
| Bytecode cache clearing | `des_plugin.py:_clear_bytecode_cache()` | Same function, applied to plugin DES bundle |
| Version reading | `build_dist.py:_get_version()` | Identical function |
| File copy patterns | `build_dist.py:build_agents/commands/skills()` | Similar patterns, different target layout |
| Hook command template | `des_plugin.py:HOOK_COMMAND_TEMPLATE` | Adapted for `${CLAUDE_PLUGIN_ROOT}` |
