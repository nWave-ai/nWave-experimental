# Checking an Existing Project Before an nWave Update

Use `des update` to inspect persisted artifacts in a project before applying
an available migration. This command does not promise a conversion from every
older workflow or every v3 project.

### Compatibility boundary

The latest retained stable v3 source, `v3.22.2`, writes
`execution-log.json` under its selected project document directory, with
`schema_version: "3.0"` and an `events` array. The current `des update`
discovery is limited to `.nwave/`; it does not convert those execution logs.
A successful preview is therefore not proof that an active v3 delivery can
resume under v4.

The packaged step-cycle catalog accepts artifact tags `v4` and `v4-revised`
and maps them to `v5`. These are **artifact format tags**, not nWave package
versions. They do not establish a v3-package-to-v4-package migration.
Preserve the old checkout, its runtime, and the project files until active
v3 work is complete or an explicit compatible transition is available.
Completed logs outside `.nwave/` remain historical files; do not delete or
rewrite them to make the preview pass.

## Preview the project

From an environment with the selected nWave runtime available:

```bash
python -P -m des.cli.update --dry-run --root /absolute/path/to/project
```

For readable JSON objects, the preview reports each discovered artifact under
the project's `.nwave/` directory, its declared version, whether the
registered versioning kernel can read it, its status, a planned action, and a
reason. Malformed or non-object JSON stops the preview with the input path and
cause before the row table is printed. `--dry-run` writes no project files.
Review every `Indeterminate` row before applying.

## Apply a supported route

```bash
python -P -m des.cli.update --apply --root /absolute/path/to/project
```

The runtime validates the full discovered batch before writing any migrated
artifact. It supports only registered artifact and workflow transition routes;
it refuses unknown shapes instead of guessing a conversion. Completed
expectation charters are preserved. A successful rerun has no further
migration for already current artifacts.

If the command refuses a project, read the path and cause in its error. Repair
a malformed input or select a runtime with an explicit transition for that
artifact. Keep a separate copy of the project before an update when you need
recovery from a filesystem failure during writes; the command does not offer a
broad rollback operation.

The older `workflow.mode: classic` to `atdd_pure` instructions that once
appeared here described a staged cutover and named CLI modules that are not
present in this tree. Do not use those commands for current projects.
