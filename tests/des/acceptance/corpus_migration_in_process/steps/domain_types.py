"""Domain types for the f-test-corpus-migration-in-process slice-01 enabler ATs.

SSOT-via-types (Mandate-12 criterion 1): the closed observables each piece pins
are typed value objects, so the step bodies are typed lookups + a composition
call (criterion 3) and carry no inline logic.

This module imports NO not-yet-created production name -- it is pure value-object
declaration, collection-safe at HEAD (DESIGN P1). The per-site production seams
(the per-spawn-site classifier, the scorecard --per-site mode, the scope-aware
gate, the recipe-conformance surface, the @requires_external skip resolver) are
all reached at RUNTIME inside the in-process call, never imported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PerSiteVerdict(str, Enum):
    """The per-site classifier's total-function verdict over an arbitrary corpus.

    The classifier must total over the open corpus (component-manifest C6): a
    recognized parseable file is classified per-site; an unrecognized language is
    NOT_APPLICABLE (no false flag); an unparseable file is INDETERMINATE (recorded,
    never silently dropped). Never a crash, never a silent pass.
    """

    RECOGNIZED = "recognized"
    # Degrade-LOUD: the language is one the per-language detector does not know
    # -> NOT_APPLICABLE with a loud reason, never a false flag (DDD-1 / C6).
    NOT_APPLICABLE = "not-applicable"
    # Degrade-LOUD: the file did not parse -> INDETERMINATE, recorded, never a
    # silent drop (port-invariant: scan_spawn_sites never silently drops a file).
    INDETERMINATE = "indeterminate"


# The two per-site decisions a spawn-site resolves to (ADR-TEST-003).
KEEP = "keep"  # enclosing scenario carries @walking_skeleton -> legitimate e2e.
MIGRATE = "migrate"  # enclosing scenario is non-WS -> the migration target.


@dataclass(frozen=True)
class PerSiteClassification:
    """The per-spawn-site classification observable a ``Then`` asserts on.

    Every field is a port-exposed observable derived from driving the REAL
    per-site classifier IN-PROCESS over a synthetic corpus -- never an internal
    struct field. The un-gameable contract (ADR-TEST-003): a spawn-site is KEEP
    iff its ENCLOSING SCENARIO carries @walking_skeleton, else MIGRATE -- decided
    per-site, NOT per-file (closing the 45-mixed-file / 155-fork blind spot).

    * ``migrate_sites`` -- spawn-site locations (``file:line``) the classifier
      decided MIGRATE (a non-@walking_skeleton enclosing scenario reaches the fork).
    * ``keep_sites`` -- spawn-site locations decided KEEP (the enclosing scenario
      carries @walking_skeleton -- the legitimate subprocess-e2e survivor).
    * ``verdict`` -- the total-function verdict (RECOGNIZED / NOT_APPLICABLE /
      INDETERMINATE) -- degrade-LOUD, never a crash, never a silent pass.
    * ``not_applicable_reason`` -- the loud reason an unrecognized language cleared
      as NOT_APPLICABLE (never a false flag).
    * ``indeterminate_sites`` -- files the per-site pass could not parse (recorded,
      never silently dropped).
    * ``resolution_available`` -- True iff the classifier surfaced a per-SITE
      resolution at all (False at HEAD: only the file-level short-circuit exists,
      so no per-site classification surface is produced -> the named RED).
    * ``recipe_conformant`` -- True iff a migrated exemplar is recipe-conformant
      (zero non-WS forks AND drives the production EDGE, DDD-2).
    * ``drives_edge`` -- True iff the migrated exemplar drives the production EDGE
      (a wired symbol), not an isolated leaf (the C13/C14 anti-theater check).
    * ``zombies_preserved`` -- True iff the migrated exemplar's sad-path (@error)
      scenario survived the migration 1:1 (DDD-2 step 6, ZOMBIES preservation).
    """

    migrate_sites: tuple[str, ...] = ()
    keep_sites: tuple[str, ...] = ()
    verdict: PerSiteVerdict = PerSiteVerdict.RECOGNIZED
    not_applicable_reason: str = ""
    indeterminate_sites: tuple[str, ...] = ()
    resolution_available: bool = False
    recipe_conformant: bool = False
    drives_edge: bool = False
    zombies_preserved: bool = False
    forked_interpreter: bool = False
    git_invoked: bool = False
    diagnostic: str = ""


@dataclass(frozen=True)
class ScopedGateOutcome:
    """The scope-follows-migration gate observable (DDD-4 ordering caveat).

    Tightening ``check_non_ws_spawn`` to per-site flags the 155 mixed-file spawns
    immediately; the gate's BLOCKING SCOPE must therefore follow the migrated
    directories (tighten per batch, AFTER that directory is migrated), never
    before -- else the live readiness gate hard-fails on un-migrated corpus.

    * ``flags_in_migrated_dir`` -- True iff a non-WS fork in a MIGRATED directory
      (per-site scope active) is FLAGGED.
    * ``hard_fails_unmigrated_dir`` -- True iff a non-WS fork in an UN-MIGRATED
      directory is FLAGGED (the regression the ordering caveat forbids -- it must
      be False: the un-migrated corpus is not hard-failed).
    * ``scope_honoured`` -- True iff the gate exposed a migration-scope surface at
      all (False at HEAD: the gate scans the whole tree file-level, no scope ->
      the named RED).
    """

    flags_in_migrated_dir: bool = False
    hard_fails_unmigrated_dir: bool = True
    scope_honoured: bool = False
    forked_interpreter: bool = False
    git_invoked: bool = False
    diagnostic: str = ""


@dataclass(frozen=True)
class ScorecardObservable:
    """The migration-scorecard observable (DDD-5), driven via ``main(argv)``.

    The scorecard plays two roles: file-level mode = the cheap gradient tracker
    (exists today); ``--per-site`` mode = the un-gameable DONE contract counting
    non-WS spawn-sites PER-SCENARIO (350 -> 0). Driven IN-PROCESS via ``main(argv)``
    with stdout captured (the content facet); ONE @walking_skeleton subprocess
    scenario proves the installed script is wired (the terminal-wiring facet).

    Resolves OPEN QUESTION 4 (the --per-site JSON output contract): the pinned
    fields below ARE the contract the per-batch gate consumes.

    * ``per_site_mode_available`` -- True iff ``--per-site`` is a recognized flag
      on ``main(argv)`` (False at HEAD: the flag + the ``main(argv)`` entry are
      absent -> argparse/TypeError inside the call -> the named RED).
    * ``per_site_non_ws_count`` -- the per-scenario non-WS spawn-site count (the
      DONE contract number; 350 today, 0 at DONE). ``None`` when the field is
      absent from the JSON.
    * ``by_scenario`` -- per-scenario records {file, scenario, tags, spawn_line,
      decision}; the un-gameable proof the mixed-file forks are counted.
    * ``by_dir`` -- per-directory non-WS spawn-site counts (the migration heat-map,
      drained per batch -- DDD-3 batching consumes this).
    * ``done`` -- True iff ``per_site_non_ws_count == 0`` (phase DONE).
    * ``file_level_mode_works`` -- True iff the file-level gradient tracker still
      emits its pure/mixed split (the cheap tracker must survive the extension).
    * ``json_fields`` -- the top-level JSON keys emitted (the contract surface a
      ``Then`` asserts the pinned fields are present in).
    """

    per_site_mode_available: bool = False
    per_site_non_ws_count: int | None = None
    by_scenario: tuple[dict, ...] = ()
    by_dir: dict = field(default_factory=dict)
    done: bool = False
    file_level_mode_works: bool = False
    json_fields: tuple[str, ...] = ()
    forked_interpreter: bool = False
    exit_code: int = 0
    captured_output: str = ""
    diagnostic: str = ""


@dataclass(frozen=True)
class WsWiringOutcome:
    """The @walking_skeleton subprocess wiring observable (the ONE legit fork).

    The single subprocess-e2e scenario per command: it proves the INSTALLED
    scorecard script reaches a real terminal with the NEW ``--per-site`` mode wired
    (the terminal-wiring facet the in-process content scenarios cannot prove).

    * ``script_wired`` -- True iff the real script exits 0 under ``--per-site
      --json`` and emits the per-site contract JSON (False at HEAD: ``--per-site``
      is unknown -> exit 2 -> the named RED).
    * ``exit_code`` -- the real subprocess exit code.
    * ``emitted_per_site_json`` -- True iff the captured stdout carried the
      ``per_site_non_ws_count`` contract field.
    """

    script_wired: bool = False
    exit_code: int = 0
    emitted_per_site_json: bool = False
    captured_output: str = ""
    diagnostic: str = ""


@dataclass(frozen=True)
class RequiresExternalSkipDecision:
    """The @requires_external degrade-LOUD-SKIP observable (DDD-6, resolves Q2).

    A @walking_skeleton @requires_external build scenario must degrade-LOUD-SKIP in
    a build-incapable sandbox: NEVER silent-pass (it is not minted GREEN), NEVER a
    hard block (it is a skip, not a failure), ALWAYS a loud structured reason. This
    resolves OPEN QUESTION 2 (the exact loud marker + skip-reason string).

    * ``skipped`` -- True iff the scenario was SKIPPED (not failed, not silent-pass).
    * ``loud_reason`` -- the structured, grep-able skip-reason string surfaced to
      the sandbox (must be non-empty and name the missing capability).
    * ``silent_pass`` -- True iff the scenario was silently passed (FORBIDDEN: must
      be False).
    * ``hard_blocked`` -- True iff the scenario hard-failed/blocked (FORBIDDEN in a
      build-incapable sandbox: must be False).
    * ``resolver_available`` -- True iff a degrade-LOUD-skip resolver exists at all
      (False at HEAD: no @requires_external skip mechanism -> the named RED).
    """

    skipped: bool = False
    loud_reason: str = ""
    silent_pass: bool = False
    hard_blocked: bool = False
    resolver_available: bool = False
    diagnostic: str = ""
