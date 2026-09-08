# DES Markers Reference

Task prompts dispatched through the DES orchestrator embed HTML-comment
markers that carry execution context. Hooks (`pre_tool_use`,
`subagent_stop`, `deliver_progress`) parse them via
`des.domain.des_marker_parser.DesMarkerParser` to validate, route, and
audit each Task invocation.

**Status (2026-09-06).** Every producer named on this page is `des dispatch`,
the composed run. ADR-DES-003 section 11 retires that command as an
orchestrator: the steps an orchestrating LLM invokes one at a time replace it.
The markers, the parser and the hooks that read them are unchanged. Which step
emits each marker is owed, and is recorded here when the composer is removed.

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

**Producer**: NONE in the current runtime. From 2026-07-28 until the retirement
of `des dispatch`, the producer was `des dispatch --repo-root <path>`, which
resolved `<path>` to an absolute path with `Path.resolve()` — the same
`resolve()` the hook-side validator applies, so generator and consumer agreed by
construction rather than by coincidence. That command no longer exists and no
surviving step emits this marker; a replacement producer is not named here
because none has been authored.

The CONSUMER is unretired: `project_root_validator.py` still reads and refuses
declared values, so a marker written by hand or by any future producer is still
honored under the rules above.

### `DES-SWARM-ISOLATED-DISPATCH` *(added 2026-07-28)*

Declares that this dispatch runs in an ISOLATED parallel worktree, which DEFERS
the carpaccio slice-order check to integration time. Needed because a swarm
worktree's local ledger carries no `SliceCommitVerified` record for predecessor
slices — those live on trunk — so the order check would otherwise refuse a
legitimately-ready slice.

**Value**: free text naming which worktree this is, and which predecessor
`SliceCommitVerified` record lands at integration.

**Status**: RETIRED — historical marker, with no live producer and no live
consumer. Its producer was `des dispatch --swarm-isolated
--swarm-justification '<text>'` (both flags required together, either one alone
refused at exit 2 at the authoring surface), and its consumer was
`carpaccio_intercept.py` via `des_marker_parser.py`. Neither module is present
in the current runtime, so this section is kept as a record of what the
declaration meant, not as a surface anything can use today. No replacement
exists; do not treat any current step as emitting it.

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
