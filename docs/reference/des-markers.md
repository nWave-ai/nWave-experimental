# DES Markers Reference

Task prompts dispatched through the DES orchestrator embed HTML-comment
markers that carry execution context. Hooks (`pre_tool_use`,
`subagent_stop`, `deliver_progress`) parse them via
`des.domain.des_marker_parser.DesMarkerParser` to validate, route, and
audit each Task invocation.

## Syntax

```
<!-- DES-{NAME} : {VALUE} -->
```

Whitespace around the colon and inside the comment is tolerated; values
must be single tokens (no spaces).

## Markers

### `DES-VALIDATION`

| Value | Semantics |
|---|---|
| `required` | Prompt is a DES Task; hooks MUST enforce validation gates |

Absent marker: prompt bypasses DES (non-DES agent passthrough).

### `DES-MODE`

| Value | Semantics |
|---|---|
| `orchestrator` | Caller is the DES orchestrator (allowed to write `execution-log.json`) |

Absent marker: caller is a sub-agent (execution-log writes restricted).

### `DES-PROJECT-ID`

Feature identifier. Required when `DES-VALIDATION=required`. Value: kebab-case
slug matching the `docs/feature/<id>/` directory name.

Example: `<!-- DES-PROJECT-ID : fix-des-worktree-project-root-marker -->`

### `DES-STEP-ID`

Roadmap step identifier. Required when `DES-VALIDATION=required`. Format:
`<phase>-<step>` (e.g. `01-01`, `03-04`). Matches `phases[].steps[].id` in
`roadmap.json`.

### `DES-PROJECT-ROOT` *(added 2026-05-19, Rex RCA F-DES-WORKTREE-EXECUTION-LOG-RESOLUTION)*

Absolute path to the worktree-rooted project directory.

**Purpose**: declare the executing worktree's filesystem root so hook
resolvers find the correct `execution-log.json` when the orchestrator's
startup CWD differs from the worktree where the crafter runs (e.g.
multi-feature parallel dispatch from a long-running orchestrator).

**Validation** (applied by
`des.adapters.drivers.hooks.project_root_validator.validate_project_root`):

1. Value MUST be an absolute path (rejects relative / `~` / unset).
2. Path MUST exist on disk.
3. Path MUST be a git work tree (`git rev-parse --git-common-dir` succeeds).
4. Path MUST share `git-common-dir` with the hook's fallback CWD — i.e.
   belong to the same repository (direct same-repo or sibling worktree of
   the same `.git/`). Prevents path-injection redirecting validation to an
   unrelated repo.

**Resolution priority** (hook handlers `subagent_stop_handler` +
`deliver_progress_handler`):

```
validated DES-PROJECT-ROOT marker  >  hook_input["cwd"]  (fallback)
```

Invalid / absent marker degrades to the previous cwd-only behaviour. The
hook does NOT block on an invalid marker; it logs and falls back.

**Audit trail**: `subagent_stop_handler` emits a `HOOK_INVOKED` event with
handler `subagent_stop_resolved` carrying the resolved
`execution_log_path` and the raw `des_project_root_marker` value (whether
honored or rejected). Post-hoc analysis can trace why a particular
execution-log was chosen.

**Example**:

```
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : fix-des-worktree-project-root-marker -->
<!-- DES-STEP-ID : 01-01 -->
<!-- DES-PROJECT-ROOT : /home/alex/worktrees/fix-des-worktree -->
```

**Producer** (since 2026-07-28): `des dispatch --repo-root <path>` emits this
marker, resolving `<path>` to an absolute path with `Path.resolve()` — the same
`resolve()` the hook-side validator applies, so generator and consumer agree by
construction rather than by coincidence. Before that fix the CLI echoed a relative
`--repo-root` verbatim and the refusal (`declared-project-root-not-absolute`)
only fired downstream, at dispatch time, after the whole prompt had been
assembled.

### `DES-SWARM-ISOLATED-DISPATCH` *(added 2026-07-28)*

Declares that this dispatch runs in an ISOLATED parallel worktree, which DEFERS
the carpaccio slice-order check to integration time. Needed because a swarm
worktree's local ledger carries no `SliceCommitVerified` record for predecessor
slices — those live on trunk — so the order check would otherwise refuse a
legitimately-ready slice.

**Value**: free text naming which worktree this is, and which predecessor
`SliceCommitVerified` record lands at integration.

**Producer**: `des dispatch --swarm-isolated --swarm-justification '<text>'`.
Both flags are required together; either one alone is refused at exit 2 at the
authoring surface. A bare `--swarm-isolated` would emit a marker the hook cannot
read, and the order check would then block naming the PREDECESSOR's missing
ledger record instead of the malformed declaration — a rejection pointing at the
wrong thing. A lone `--swarm-justification` would be silently dropped.

**Consumer**: `carpaccio_intercept.py`, parsed by `des_marker_parser.py`.

The isolation is a DECLARED fact, never inferred: the CLI does not sniff whether
`.git` is a file or a directory, nor inspect the shape of the cwd. A gate decides
on declared facts, never on inferred signals.

```
<!-- DES-SWARM-ISOLATED-DISPATCH : wt/df-slice-05; predecessor slice-04's SliceCommitVerified lands at integration -->
```

## Empirical anchor

Rex RCA 2026-05-19 (feature `fix-des-worktree-project-root-marker`,
wave-decisions record) — audit-2026-05-19.log:270,365 showed
false-positive validation halts where the orchestrator running on master
dispatched a crafter on a worktree; the stop hook read `execution-log`
from master's `docs/feature/...` rather than the worktree's, then
blocked on a non-existent log.
