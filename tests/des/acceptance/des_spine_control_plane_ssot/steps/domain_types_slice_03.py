"""Domain types for des-spine-control-plane-ssot slice-03 (mode-resolution SSOT).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-03 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-03 SUT = the spine's two mode-reading driving ports — the
`des verify-integrity` CLI (the verify role) and the `des init-log` CLI (the
DELIVER-dispatch role). The slice-03 BEHAVIOR is the mode-resolution SSOT
consolidation (DDD-5/6/7): ONE `resolve_workflow_mode` with ONE absent-key
default (`atdd_pure`, DDD-7), replacing the two-resolver / two-opposite-default
divergence that IS #65.

The disease (grep-evidenced, witnessed at DISTILL HEAD):

  * `workflow_mode._resolve_workflow_mode` (`:92`): absent config -> `classic`.
    Consumed by `verify_deliver_integrity.py:539` (#65), `init_log.py:135`,
    `session_start_handler.py:229`.
  * `init_log.resolve_dispatch_mode` (`:63`, via `_read_workflow_mode:104`):
    absent config -> `atdd_pure`. The DELIVER-dispatch resolver.

So on an UNCONFIGURED project the DELIVER dispatch resolves `atdd_pure` while
verify-integrity resolves `classic` -> verify hunts for a `roadmap.json` the
atdd_pure spine never created and refuses exit 2 (#65). After consolidation both
ports resolve the SAME answer (`atdd_pure`), so verify never hunts for the
phantom roadmap and init-log refuses-as-atdd_pure (roadmap-free) consistently.

DDD-7 (the canonical absent-key default) is decided ONCE upstream — DESIGN
Decisions Table DDD-7, DISCUSS US-3, Outcome KPI-3 ALL name `atdd_pure`. The AT
does not re-litigate it; it pins it as the observable contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# The exact substring the #65 refusal prints when verify-integrity mis-resolves
# the mode to classic on an atdd_pure project and hunts for a roadmap.json that
# the roadmap-free atdd_pure spine never wrote (verify_deliver_integrity.py:543,
# `Error: roadmap.json not found at ...`). The AT asserts this phantom-roadmap
# refusal is ABSENT post-consolidation (the #65-dissolution observable).
ROADMAP_NOT_FOUND_MARKER = "roadmap.json not found"


class ModeConfig(str, Enum):
    """How the project's `.nwave/config.yaml` declares (or omits) `workflow.mode`.

    UNCONFIGURED is the #65 trigger: NO `.nwave/config.yaml` at all. The absent
    key forces the absent-key default — the precise point the two legacy
    resolvers disagreed (DELIVER-dispatch -> atdd_pure, verify -> classic). The
    SSOT cure makes ONE answer (`atdd_pure`, DDD-7) for this case at EVERY port.

    EXPLICIT_ATDD_PURE / EXPLICIT_CLASSIC carry a written `workflow.mode`. The
    explicit cases are honoured byte-for-byte by both legacy and consolidated
    resolvers — only the absent case changes. EXPLICIT_CLASSIC additionally
    surfaces the `ClassicSpineDeprecated` advisory (init_log.resolve_dispatch_mode).

    The `.value` strings are the human-readable Gherkin phrases the step
    decorators parse (DSL emergence over a typed enum — Mandate-12).
    """

    UNCONFIGURED = "project with no workflow mode configured"
    EXPLICIT_ATDD_PURE = "project explicitly configured for the atdd_pure spine"
    EXPLICIT_CLASSIC = "project explicitly configured for the classic spine"


class ResolvedMode(str, Enum):
    """The mode a driving port resolves for the project — the answer under test.

    A closed 2-member set mirroring the `WorkflowMode` VO (DDD-6). The slice-03
    invariant is that EVERY mode-reading driving port resolves the SAME member
    for the SAME project state (referential transparency, Context-B invariant).
    """

    ATDD_PURE = "atdd_pure"
    CLASSIC = "classic"


class VerifyOutcome(str, Enum):
    """How `des verify-integrity` resolves on the project — EXIT-CODE-EXACT.

    The #65-dissolution observable (AT-01) lives here. On an UNCONFIGURED
    atdd_pure project the verifier must NOT mis-resolve to classic and hunt for
    a roadmap.json (the legacy exit-2 `roadmap.json not found`); it must resolve
    atdd_pure and check the atdd_pure artifacts that actually exist.

    * RESOLVED_ATDD_PURE — the verifier took the atdd_pure branch
      (`_verify_atdd_pure`): a missing roadmap.json is NEVER exit 2 here. The
      verdict reflects the atdd_pure artifacts (the AT-completion ledger): exit 0
      when the ledger + feature-end cycle are present, exit 1 on an
      atdd_pure-shaped integrity violation. Either way the `roadmap.json not
      found` phantom-refusal is ABSENT. This is the #65-dissolved state.
    * PHANTOM_ROADMAP_REFUSAL — the #65 bug: exit 2 with `roadmap.json not
      found`, the verifier mis-resolved the mode to classic and hunted for a
      file the active mode never wrote. The RED slice-03 AT-01 targets.
    * UNEXPECTED — any other shape, so a verdict never passes for the wrong reason.
    """

    RESOLVED_ATDD_PURE = "resolved atdd_pure (no phantom roadmap hunt)"
    PHANTOM_ROADMAP_REFUSAL = "exit 2 roadmap.json-not-found (#65)"
    UNEXPECTED = "unexpected"


class DispatchOutcome(str, Enum):
    """How `des init-log` (the DELIVER-dispatch port) resolves the mode — observable.

    init-log is the DELIVER-side mode-reading driving port. Its OBSERVABLE mode
    answer is its refusal behaviour:

    * REFUSED_ATDD_PURE — init-log resolved atdd_pure: the spine is roadmap-free
      and execution-log-free, so init-log REFUSES to create a log (exit 1,
      "workflow.mode is atdd_pure"). This is the atdd_pure mode answer made
      observable at the DELIVER port.
    * CREATED_LOG_CLASSIC — init-log resolved classic: it created an
      execution-log.json (exit 0). The roadmap-based classic mode answer.
    * UNEXPECTED — any other shape.

    AT-02 (default consistency) pairs THIS port's answer with verify-integrity's
    answer on the SAME unconfigured project: post-SSOT both must resolve
    atdd_pure (init-log REFUSED_ATDD_PURE, verify RESOLVED_ATDD_PURE). Today they
    DIVERGE — init-log:135 uses the classic-defaulting `_resolve_workflow_mode`
    and CREATES a log, while the DELIVER-dispatch `resolve_dispatch_mode` says
    atdd_pure: a fourth representation of the same split concept.
    """

    REFUSED_ATDD_PURE = "refused: atdd_pure spine is roadmap-free"
    CREATED_LOG_CLASSIC = "created an execution-log (classic spine)"
    UNEXPECTED = "unexpected"


# --- Frozen probe / outcome dataclasses ----------------------------------


@dataclass(frozen=True)
class ProjectProbe:
    """A handle on a synthetic project the operator runs the spine ports against.

    Wraps a tmp_path-scoped project directory. `mode_config` records how the
    project declares (or omits) `workflow.mode` — the seam the consolidated
    resolver reads and the slice-03 SSOT cure makes one answer across. For the
    atdd_pure-shaped verify path the project also carries a minimal AT-completion
    ledger (the artifact the atdd_pure spine actually wrote), so the
    #65-dissolution is observed end-to-end (verify checks the ledger, not a
    phantom roadmap).
    """

    project_dir: str  # the directory the CLI ports point at
    deliver_dir: str  # {project_dir}/docs/feature/{id}/deliver — the verify target
    mode_config: ModeConfig


@dataclass(frozen=True)
class VerifyRun:
    """Observable outcome of one `des verify-integrity` fire.

    Universe entries `assert_state_delta` tracks are built from THIS dataclass's
    port-exposed fields: `exit_code`, `outcome`, `roadmap_hunt`. Internal
    plumbing (Popen handle, env dict, raw stream bytes) is NEVER in the universe
    (Mandate 8 — port-exposed observables only).
    """

    exit_code: int
    stdout: str
    stderr: str
    outcome: VerifyOutcome
    roadmap_hunt: bool  # True iff the `roadmap.json not found` phantom-refusal printed


@dataclass(frozen=True)
class DispatchRun:
    """Observable outcome of one `des init-log` (DELIVER-dispatch port) fire."""

    exit_code: int
    stdout: str
    stderr: str
    outcome: DispatchOutcome


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

MODE_CONFIG_BY_PHRASE: dict[str, ModeConfig] = {m.value: m for m in ModeConfig}


__all__ = [
    "MODE_CONFIG_BY_PHRASE",
    "ROADMAP_NOT_FOUND_MARKER",
    "DispatchOutcome",
    "DispatchRun",
    "ModeConfig",
    "ProjectProbe",
    "ResolvedMode",
    "VerifyOutcome",
    "VerifyRun",
]
