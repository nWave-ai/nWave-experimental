# Migrating off the classic DELIVER spine

The classic, roadmap-based DELIVER spine is **deprecated** as of release N of
the staged ADR-032 cutover. It still resolves and runs as a fallback floor, but
`atdd_pure` is now the default spine. This guide explains what changed, how to
convert a project, and when the classic spine is removed.

## What changed in release N

Release N **deprecates** the classic spine — it does **not** remove it.

- A project that explicitly sets `workflow.mode: classic` in
  `.nwave/config.yaml` still dispatches on the classic spine. Every DELIVER
  dispatch emits a loud `ClassicSpineDeprecated` advisory.
- A project with **no** `workflow.mode` key now resolves to `atdd_pure` (the
  default flipped in slice-13). Previously an absent key meant `classic`.
- No classic artifact is deleted in release N. The classic CLIs, the roadmap
  schema, and the `nw-roadmap` skill and task remain on disk and fully
  functional. The DELETE sweep is the N+1 sibling epic
  `F-CLASSIC-SPINE-REMOVAL`.

The classic spine remains a safe **one-config-flip fallback** for the whole of
release N: if a project hits a blocker on `atdd_pure`, setting
`workflow.mode: classic` restores the prior behaviour with zero data loss.

## How to convert a project to `atdd_pure`

Conversion is automated by the `des-convert-to-atdd-pure` CLI. The recommended
sequence is:

1. **Classify** the feature tree to see which features are convertible:

   ```bash
   python -m des.cli.classify_features \
     --features-root docs/feature \
     --out migration-manifest.json
   ```

2. **Preview** the conversion for a feature — a dry run writes nothing:

   ```bash
   python -m des.cli.convert_to_atdd_pure \
     --workspace . --feature-id my-feature --dry-run
   ```

3. **Convert** the feature. The conversion is journalled, resumable, and
   rollback-able:

   ```bash
   python -m des.cli.convert_to_atdd_pure \
     --workspace . --feature-id my-feature
   ```

   This promotes the DESIGN slice plan into a `## Wave: DISCUSS / [REF] Slice
   Plan` heading, seeds the AT-completion ledger, flips `workflow.mode` to
   `atdd_pure`, and archives `deliver/roadmap.json` under
   `deliver/.classic-archive/`.

4. **Roll back** if anything looks wrong — a partial conversion is fully
   reversible:

   ```bash
   python -m des.cli.convert_to_atdd_pure \
     --workspace . --feature-id my-feature --rollback
   ```

To convert many features in one pass, use `--drain` with `--feature-ids`. The
drain converts every convertible feature and parks any untagged or
manual-review feature on `migration-parked.json` rather than failing the run.

## Removal timeline

| Release | Classic spine status |
|---|---|
| Release N (this release) | Deprecated. Resolves, runs, emits a per-dispatch advisory. No artifact deleted. |
| Release N+1 (`F-CLASSIC-SPINE-REMOVAL`) | Removed. The classic CLIs, the roadmap schema, and the `nw-roadmap` skill/task are deleted. `workflow.mode: classic` no longer resolves. |

Convert your projects to `atdd_pure` during release N. Once release N+1 ships,
the classic fallback is gone and an unconverted project will no longer
dispatch.

## Audit-log replay is preserved

Removing the classic spine does **not** invalidate historical audit logs.
Pre-2026-05-07 commits carrying legacy 5-phase, v2.0 pipe-delimited
`execution-log.json` events continue to replay cleanly through
`des-verify-commit-trailers` and the `PhaseEventParser` MARK-HISTORICAL path.
Your project history stays verifiable across the cutover.
