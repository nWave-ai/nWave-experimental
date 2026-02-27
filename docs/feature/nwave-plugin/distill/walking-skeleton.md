# Walking Skeleton: nWave Plugin Build

**Date**: 2026-02-27
**Feature**: nwave-plugin-marketplace

---

## Walking Skeleton Definition

The walking skeleton for the plugin marketplace feature answers one question:

> Can the build pipeline transform the nWave source tree into a plugin directory that contains metadata, agents, commands, and skills?

This is the thinnest possible vertical slice: one build invocation producing one plugin directory with observable content.

## Walking Skeletons (3 total)

### WS-1: Simplest plugin build produces a directory with metadata

**Feature file**: `walking-skeleton.feature`
**User goal**: Build a plugin directory from source
**Observable outcome**: Directory exists with plugin.json, agents, commands, skills
**Driving port**: `PluginAssembler.build(config)`
**Implementation order**: FIRST

### WS-2: Developer verifies a freshly built plugin is structurally complete

**Feature file**: `walking-skeleton.feature`
**User goal**: Validate a built plugin before distribution
**Observable outcome**: Validation passes, all sections confirmed present
**Driving port**: `PluginValidator.validate(plugin_dir)`
**Implementation order**: SECOND (after WS-1)

### WS-3: Built plugin includes DES enforcement hooks

**Feature file**: `walking-skeleton.feature`
**User goal**: Plugin enforces TDD phases via hooks
**Observable outcome**: hooks.json exists, DES module importable
**Driving port**: `PluginAssembler.build(config)` (DES bundling path)
**Implementation order**: THIRD (after WS-2)

## Implementation Sequence

1. Enable WS-1 (remove @skip tag -- it has none, it is the first scenario)
2. Implement `BuildConfig`, `MetadataGenerator`, and basic `PluginAssembler.build()` that copies agents/skills/commands and generates plugin.json
3. WS-1 passes
4. Enable WS-2
5. Implement `PluginValidator.validate()` returning sections report
6. WS-2 passes
7. Enable WS-3
8. Implement DES bundling (import rewriting, hooks.json generation)
9. WS-3 passes
10. All walking skeletons green -- proceed to focused scenarios

## Stakeholder Demo Script

After WS-1 passes, demonstrate:
- "Here is the build command output -- a plugin directory."
- "It contains 23 agents, 98+ skills, 21+ commands."
- "The plugin.json has version 2.18.0 matching our release."
- "A user would install this with one command in Claude Code."
