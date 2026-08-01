# @feature-gate-armed-state-derivation
# @slice-02
# @slice-03
# @slice-04
# @slice-05
# @slice-06
"""Acceptance tests -- `des verify-gate-armed-state` (DISTILL, slice-02 + slice-03 + slice-04 + slice-05 + slice-06).

@contract-shape:bounded-change

Charter: docs/product/expectations/gate-armed-state-derivation/
         a-maintainer-running-des-verify-gate-armed-state-gets-a-real-catalogued-operator-invokable-cli.md
Feature-delta: docs/feature/gate-armed-state-derivation/feature-delta.md
Design brief: docs/feature/gate-armed-state-derivation/design/brief.md

SCOPE FENCE (slice-02): a PURE MOVE + wiring of the already-GREEN
`coherence_offenders` reducer (today living inside
tests/build/f_nonbypassable_attestation/test_arch_catalog_gate_wiring.py)
into a first-class, catalogued, operator-invokable `des` CLI gate mirroring
`src/des/cli/verify_catalog_coherence.py`'s shape -- ZERO verdict-logic
change. This file therefore does NOT re-derive every offender/dormant/
empty-catalog branch the 6 existing regression ATs already pin (Test
Reuse & Consolidation Analysis: "CONSOLIDATE ... zero duplication with the 6
existing coherence_offenders fixtures"); it proves the CLI-CONTRACT layer
those 6 ATs cannot: real subcommand registration, argparse `--repo-root`,
JSON verdict shape, degrade-LOUD outside a checkout, catalog/registry
self-coherence, and stdlib-only-ness (F-D-09).

SCOPE FENCE (slice-03, THE LOAD-BEARING SLICE, decision #1): demotes
`host_visibility` self-declaration to CLI-existence-only metadata (never
sufficient wiring proof by itself) and introduces the 4-tier verdict --
ARMED / ARMED-PROSE / DORMANT / INDETERMINATE -- replacing today's binary
WIRED/DORMANT. ARMED-PROSE and INDETERMINATE are authored here as REACHABLE
verdict states with INJECTABLE inputs (`ArmedStateInputs.prose_text`,
`ArmedStateInputs.registered_cli_verbs`); the real agent/skill/task prose
scanner is slice-06's job, the per-wave dispatch table is slice-04's, the
pre-commit/CI/2-hop indirection resolver is slice-05's, and the reviewed
baseline-diff (which turns a NEW unreviewed indeterminate gate into a hard
exit-1 refusal) is slice-07's -- none of those readers or the baseline are
built here. Per the feature-delta's own CLI contract
(`## Wave: DESIGN / [REF] Architecture & Contract Tests`): "Success (exit
0): every catalogued gate resolves to one of the four tiers; every
INDETERMINATE gate is ... reported as a NEW INDETERMINATE (a WARNING
annotation, not a hard failure, ... until slice-07 lands it as fail-closed)"
-- so at THIS slice, an INDETERMINATE population is visible in the JSON
verdict and still exits 0; only a structurally-unreadable input (malformed
catalog, missing `nWave/gates/` dir) exits non-zero.

REGRESSION OBLIGATION (dispatch envelope): the trust-policy change
legitimately flips the verdict of any existing fixture whose ONLY wiring
evidence was `host_visibility` self-declaration alone. Full (a)/(b) decision
table, per existing AT:
  (a) UNCHANGED (evidence was a real independent surface, or unrelated to
      trust policy): `test_walking_skeleton_...` (1), `test_main_excuses_a_
      gate_carrying_a_non_empty_dormant_rationale` (4),
      `test_main_does_not_silently_pass_on_a_malformed_catalog` (6),
      `test_main_degrades_loud_when_repo_root_has_no_gate_catalog_at_all`
      (7), `test_gate_is_registered_in_the_real_cli_registry` (9),
      `test_gate_has_a_catalog_row_in_the_real_gate_catalog` (10),
      `test_gate_has_a_per_gate_contract_file` (11),
      `test_promoted_module_is_resolvable_as_a_production_symbol` (12),
      `test_promoted_module_source_contains_no_yaml_import` (13).
  (b) RE-BASELINED (evidence WAS `host_visibility` self-declaration alone,
      or the real-catalog parity claim the 33/78 self-declaration-only
      population breaks): originally `test_main_reports_a_coherent_verdict_
      on_a_wired_synthetic_repo` (2, retargeted at a genuine CODE hit so it
      keeps proving the ARMED/exit-0 happy path honestly), `test_main_names_
      the_unwired_non_dormant_gate_and_exits_non_zero` (3, renamed --
      `host_visibility`-only no longer escapes to "not flagged", exit code
      is now 0 not != 0 pre-baseline), `test_main_never_excuses_an_empty_
      dormant_rationale` (5, renamed -- the dormant rule is unchanged but
      the not-excused gate now falls to `indeterminate` with exit 0, not
      `!= 0`), `test_new_cli_agrees_with_todays_known_coherent_live_catalog_
      verdict` (8, renamed -- the real-catalog parity claim of zero
      offenders is exactly what decision #1 breaks). Each re-baselined test
      keeps its docstring's WHY inline; none is silently relaxed -- each
      still proves the reducer distinguishes tiers correctly, only the
      EXPECTED tier / exit code changed.

SCOPE FENCE (slice-04, decision #2): DISTILL's own gate-out stack IS
declared as DATA in `nWave/waves/distill.yaml` (`gate_stack.gate-out`,
including an `on_failure: block` row, `check-slice-at-completeness`) but NO
live invoker dispatches that stack -- `"distill"` is absent from
`_REVIEW_GATE_OUT_WAVES` (`src/des/application/subagent_stop_service.py:56`,
own module-level DISCOVERY comment: adding it would activate the WHOLE
stack including the block-on-failure row, hard-blocking every DISTILL
return). DISCUSS/DESIGN/DEVOPS are the opposite case: each IS a member of
`_REVIEW_GATE_OUT_WAVES` and its declared gate-out rows really do dispatch
live with veto power. A uniform "waves/* declares gate-out => armed" rule
is therefore FALSE -- it would grant the exact same credit to a merely-
declared, never-dispatched DISTILL row as to a genuinely veto-dispatched
DISCUSS/DESIGN/DEVOPS row. This slice adds: (1) a small REVIEWED per-wave
dispatch-class table, `WAVE_DISPATCH_CLASS: dict[str, str]` --
`{"discuss": "registry-veto", "design": "registry-veto", "devops":
"registry-veto", "distill": "registry-advisory", "deliver":
"no-gate-out-stack"}`; (2) a stdlib-only wave-yaml gate-out reader,
`_wave_gate_out_gate_ids(repo_root, wave) -> frozenset[str]`, parsing
`nWave/waves/<wave>.yaml`'s `gate_stack: gate-out:` block for its declared
`gate_id` entries (mirroring `_parse_gate_host_visibility`'s stdlib-regex
shape); (3) a cross-check function, `wave_dispatch_class_divergences
(review_gate_out_waves: frozenset[str]) -> list[str]`, so the reviewed table
and the LIVE `_REVIEW_GATE_OUT_WAVES` set can never silently diverge; (4) a
new `ArmedStateInputs.wave_gate_out_hits: dict[str, frozenset[str]]` field
(wave name -> the gate_ids that wave's `_wave_gate_out_gate_ids` reader
found, injectable so the reducer is drivable synthetically); (5)
`gate_armed_states` extended so a gate_id present under a
`WAVE_DISPATCH_CLASS == "registry-veto"` wave's hits is a genuine
independent CODE hit (-> `"armed"`), while the SAME shape of evidence under
a `"registry-advisory"` wave's hits grants NO such credit (falls through to
prose/dormant/indeterminate exactly as before). Out of scope here: the
pre-commit/CI/2-hop indirection resolver (slice-05) and the real agent/
skill/task prose scanner (slice-06) -- unaffected by this slice.

SCOPE FENCE (slice-05, decision #3): a naive flat concatenation of
`.pre-commit-config.yaml` text (the existing `_firing_surface_text` shape)
would report `run-slice-ats` as unwired, because `.pre-commit-config.yaml`
only names the WRAPPER SCRIPT file (`entry: python3 scripts/hooks/
run_slice_ats_precommit.py`) -- the gate_id literal `"run-slice-ats"` lives
one hop further in, inside that wrapper's own `subprocess.run([..., "des",
"run-slice-ats", ...])` call (measurement §4, confirmed real). `des
declare-done`'s pre-push wrapper (`scripts/hooks/
run_des_declare_done_pre_push.py`) is dispatched via a THIRD, incompatible
pattern: `importlib.util.spec_from_file_location` loading a script from a
home-directory-relative path (`~/.claude/scripts/...`) -- a path OUTSIDE the
repo tree entirely, genuinely target-machine-dependent. Decision #3's policy: cap
indirection-following at hops where EVERY hop is a static file and the
terminal token is a literal argv element (regex-matched, no interpolation);
the moment a hop requires a real interpreter or resolves outside the repo
tree, the resolver refuses to chase further -- that gate falls through to
`"indeterminate"` (never chased, never fabricated as armed, never a hard
NOT-ARMED -- decision #4, no such tier exists yet). This slice adds: (1) a
stdlib-only 2-hop pre-commit/CI indirection reader,
`_precommit_ci_indirection_gate_ids(repo_root: Path) -> frozenset[str]`,
that reads `.pre-commit-config.yaml` for an `entry:` line naming an in-repo
wrapper script, reads THAT script's own text as DATA (never imports or
executes it), and returns the gate_ids it finds as a literal, non-
interpolated element of a `subprocess.run([...])` call -- a wrapper whose
own body dispatches dynamically (an `importlib.util.spec_from_file_location`
call) to a path outside `repo_root` contributes NOTHING to the returned set
for that gate, by construction, rather than raising or guessing; (2) a new
`ArmedStateInputs.precommit_ci_indirection_hits: frozenset[str]` field
(gate_ids the reader resolved as a genuine independent CODE hit, injectable
so the reducer is drivable synthetically); (3) `gate_armed_states` extended
so a gate_id present in `precommit_ci_indirection_hits` is a genuine
independent CODE hit (-> `"armed"`), exactly as `veto_wave_gate_ids`
already grants. Out of scope here: the real agent/skill/task prose scanner
(slice-06) and the reviewed INDETERMINATE baseline-diff (slice-07) --
unaffected by this slice.

SCOPE FENCE (slice-06): `ArmedStateInputs.prose_text` already exists
(slice-03) as a REACHABLE, injectable field, but NOTHING populates it from
the real repo tree -- `_gate_states_for_repo` (the real CLI's wiring
function) passes only `firing_text` to `gate_armed_states`, so no real gate
can ever resolve `"armed-prose"` through `des verify-gate-armed-state`
itself, only through a synthetic test fixture (as slice-03's own
`test_a_gate_with_only_prose_evidence_resolves_the_distinct_armed_prose_
tier` proves). This slice adds the missing REAL reader: a stdlib-only
(F-D-09, no PyYAML) `_prose_surface_text(repo_root: Path) -> str` that
concatenates the text of every file matching `nWave/agents/*.md`,
`nWave/skills/*/SKILL.md`, and `nWave/tasks/nw/*.md` under `repo_root`
(mirroring `_firing_surface_text`'s concatenation-and-search shape), wired
into `_gate_states_for_repo`'s `ArmedStateInputs(prose_text=
_prose_surface_text(repo_root), ...)` construction. `verify-red-green`
(brief §6 slice 6's own named example) is the real fixture: it self-declares
only `host_visibility: [cli]`, has ZERO code-surface hit (no flavor row, no
live-hook module reference), and IS genuinely mentioned across multiple real
agent/skill/task files (`nWave/agents/nw-acceptance-designer.md`,
`nWave/skills/nw-distill-red-scaffolding/SKILL.md`, `nWave/tasks/nw/
execute.md`, others) -- so it resolves `indeterminate` today and must
resolve `armed-prose` once this slice's reader lands and is wired. Two
correctness boundaries this slice's reader must also honour, both proven by
NEW negative ATs: (1) the reader is SCOPED to the three named surface
classes only -- a `des <verb>` mention living anywhere else in the repo
(README, docs, tests, ADRs) must NOT produce a false armed-prose hit, or
every gate whose name happens to appear in any prose anywhere would falsely
arm; (2) a CODE hit still takes absolute priority over a prose hit for the
SAME gate_id -- a gate reachable through BOTH a real flavor/live-hook
reference AND agent/skill/task prose must resolve `"armed"`, never
`"armed-prose"` (GDP-8 arity: the two tiers must never conflate). Out of
scope here: the pre-commit/CI/2-hop indirection resolver (slice-05, already
shipped independently) and the reviewed INDETERMINATE baseline-diff
(slice-07) -- unaffected by this slice.

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/cli/verify_gate_armed_state.py:main(argv: list[str] | None) -> int`
-- same CLI contract family as `verify_catalog_coherence.py` (`--repo-root`,
JSON verdict to stdout, degrade-LOUD, stdlib-only regex parsing, exit 0/
non-zero). Slice-03 additionally requires (RED at HEAD 4e2c07581):
`gate_armed_states(gates, *, inputs: ArmedStateInputs) -> dict[str, str]`
(per-gate tier in {"armed", "armed-prose", "dormant", "indeterminate"}); a
JSON verdict carrying FOUR distinct populations `armed` / `armed_prose` /
`dormant` / `indeterminate` (GDP-8 arity corollary -- INDETERMINATE must
reach the aggregate, never collapsed into ARMED); and `ArmedStateInputs`
growing two new fields, `prose_text: str = ""` and
`registered_cli_verbs: frozenset[str] = frozenset()`. Slice-04 additionally
requires (RED at slice-04's DISTILL dispatch): `WAVE_DISPATCH_CLASS`,
`wave_dispatch_class_divergences`, `_wave_gate_out_gate_ids`, and
`ArmedStateInputs.wave_gate_out_hits` -- see the SCOPE FENCE (slice-04)
paragraph above for the exact shapes. Slice-05 additionally requires (RED at
slice-05's DISTILL dispatch): `_precommit_ci_indirection_gate_ids` and
`ArmedStateInputs.precommit_ci_indirection_hits` -- see the SCOPE FENCE
(slice-05) paragraph above for the exact shapes. Slice-06 additionally
requires (RED at slice-06's DISTILL dispatch): `_prose_surface_text(repo_root:
Path) -> str`, plus its wiring into `_gate_states_for_repo` -- see the SCOPE
FENCE (slice-06) paragraph above for the exact shape and the two correctness
boundaries.

Active-RED scaffolding (P1-P4, `nw-distill-red-scaffolding`): the module is
absent today, so every in-process test hides its import inside a helper
called from the test body (hidden-import), never at module top -- collection
stays green (COLLECT >= 1) and the absence surfaces as a semantic
AssertionError (MISSING_FUNCTIONALITY), never a collection ImportError
(BROKEN). The one `@walking_skeleton` scenario drives the real CLI via
subprocess (`python -m des.cli verify-gate-armed-state ...`) -- today
`verify-gate-armed-state` is an unregistered subcommand, so argparse reports
"invalid choice" (a clean, non-crashing exit) rather than the JSON verdict
the assertions expect; that mismatch is the semantic RED, never a Python
traceback. Slice-03's NEW capability (`gate_armed_states`, the new
`ArmedStateInputs` fields) is guarded by its OWN presence-probe helpers
(`_import_gate_armed_states`, `_assert_armed_state_inputs_supports_
slice03_fields`) so a missing field/function surfaces as a NAMED
AssertionError, never a bare `TypeError: unexpected keyword argument`.
Slice-04's NEW capability (`WAVE_DISPATCH_CLASS`,
`wave_dispatch_class_divergences`, `_wave_gate_out_gate_ids`,
`ArmedStateInputs.wave_gate_out_hits`) is guarded the SAME way by its own
presence-probe helpers (`_import_wave_dispatch_class_table`,
`_import_wave_dispatch_class_divergences`,
`_import_wave_gate_out_gate_ids_reader`,
`_assert_armed_state_inputs_supports_slice04_field`). Slice-05's NEW
capability (`_precommit_ci_indirection_gate_ids`,
`ArmedStateInputs.precommit_ci_indirection_hits`) is guarded the SAME way by
its own presence-probe helpers (`_import_precommit_ci_indirection_reader`,
`_assert_armed_state_inputs_supports_slice05_field`). Slice-06's NEW
capability (`_prose_surface_text` + its wiring into `_gate_states_for_repo`)
is guarded the SAME way by its own presence-probe helper
(`_import_prose_surface_text_reader`) -- no new `ArmedStateInputs` field is
needed (`prose_text` already exists since slice-03), so no new
`_assert_armed_state_inputs_supports_*` helper is required either.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_PROMOTED_MODULE = "des.cli.verify_gate_armed_state"


# ---------------------------------------------------------------------------
# Hidden-import + hidden-find_spec helpers (P1 + P3): keep the absent module
# out of collection scope; the absence surfaces as a runtime AssertionError
# inside a test body, never a collection ImportError.
# ---------------------------------------------------------------------------


def _import_verify_gate_armed_state():
    """Presence-probe BEFORE import (P1+P3, hardened per review): asserts a
    NAMED, self-explaining failure via `find_spec` first, so the `from ...
    import main` statement below is only ever reached once the module is
    confirmed present -- the import itself can never be the thing that
    raises (never a bare `ModuleNotFoundError` with no WHAT/WHY/HOW)."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet. WHY: this AT drives the promoted CLI entrypoint, which "
            "this slice has not yet created. HOW: promote `coherence_offenders` "
            "(tests/build/f_nonbypassable_attestation/"
            "test_arch_catalog_gate_wiring.py) into this module, register it as "
            "the `verify-gate-armed-state` CLI verb "
            "(_SubcommandRow in src/des/cli/__main__.py), mirroring "
            "src/des/cli/verify_catalog_coherence.py's --repo-root/JSON/"
            "degrade-LOUD CLI contract, and implement "
            "`main(argv: list[str] | None = None) -> int`."
        )
    from des.cli.verify_gate_armed_state import main

    return main


def _find_promoted_module_spec():
    """`importlib.util.find_spec` -- resolves without ever importing the
    absent module, so a bare existence check never risks a collection-time
    ImportError even when called outside a hidden-import wrapper."""
    return importlib.util.find_spec(_PROMOTED_MODULE)


def _import_gate_armed_states():
    """Presence-probe (P1+P3) for slice-03's NEW per-gate tier classifier.
    The module itself exists since slice-02 -- what may be ABSENT is the
    `gate_armed_states` symbol on it. Guarding with `getattr(..., None)`
    (never a bare `from ... import gate_armed_states`) means the absence
    surfaces as a NAMED AssertionError, never an ImportError at collection
    or call time."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet (slice-02 must land first)."
        )
    import importlib as _importlib

    module = _importlib.import_module(_PROMOTED_MODULE)
    fn = getattr(module, "gate_armed_states", None)
    if fn is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state has no "
            "`gate_armed_states` function yet -- slice-03's per-gate 4-tier "
            "classifier (armed/armed-prose/dormant/indeterminate) has not been "
            "implemented. WHY: this AT drives the tier-classification the "
            "trust-policy change (decision #1) requires -- `host_visibility` "
            "self-declaration alone must no longer resolve a gate as armed. "
            "HOW: implement `gate_armed_states(gates, *, inputs: "
            "ArmedStateInputs) -> dict[str, str]` returning {gate_id: tier} "
            "for every catalogued gate, tiers in {'armed', 'armed-prose', "
            "'dormant', 'indeterminate'}; keep `coherence_offenders` as a "
            "backward-compatible view returning the gate-ids whose tier is "
            "'indeterminate'."
        )
    return fn


def _assert_armed_state_inputs_supports_slice03_fields() -> None:
    """Presence-probe (P1+P3) for `ArmedStateInputs`'s two NEW slice-03
    fields. Introspects `dataclasses.fields()` -- never constructs the
    dataclass with the new kwargs directly -- so a missing field surfaces as
    a NAMED AssertionError, never a bare `TypeError: unexpected keyword
    argument 'prose_text'` at construction time."""
    import dataclasses

    from des.cli.verify_gate_armed_state import ArmedStateInputs

    field_names = {f.name for f in dataclasses.fields(ArmedStateInputs)}
    missing = {"prose_text", "registered_cli_verbs"} - field_names
    if missing:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: ArmedStateInputs is missing field(s) "
            f"{sorted(missing)} -- slice-03 grows the surface-evidence bundle "
            'with injectable prose evidence (`prose_text: str = ""`, later '
            "wired by slice-06's real agent/skill/task scanner) and the "
            "_REGISTRY cross-check set (`registered_cli_verbs: "
            "frozenset[str] = frozenset()`, necessary-but-not-sufficient "
            "metadata per decision #1). WHY: without these fields the "
            "ARMED-PROSE tier and the host_visibility/_REGISTRY cross-check "
            "cannot be exercised as reachable, injectable verdict states. "
            "HOW: add both fields (with default values, so existing call "
            "sites keep working unchanged) to the ArmedStateInputs dataclass "
            "in src/des/cli/verify_gate_armed_state.py."
        )


def _import_wave_dispatch_class_table() -> dict[str, str]:
    """Presence-probe (P1+P3) for slice-04's reviewed per-wave dispatch-class
    table (decision #2). Guarded with `getattr(..., None)` so absence
    surfaces as a NAMED AssertionError, never an ImportError."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet (slice-02 must land first)."
        )
    import importlib as _importlib

    module = _importlib.import_module(_PROMOTED_MODULE)
    table = getattr(module, "WAVE_DISPATCH_CLASS", None)
    if table is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state has no "
            "`WAVE_DISPATCH_CLASS` table yet -- slice-04's reviewed per-wave "
            "dispatch-class table (decision #2) has not been authored. "
            "WHY: DISCUSS/DESIGN/DEVOPS's veto-capable review-gate-out stack "
            "must resolve ARMED differently from DISTILL's advisory-only "
            "stack -- a uniform 'waves/* declares gate-out => armed' rule is "
            "false. HOW: add `WAVE_DISPATCH_CLASS: dict[str, str]` mapping "
            "each wave to one of {'registry-veto', 'registry-advisory', "
            "'no-gate-out-stack'}: discuss/design/devops -> 'registry-veto' "
            "(dispatched live through _discuss_gate_out_declarative / "
            "_REVIEW_GATE_OUT_WAVES with real veto power), distill -> "
            "'registry-advisory' (the stack is declared in "
            "nWave/waves/distill.yaml but no live invoker dispatches it -- "
            "'distill' is absent from _REVIEW_GATE_OUT_WAVES), deliver -> "
            "'no-gate-out-stack' (nWave/waves/deliver.yaml declares "
            "gate_stack.gate-out: [] -- genuinely empty, not merely unwired)."
        )
    return table


def _import_wave_dispatch_class_divergences():
    """Presence-probe (P1+P3) for slice-04's cross-check function -- the
    mechanism that keeps `WAVE_DISPATCH_CLASS` and the LIVE
    `_REVIEW_GATE_OUT_WAVES` set from silently diverging (decision #2)."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet (slice-02 must land first)."
        )
    import importlib as _importlib

    module = _importlib.import_module(_PROMOTED_MODULE)
    fn = getattr(module, "wave_dispatch_class_divergences", None)
    if fn is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state has no "
            "`wave_dispatch_class_divergences` function yet -- decision #2's "
            "cross-check (the reviewed WAVE_DISPATCH_CLASS table must never "
            "silently diverge from the LIVE _REVIEW_GATE_OUT_WAVES set) has "
            "not been implemented. WHY: without this cross-check, someone "
            "adding/removing a wave from _REVIEW_GATE_OUT_WAVES (e.g. wiring "
            "'distill' into the live veto invoker) could forget to update "
            "WAVE_DISPATCH_CLASS, silently re-introducing the exact false "
            "'declares gate-out => armed' collapse this slice fixes. HOW: "
            "implement `wave_dispatch_class_divergences(review_gate_out_"
            "waves: frozenset[str]) -> list[str]` returning the sorted list "
            "of wave names where WAVE_DISPATCH_CLASS's 'registry-veto' rows "
            "disagree (in either direction) with membership in "
            "review_gate_out_waves; empty list means no divergence."
        )
    return fn


def _import_wave_gate_out_gate_ids_reader():
    """Presence-probe (P1+P3) for slice-04's stdlib-only wave-yaml gate-out
    reader -- parses `nWave/waves/<wave>.yaml`'s `gate_stack: gate-out:`
    block, mirroring `_parse_gate_host_visibility`'s established
    stdlib-regex shape (no PyYAML, F-D-09)."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet (slice-02 must land first)."
        )
    import importlib as _importlib

    module = _importlib.import_module(_PROMOTED_MODULE)
    fn = getattr(module, "_wave_gate_out_gate_ids", None)
    if fn is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state has no "
            "`_wave_gate_out_gate_ids` reader yet -- slice-04's wave-yaml "
            "gate-out reader (decision #2) has not been implemented. WHY: "
            "the per-wave dispatch-class table needs a real reader over "
            "nWave/waves/<wave>.yaml to feed `ArmedStateInputs."
            "wave_gate_out_hits`. HOW: implement `_wave_gate_out_gate_ids"
            "(repo_root: Path, wave: str) -> frozenset[str]`, stdlib-only "
            "line-oriented regex over nWave/waves/<wave>.yaml's `gate_stack: "
            "gate-out:` block (never the sibling `gate-in:` block), "
            "returning an empty frozenset when the file, the gate_stack "
            "key, or the gate-out block is absent or declared empty -- "
            "never raising (a wave legitimately declaring no gate-out stack, "
            "e.g. deliver.yaml's `gate-out: []`, is NOT an error)."
        )
    return fn


def _assert_armed_state_inputs_supports_slice04_field() -> None:
    """Presence-probe (P1+P3) for `ArmedStateInputs`'s slice-04 field.
    Introspects `dataclasses.fields()` -- never constructs the dataclass
    with the new kwarg directly -- so a missing field surfaces as a NAMED
    AssertionError, never a bare `TypeError: unexpected keyword argument
    'wave_gate_out_hits'`."""
    import dataclasses

    from des.cli.verify_gate_armed_state import ArmedStateInputs

    field_names = {f.name for f in dataclasses.fields(ArmedStateInputs)}
    if "wave_gate_out_hits" not in field_names:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: ArmedStateInputs is missing field "
            "'wave_gate_out_hits' -- slice-04 grows the surface-evidence "
            "bundle with the per-wave gate-out declarations "
            "`_wave_gate_out_gate_ids` reads (`wave_gate_out_hits: "
            "dict[str, frozenset[str]] = field(default_factory=dict)`, "
            "wave name -> the gate_ids that wave's gate-out stack declares). "
            "WHY: without this field, `gate_armed_states` cannot be driven "
            "with injected per-wave gate-out evidence, and the "
            "registry-veto-vs-registry-advisory distinction (decision #2) "
            "cannot be exercised as a reachable, injectable verdict path. "
            "HOW: add the field (with a default, so existing call sites "
            "keep working unchanged) to the ArmedStateInputs dataclass in "
            "src/des/cli/verify_gate_armed_state.py, and extend "
            "`gate_armed_states` so a gate_id present under a "
            "WAVE_DISPATCH_CLASS == 'registry-veto' wave's hits resolves "
            "'armed', while the SAME shape of evidence under a "
            "'registry-advisory' wave's hits grants no such credit."
        )


def _import_precommit_ci_indirection_reader():
    """Presence-probe (P1+P3) for slice-05's stdlib-only 2-hop pre-commit/CI
    indirection reader (decision #3) -- parses `.pre-commit-config.yaml` for
    an `entry:` line naming an in-repo wrapper script, reads that script's
    OWN text as DATA (never imports/executes it), and returns the gate_ids
    it finds as a literal, non-interpolated element of a
    `subprocess.run([...])` call."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet (slice-02 must land first)."
        )
    import importlib as _importlib

    module = _importlib.import_module(_PROMOTED_MODULE)
    fn = getattr(module, "_precommit_ci_indirection_gate_ids", None)
    if fn is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state has no "
            "`_precommit_ci_indirection_gate_ids` reader yet -- slice-05's "
            "2-hop pre-commit/CI indirection resolver (decision #3) has not "
            "been implemented. WHY: `.pre-commit-config.yaml` names only the "
            "WRAPPER SCRIPT (`entry: python3 scripts/hooks/"
            "run_slice_ats_precommit.py`) -- the gate_id literal "
            "'run-slice-ats' lives one hop further in, inside that wrapper's "
            'own `subprocess.run([..., "des", "run-slice-ats", ...])` '
            "call; a flat concatenation of .pre-commit-config.yaml text "
            "alone (the existing `_firing_surface_text` shape) cannot see "
            "it. HOW: implement `_precommit_ci_indirection_gate_ids"
            "(repo_root: Path) -> frozenset[str]`: read "
            "`.pre-commit-config.yaml`, resolve each `entry:` line's script "
            "path relative to repo_root, and for every such script that "
            "exists INSIDE repo_root, read its text and regex-search for a "
            "`subprocess.run([...])` call's literal (non-interpolated, "
            "non-f-string) quoted string elements -- any element matching a "
            "catalogued gate_id is a genuine independent CODE hit. A "
            "wrapper whose OWN body dispatches dynamically (e.g. an "
            "`importlib.util.spec_from_file_location` call resolving a path "
            "outside repo_root, mirroring `scripts/hooks/"
            'run_des_declare_done_pre_push.py`\'s `Path.home() / ".claude" '
            '/ "scripts" / ...` shape) must contribute NOTHING for that '
            "gate -- never raise, never guess, never chase past that hop."
        )
    return fn


def _import_prose_surface_text_reader():
    """Presence-probe (P1+P3) for slice-06's real agent/skill/task prose
    surface reader. The module and `ArmedStateInputs.prose_text` both exist
    since slice-02/slice-03 -- what may be ABSENT is the `_prose_surface_text`
    reader function itself (and, separately, its wiring into
    `_gate_states_for_repo`, which the tests in this section prove by driving
    `main()`/`_gate_states_for_repo` over a real or synthetic repo tree
    rather than by introspecting the wiring call site directly)."""
    if importlib.util.find_spec(_PROMOTED_MODULE) is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: `importlib.util.find_spec({_PROMOTED_MODULE!r})` "
            "resolved to None -- src/des/cli/verify_gate_armed_state.py does not "
            "exist yet (slice-02 must land first)."
        )
    import importlib as _importlib

    module = _importlib.import_module(_PROMOTED_MODULE)
    fn = getattr(module, "_prose_surface_text", None)
    if fn is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state has no "
            "`_prose_surface_text` reader yet -- slice-06's real agent/skill/"
            "task prose surface reader (feature-delta.md slice-06 Value "
            "statement; design/brief.md §6 slice 6) has not been implemented. "
            "WHY: `ArmedStateInputs.prose_text` (slice-03) is a REACHABLE, "
            "injectable field, but nothing populates it from the REAL repo "
            "tree -- `_gate_states_for_repo` (the real CLI's wiring function) "
            "passes only `firing_text` today, so no real gate can ever "
            "resolve 'armed-prose' through `des verify-gate-armed-state` "
            "itself, only through a synthetic test fixture (slice-03's own "
            "injectable-only test). HOW: implement `_prose_surface_text"
            "(repo_root: Path) -> str`, a stdlib-only reader (F-D-09, no "
            "PyYAML) that concatenates the text of every file matching "
            "`nWave/agents/*.md`, `nWave/skills/*/SKILL.md`, and "
            "`nWave/tasks/nw/*.md` under repo_root (mirroring "
            "`_firing_surface_text`'s concatenation-and-search shape, "
            "`if candidate.exists()` skip-when-absent), then wire its output "
            "into `_gate_states_for_repo`'s `ArmedStateInputs(prose_text="
            "_prose_surface_text(repo_root), ...)` construction so the real "
            "CLI path actually resolves 'armed-prose' for a real "
            "prose-only-corroborated gate (e.g. verify-red-green)."
        )
    return fn


def _assert_armed_state_inputs_supports_slice05_field() -> None:
    """Presence-probe (P1+P3) for `ArmedStateInputs`'s slice-05 field.
    Introspects `dataclasses.fields()` -- never constructs the dataclass
    with the new kwarg directly -- so a missing field surfaces as a NAMED
    AssertionError, never a bare `TypeError: unexpected keyword argument
    'precommit_ci_indirection_hits'`."""
    import dataclasses

    from des.cli.verify_gate_armed_state import ArmedStateInputs

    field_names = {f.name for f in dataclasses.fields(ArmedStateInputs)}
    if "precommit_ci_indirection_hits" not in field_names:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: ArmedStateInputs is missing field "
            "'precommit_ci_indirection_hits' -- slice-05 grows the "
            "surface-evidence bundle with the gate_ids "
            "`_precommit_ci_indirection_gate_ids` resolves via the 2-hop "
            "pre-commit/CI indirection (`precommit_ci_indirection_hits: "
            "frozenset[str] = frozenset()`). WHY: without this field, "
            "`gate_armed_states` cannot be driven with injected "
            "pre-commit/CI indirection evidence, and the "
            "2-hop-static-vs-out-of-repo-dynamic distinction (decision #3) "
            "cannot be exercised as a reachable, injectable verdict path. "
            "HOW: add the field (with a default, so existing call sites "
            "keep working unchanged) to the ArmedStateInputs dataclass in "
            "src/des/cli/verify_gate_armed_state.py, and extend "
            "`gate_armed_states` so a gate_id present in "
            "`precommit_ci_indirection_hits` resolves 'armed', exactly as "
            "`wave_gate_out_hits` under a registry-veto wave already grants."
        )


# ---------------------------------------------------------------------------
# Throwaway repo-tree builders (mirror the real `nWave/gates/` layout
# minimally). The promoted reducer's CURRENT (unchanged) decision rule reads
# ONLY: (a) `nWave/gates/_catalog.yaml` gate rows (gate_id / module /
# optional dormant), (b) each gate's own per-gate `nWave/gates/<id>.yaml`
# `host_visibility` list, and (c) flavor/live-hook files AS OPTIONAL firing-
# text surfaces it skips when absent (`if f.exists()` in the reducer being
# promoted) -- so a fixture that omits flavor/hook files entirely is a valid,
# minimal throwaway repo: wiredness then resolves purely via the
# `host_visibility: [cli]` operator-tier (the S3 indirect-wiring case the 6
# existing ATs already exercise at the function level; this file drives the
# SAME rule through the CLI entrypoint instead of re-deriving it).
# ---------------------------------------------------------------------------


def _write_catalog_and_per_gate_files(repo_root: Path, gates: list[dict]) -> None:
    gates_dir = repo_root / "nWave" / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)

    catalog_lines = ['version: "1.0.0"', "", "gates:"]
    for gate in gates:
        gate_id = gate["gate_id"]
        module = gate.get("module", f"des.cli.{gate_id.replace('-', '_')}")
        catalog_lines.append(f"  - gate_id: {gate_id}")
        catalog_lines.append(f"    module: {module}")
        catalog_lines.append("    entry_function: main")
        if gate.get("dormant") is not None:
            catalog_lines.append(f'    dormant: "{gate["dormant"]}"')
    (gates_dir / "_catalog.yaml").write_text(
        "\n".join(catalog_lines) + "\n", encoding="utf-8"
    )

    for gate in gates:
        gate_id = gate["gate_id"]
        module = gate.get("module", f"des.cli.{gate_id.replace('-', '_')}")
        lines = [
            f"gate_id: {gate_id}",
            f"module: {module}",
            "entry_function: main",
        ]
        host_visibility = gate.get("host_visibility", [])
        if host_visibility:
            lines.append("host_visibility:")
            lines.extend(f"  - {v}" for v in host_visibility)
        (gates_dir / f"{gate_id}.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


def _write_malformed_catalog(repo_root: Path) -> None:
    gates_dir = repo_root / "nWave" / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    (gates_dir / "_catalog.yaml").write_text(
        "gates: [this is: not, valid: yaml: at all\n", encoding="utf-8"
    )


def _verdict_from(captured_out: str, *, command: str) -> dict:
    """The last non-empty JSON-shaped stdout line -- mirrors
    `verify_catalog_coherence`'s single `print(json.dumps(verdict))` shape.

    ``command`` names the exact invocation this AT ran, so a failure here
    states WHAT was run, WHY no verdict line was found, and HOW to fix it --
    never a bare "got none" with no route back to the missing behaviour.
    """
    json_lines = [
        line for line in captured_out.splitlines() if line.lstrip().startswith("{")
    ]
    assert json_lines, (
        f"WHAT: ran `{command}` and found zero JSON-shaped lines on stdout. "
        "WHY: main() must print exactly one JSON verdict object to stdout "
        "(mirroring `verify_catalog_coherence.py`'s "
        "`print(json.dumps(verdict))`) naming a `verdict` key + a `reason`. "
        "HOW: implement that print in src/des/cli/verify_gate_armed_state.py "
        f"so `{command}` emits it. Captured stdout=\n{captured_out}"
    )
    return json.loads(json_lines[-1])


# ===========================================================================
# 1. WALKING SKELETON (subprocess, the ONE per-feature E2E) -- covers: R1, R2, R3
# ===========================================================================


def _run_via_real_subprocess(
    cwd: Path, extra_args: list[str]
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC_ROOT)
    env["NWAVE_FRESHNESS"] = "skip"
    return subprocess.run(
        [sys.executable, "-m", "des.cli", "verify-gate-armed-state", *extra_args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.walking_skeleton
def test_walking_skeleton_maintainer_runs_verify_gate_armed_state_via_real_cli(
    tmp_path: Path,
) -> None:
    """A maintainer invokes `des verify-gate-armed-state` as its own real,
    catalogued CLI entrypoint -- proving the feature's user-observable
    capability end-to-end through the ACTUAL installed dispatcher: (a) a
    coherent real checkout resolves a JSON verdict + exit 0; (b) a directory
    that is not an nWave-dev checkout at all degrades LOUD -- non-zero exit,
    no raw Python traceback, a reason + HOW guidance -- never a silent pass.
    One scenario, two sub-checks, matching the charter's own two named root
    kinds (real checkout / non-checkout) -- this feature's whole value
    proposition IS the happy-path-vs-degrade-LOUD contract, so both belong
    in the single walking skeleton rather than a second justified E2E.

    # covers: R1
    # covers: R2
    # covers: R3
    """
    # (a) the real feature checkout -- known-coherent today (the 6 existing
    # regression ATs over the live catalog are GREEN).
    coherent_proc = _run_via_real_subprocess(_REPO_ROOT, ["--repo-root", "."])
    coherent_output = coherent_proc.stdout + coherent_proc.stderr
    assert "Traceback (most recent call last)" not in coherent_output, (
        f"the real checkout must never crash with a raw traceback: {coherent_output}"
    )
    coherent_verdict = _verdict_from(
        coherent_proc.stdout,
        command="python -m des.cli verify-gate-armed-state --repo-root . (real checkout)",
    )
    assert "verdict" in coherent_verdict, (
        f"expected a `verdict` key naming the judgment: {coherent_verdict}"
    )
    assert coherent_proc.returncode == 0, (
        "a coherent real checkout must exit 0 -- got "
        f"{coherent_proc.returncode}, verdict={coherent_verdict}"
    )

    # (b) a bare directory that is not an nWave-dev checkout at all.
    outside = tmp_path / "not-a-checkout"
    outside.mkdir()
    outside_proc = _run_via_real_subprocess(outside, [])
    outside_output = outside_proc.stdout + outside_proc.stderr
    assert "Traceback (most recent call last)" not in outside_output, (
        "outside a checkout the command must degrade LOUD with a "
        f"human-readable message, never a raw traceback: {outside_output}"
    )
    assert outside_proc.returncode != 0, (
        "outside a checkout the exit code must be non-zero (never a silent "
        f"pass) -- got {outside_proc.returncode}, output=\n{outside_output}"
    )
    assert outside_output.strip(), (
        "outside a checkout the command must print a non-empty diagnostic "
        "-- got empty output"
    )


# ===========================================================================
# 2. IN-PROCESS -- CLI contract shape (argparse smoke test / JSON-format
#    smoke test / degrade-LOUD-on-unreadable-input), the L2 default.
# ===========================================================================


def test_main_reports_exit_zero_on_a_code_armed_synthetic_repo(
    tmp_path: Path,
) -> None:
    """RE-BASELINED (slice-03, decision #1): originally named
    `test_main_reports_a_coherent_verdict_on_a_wired_synthetic_repo` and
    drove a gate wired ONLY via operator-direct `host_visibility: [cli]` --
    exactly the self-declaration-only evidence decision #1 demotes to
    CLI-existence-only metadata. Retargeted at a genuine CODE-surface hit
    (the gate's module named in a flavor `gate_id` row) so this smoke test
    still legitimately proves the ARMED/exit-0 happy path; the
    `host_visibility`-only case is now covered by
    `test_a_self_declaration_only_gate_resolves_indeterminate_not_armed`
    below and the real-catalog headline regression, both of which assert it
    resolves `indeterminate`, never `armed`.

    # covers: R2
    # covers: R4
    """
    main = _import_verify_gate_armed_state()
    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [{"gate_id": "code-armed-gate", "host_visibility": []}],
    )
    flavor_dir = repo_root / "nWave" / "flavors"
    flavor_dir.mkdir(parents=True, exist_ok=True)
    (flavor_dir / "atdd_pure.yaml").write_text(
        "gate_id: code-armed-gate\n", encoding="utf-8"
    )

    exit_code = main(["--repo-root", str(repo_root)])

    assert exit_code == 0, (
        f"expected exit 0 on a genuinely CODE-armed synthetic repo, got {exit_code}"
    )


def test_a_self_declaration_only_gate_resolves_indeterminate_not_armed(
    tmp_path: Path, capsys
) -> None:
    """RE-BASELINED (slice-03, decision #1): originally
    `test_main_names_the_unwired_non_dormant_gate_and_exits_non_zero` --
    named `wired-gate` (`host_visibility: [cli]` only) as the NOT-flagged
    control and asserted `exit_code != 0` when the orphan gate (zero
    evidence) existed. BOTH claims flip under the new trust policy: (i)
    `wired-gate` is no longer armed by self-declaration alone -- it now
    resolves `indeterminate` exactly like `orphan-gate` (zero independent
    evidence of any kind); (ii) with no reviewed baseline yet (pre-slice-07)
    an indeterminate population is a WARNING annotation, not a hard failure
    (feature-delta.md `## Wave: DESIGN / [REF] Architecture & Contract
    Tests`: "Success (exit 0): ... every INDETERMINATE gate is ... reported
    as a NEW INDETERMINATE (a WARNING annotation, not a hard failure, ...
    until slice-07 lands it as fail-closed)") -- so exit code is now 0,
    never `!= 0`, for this fixture.

    NEVER silently relaxed to pass: both gates must still be NAMED, now
    under the `indeterminate` population, and absent from `armed` -- the
    check still proves the reducer distinguishes unresolved gates, just
    reports them softly instead of hard-failing pre-baseline.

    # covers: R2
    # covers: R9
    """
    main = _import_verify_gate_armed_state()
    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [
            {"gate_id": "orphan-gate", "host_visibility": []},
            {"gate_id": "self-declared-only-gate", "host_visibility": ["cli"]},
        ],
    )

    exit_code = main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    verdict = _verdict_from(
        captured.out,
        command=f"main(['--repo-root', {str(repo_root)!r}]) (self-declaration-only repo)",
    )
    indeterminate = verdict.get("indeterminate", verdict.get("offenders", []))
    assert "orphan-gate" in indeterminate, (
        f"a gate with zero independent evidence must be named indeterminate: {verdict}"
    )
    assert "self-declared-only-gate" in indeterminate, (
        "a gate corroborated ONLY by host_visibility self-declaration must "
        f"ALSO resolve indeterminate -- it is no longer excused by "
        f"self-declaration alone: {verdict}"
    )
    armed = verdict.get("armed", [])
    assert "self-declared-only-gate" not in armed, (
        f"host_visibility alone must never populate 'armed': {verdict}"
    )
    assert exit_code == 0, (
        "pre-slice-07 (no reviewed baseline yet) an indeterminate population "
        f"is a WARNING, not a hard failure -- got exit {exit_code}: {verdict}"
    )


def test_main_excuses_a_gate_carrying_a_non_empty_dormant_rationale(
    tmp_path: Path, capsys
) -> None:
    """The explicit `dormant: <rationale>` escape (existing schema key,
    unchanged per Locked Decision L-4) excuses an otherwise-unwired gate.

    # covers: R2
    """
    main = _import_verify_gate_armed_state()
    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [
            {
                "gate_id": "dozing-gate",
                "host_visibility": [],
                "dormant": "intentionally unwired pending the SF-tier dispatch layer",
            }
        ],
    )

    exit_code = main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    verdict = _verdict_from(
        captured.out,
        command=f"main(['--repo-root', {str(repo_root)!r}]) (dormant-excused repo)",
    )
    assert exit_code == 0, (
        f"a dormant-excused gate with a real rationale must resolve coherent: {verdict}"
    )
    offenders = verdict.get("offenders", verdict.get("drifting_ids", []))
    assert "dozing-gate" not in offenders, (
        f"the dormant-excused gate must not be flagged: {verdict}"
    )


@pytest.mark.negative_at
def test_main_never_excuses_an_empty_dormant_rationale_and_reports_it_indeterminate(
    tmp_path: Path, capsys
) -> None:
    """RE-BASELINED (slice-03): the dormant-escape rule itself is UNCHANGED
    (Locked Decision L-4 -- `dormant`'s schema shape and meaning are reused
    verbatim) -- an empty/whitespace `dormant:` value still does NOT excuse
    a gate (inverse robustness, AT-A1-C's whitespace case). What changes is
    WHERE the not-excused gate lands: under the old binary check it was a
    hard-failing 'offender' (exit `!= 0`); under the new trust policy it
    falls through to `indeterminate` (no CODE/PROSE hit, no valid dormant
    rationale) and -- pre-slice-07, no reviewed baseline -- that is a
    WARNING, not a hard failure, so exit stays 0.

    # covers: R2
    """
    main = _import_verify_gate_armed_state()
    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [{"gate_id": "dozing-gate", "host_visibility": [], "dormant": "   "}],
    )

    exit_code = main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    verdict = _verdict_from(
        captured.out,
        command=f"main(['--repo-root', {str(repo_root)!r}]) (empty-dormant-rationale repo)",
    )
    dormant = verdict.get("dormant", [])
    indeterminate = verdict.get("indeterminate", verdict.get("offenders", []))
    assert "dozing-gate" not in dormant, (
        f"a whitespace-only dormant rationale must NOT excuse the gate: {verdict}"
    )
    assert "dozing-gate" in indeterminate, (
        f"the not-excused gate must still be NAMED, now in the indeterminate "
        f"population: {verdict}"
    )
    assert exit_code == 0, (
        "pre-slice-07 (no reviewed baseline yet) an indeterminate population "
        f"is a WARNING, not a hard failure -- got exit {exit_code}: {verdict}"
    )


@pytest.mark.negative_at
def test_main_does_not_silently_pass_on_a_malformed_catalog(
    tmp_path: Path, capsys
) -> None:
    """Degrade-LOUD-on-unreadable-input smoke test (Reuse Analysis:
    'CONSOLIDATE' -- the new CLI's own suite reuses this exact contract-shape
    test structure from `verify_catalog_coherence`'s sibling suite). A
    malformed `_catalog.yaml` must never crash with a raw traceback and must
    never silently exit 0.

    # covers: R3
    # covers: R5
    """
    main = _import_verify_gate_armed_state()
    repo_root = tmp_path / "repo"
    _write_malformed_catalog(repo_root)

    try:
        exit_code = main(["--repo-root", str(repo_root)])
    except Exception as exc:
        pytest.fail(
            "degrade-LOUD violation: a malformed _catalog.yaml must return a "
            f"non-zero exit + diagnostic, not raise {type(exc).__name__}: {exc}"
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code != 0, (
        "degrade-LOUD violation: a malformed _catalog.yaml must NOT produce "
        f"a silent PASS (exit 0); got {exit_code}"
    )
    assert "Traceback" not in combined_output, (
        "degrade-LOUD violation: a malformed catalog crashed with a "
        f"traceback instead of a diagnostic verdict:\n{combined_output}"
    )
    assert combined_output.strip(), (
        "expected a non-empty diagnostic message on a malformed catalog, "
        "got empty output"
    )


@pytest.mark.negative_at
def test_main_degrades_loud_when_repo_root_has_no_gate_catalog_at_all(
    tmp_path: Path, capsys
) -> None:
    """A `--repo-root` with no `nWave/gates/` directory at all (the common
    "not an nWave-dev checkout" case) must never silently pass and never
    raise -- an inability to look must never be reported identically to
    "I looked and it's fine" (charter negative observation).

    # covers: R3
    # covers: R5
    """
    main = _import_verify_gate_armed_state()
    bare_repo = tmp_path / "bare"
    bare_repo.mkdir()

    try:
        exit_code = main(["--repo-root", str(bare_repo)])
    except Exception as exc:
        pytest.fail(
            "degrade-LOUD violation: a repo-root with no nWave/gates/ "
            f"directory must return a non-zero exit + diagnostic, not raise "
            f"{type(exc).__name__}: {exc}"
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code != 0, (
        "a --repo-root with no nWave/gates/ directory must never silently "
        f"pass -- got exit {exit_code}"
    )
    assert combined_output.strip(), (
        "expected a non-empty diagnostic naming what could not be "
        "evaluated -- got empty output"
    )
    verdict_lines = [
        line for line in captured.out.splitlines() if line.lstrip().startswith("{")
    ]
    if verdict_lines:
        verdict = json.loads(verdict_lines[-1])
        assert verdict.get("verdict") != "coherent", (
            "an unevaluatable repo-root must never resolve the same "
            f"'coherent' verdict as a real pass: {verdict}"
        )


# ===========================================================================
# 3. PARITY -- the SAME real repo must not diverge from today's known-green
#    verdict (charter negative: "must NOT report ... different ... verdict
#    content ... than before this slice was built").
# ===========================================================================


def test_new_cli_over_the_real_catalog_moves_self_declaration_only_gates_to_indeterminate() -> (
    None
):
    """RE-BASELINED (slice-06, second re-baseline of this same test):
    slice-06 adds the R10/R16 armed-prose tier -- a gate mentioned in one of
    the three scanned prose surfaces (`nWave/agents/*.md`,
    `nWave/skills/*/SKILL.md`, `nWave/tasks/nw/*.md`) now resolves
    `armed_prose`, not `indeterminate`. `verify-charter-filled` is
    genuinely mentioned in `nWave/agents/nw-product-owner.md` and
    `nWave/skills/nw-distill/SKILL.md` / `nWave/skills/nw-expectation-
    charter/SKILL.md`, so it correctly moved from `indeterminate`
    (slice-03 baseline) to `armed_prose` (slice-06 design) -- this is the
    DESIGNED slice-06 behaviour, proven by slice-06's own new passing
    tests, not a regression. The parity claim this test proves --
    self-declaration-only gates (zero CODE evidence) must never silently
    resolve `armed` -- still holds; it now needs an exemplar with zero
    CODE hit AND zero PROSE hit AND no dormant-allowlist rationale.
    `runner-probe` has no `gate_id` row in `nWave/flavors/atdd_pure.yaml`
    and zero mentions across the three scanned prose surfaces (verified
    empirically), so it remains a genuine `indeterminate` exemplar. A
    genuinely CODE-wired gate (`carpaccio-slice-gate`, a real `gate_id`
    row in `nWave/flavors/atdd_pure.yaml`) remains under `armed`. The
    check still proves the promoted CLI agrees with the reducer's real
    behaviour over the real tree -- it is the reducer's OWN behaviour
    that legitimately changed across slices (mirrors the arch-tier
    re-baseline in
    `test_arch_a_live_catalog_moves_self_declaration_only_gates_to_
    indeterminate`, tests/build/f_nonbypassable_attestation/
    test_arch_catalog_gate_wiring.py).

    # covers: R4
    # covers: R9
    """
    main = _import_verify_gate_armed_state()

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--repo-root", str(_REPO_ROOT)])

    verdict = _verdict_from(
        buf.getvalue(),
        command=f"main(['--repo-root', {str(_REPO_ROOT)!r}]) (real, unchanged checkout)",
    )
    indeterminate = verdict.get("indeterminate", verdict.get("offenders", []))
    assert "runner-probe" in indeterminate, (
        "runner-probe (zero gate_id row in nWave/flavors/atdd_pure.yaml, "
        f"zero mentions across the three scanned prose surfaces) must "
        f"resolve indeterminate over the REAL checkout: {verdict}"
    )
    assert "runner-probe" not in verdict.get("armed", []), (
        f"a gate with zero CODE evidence must never populate 'armed': {verdict}"
    )
    assert "verify-charter-filled" in verdict.get("armed_prose", []), (
        "verify-charter-filled is genuinely mentioned in "
        "nWave/agents/nw-product-owner.md and nWave/skills/nw-distill + "
        "nw-expectation-charter SKILL.md (all inside the three scanned "
        "prose surfaces), so slice-06's prose reader (R10/R16) must "
        f"resolve it 'armed_prose': {verdict}"
    )
    assert "verify-charter-filled" not in verdict.get("armed", []), (
        f"prose-only evidence alone must never populate 'armed': {verdict}"
    )
    assert "carpaccio-slice-gate" in verdict.get("armed", []), (
        "carpaccio-slice-gate has a real CODE-surface hit (a `gate_id` row in "
        "nWave/flavors/atdd_pure.yaml) and must remain armed -- the "
        f"host_visibility trust-policy demotion must never downgrade a gate "
        f"with independent CODE evidence: {verdict}"
    )
    assert exit_code == 0, (
        "pre-slice-07 (no reviewed baseline yet) an indeterminate population "
        f"is a WARNING, not a hard failure -- the real checkout must still "
        f"exit 0: got {exit_code}, verdict={verdict}"
    )


# ===========================================================================
# 4. CATALOGUE + REGISTRY SELF-COHERENCE -- the gate must catalogue ITSELF
#    (DoD row 1). Pure text reads over the REAL shipped files -- no import.
# ===========================================================================


def test_gate_is_registered_in_the_real_cli_registry() -> None:
    """`src/des/cli/__main__.py` must carry a `_SubcommandRow` naming
    `verify-gate-armed-state` -- reads the REAL shipped registry as DATA
    (protocol-driver contract: assert a shipped artifact), no import.

    # covers: R6
    """
    main_py = _REPO_ROOT / "src" / "des" / "cli" / "__main__.py"
    text = main_py.read_text(encoding="utf-8")
    assert '"verify-gate-armed-state"' in text, (
        "MISSING_FUNCTIONALITY: src/des/cli/__main__.py has no "
        '_SubcommandRow("verify-gate-armed-state", ...) row yet. Add one '
        "pointing at des.cli.verify_gate_armed_state:main."
    )


def test_gate_has_a_catalog_row_in_the_real_gate_catalog() -> None:
    """`nWave/gates/_catalog.yaml` must carry a `gate_id: verify-gate-armed-
    state` row -- reads the REAL shipped catalog as DATA, no import.

    # covers: R6
    """
    catalog_path = _REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"
    text = catalog_path.read_text(encoding="utf-8")
    assert "gate_id: verify-gate-armed-state" in text, (
        "MISSING_FUNCTIONALITY: nWave/gates/_catalog.yaml has no "
        "`gate_id: verify-gate-armed-state` row yet. Add one alongside the "
        "sibling verify-catalog-coherence row."
    )


def test_gate_has_a_per_gate_contract_file() -> None:
    """`nWave/gates/verify-gate-armed-state.yaml` must exist and name the
    promoted module + entrypoint (GateContractFull shape, mirroring the
    sibling `verify-catalog-coherence.yaml`).

    # covers: R6
    """
    per_gate_path = _REPO_ROOT / "nWave" / "gates" / "verify-gate-armed-state.yaml"
    assert per_gate_path.exists(), (
        "MISSING_FUNCTIONALITY: nWave/gates/verify-gate-armed-state.yaml "
        "does not exist yet. Create it (GateContractFull shape) mirroring "
        "nWave/gates/verify-catalog-coherence.yaml."
    )
    text = per_gate_path.read_text(encoding="utf-8")
    assert "gate_id: verify-gate-armed-state" in text, text
    assert "module: des.cli.verify_gate_armed_state" in text, text
    assert "entry_function: main" in text, text


# ===========================================================================
# 5. PRODUCTION SYMBOL + STDLIB-ONLY (F-D-09) -- covers: R7, R8
# ===========================================================================


def test_promoted_module_is_resolvable_as_a_production_symbol() -> None:
    """`des.cli.verify_gate_armed_state` must resolve via `find_spec` --
    the production home the existing arch test
    (tests/build/f_nonbypassable_attestation/test_arch_catalog_gate_wiring.py)
    is meant to become a thin consumer of, instead of owning its own copy of
    the reducer.

    # covers: R8
    """
    spec = _find_promoted_module_spec()
    assert spec is not None, (
        "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state does not "
        "exist yet. Promote coherence_offenders "
        "(tests/build/f_nonbypassable_attestation/"
        "test_arch_catalog_gate_wiring.py) into "
        "src/des/cli/verify_gate_armed_state.py so it is importable as a "
        "real production symbol."
    )


def _top_level_import_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Every top-level module name an `import X` / `from X import Y` node
    binds, paired with its 1-based source line -- walks the REAL parsed AST,
    never source text, so a docstring/comment that merely mentions an import
    (prose documenting a constraint) can never be mistaken for one."""
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:  # None only for a relative `from . import x`
                names.append((node.module.split(".")[0], node.lineno))
    return names


def test_promoted_module_source_contains_no_yaml_import() -> None:
    """DES-bundle contract (F-D-09,
    tests/build/acceptance/plugin/steps/test_des_bundle_steps.py::
    des_no_external_deps): a bundled `des` module MUST NOT depend on PyYAML
    or any other third-party package -- stdlib and `des.*` only.

    Decides on the PROPERTY (a real `Import`/`ImportFrom` AST node naming a
    non-stdlib, non-`des` top-level module), never the DESIGNATION (a
    substring match over source text): `ast.parse` the promoted module and
    walk its import nodes, so a docstring/comment merely documenting the
    stdlib-only constraint in prose can never fail this AT, and a real
    non-stdlib import can never hide behind a renamed/aliased/reworded
    comment. Catches ANY external dependency, not only `yaml` by name.

    # covers: R7
    """
    spec = _find_promoted_module_spec()
    if spec is None or spec.origin is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: des.cli.verify_gate_armed_state does "
            "not exist yet -- cannot verify it is stdlib-only. Implement "
            "src/des/cli/verify_gate_armed_state.py first (stdlib-only "
            "regex parsing, no third-party imports, mirroring "
            "verify_catalog_coherence.py's DES-bundle-compliant reader)."
        )
    source_path = Path(spec.origin)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    stdlib_names = sys.stdlib_module_names
    offenders = [
        (name, lineno)
        for name, lineno in _top_level_import_names(tree)
        if name not in stdlib_names and name != "des" and name != "__future__"
    ]
    assert offenders == [], (
        "DES-bundle contract violation (F-D-09): "
        f"src/des/cli/verify_gate_armed_state.py imports non-stdlib, "
        f"non-des module(s) {[n for n, _ in offenders]} at line(s) "
        f"{[ln for _, ln in offenders]} -- a bundled des module must be "
        "stdlib-only. Parse _catalog.yaml / per-gate files with "
        "line-oriented regex instead, mirroring verify_catalog_coherence.py."
    )


# ===========================================================================
# 6. SLICE-03 NEW -- trust-policy demotion + the 4-tier verdict
#    (ARMED / ARMED-PROSE / DORMANT / INDETERMINATE). Covers: R9, R10.
# ===========================================================================


def test_verify_charter_filled_gate_resolves_indeterminate_never_armed_on_the_real_catalog() -> (
    None
):
    """HEADLINE regression (dispatch envelope; feature-delta.md Critical
    Grounding Finding): `verify-charter-filled` self-declares
    `host_visibility: [claude-code, codex, opencode, cli]` and has ZERO real
    callers (prior 912k-token audit) -- today's `coherence_offenders` falsely
    treats operator-visibility self-declaration as sufficient wiring proof,
    so this gate passes as WIRED. Decision #1 demotes host_visibility to
    CLI-existence-only metadata: it must NO LONGER, by itself, resolve
    ARMED.

    Drives `gate_armed_states` over the REAL, unchanged `nWave/gates/`
    catalog + firing surfaces (the live-tree witness, mirroring
    `test_arch_a_live_catalog_moves_self_declaration_only_gates_to_
    indeterminate`'s real-tree discipline) -- this false positive is LIVE,
    not theoretical (dispatch envelope), so the regression fixture is the
    REAL gate, never a synthetic stand-in.

    # covers: R9
    """
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice03_fields()

    from des.cli.verify_gate_armed_state import (
        ArmedStateInputs,
        _firing_surface_text,
        _parse_catalog_entries,
        _parse_gate_host_visibility,
    )

    gates = _parse_catalog_entries(_REPO_ROOT)
    gate_ids = {g["gate_id"] for g in gates}
    assert "verify-charter-filled" in gate_ids, (
        "the real catalog no longer carries `verify-charter-filled` -- this "
        "regression fixture requires it; if the gate was renamed or removed, "
        "retarget this AT at nWave/gates/_catalog.yaml's current "
        "self-declaration-only gate instead of deleting the assertion."
    )
    host_visibility = {
        g["gate_id"]: _parse_gate_host_visibility(_REPO_ROOT, g["gate_id"])
        for g in gates
    }
    states = gate_armed_states(
        gates,
        inputs=ArmedStateInputs(
            firing_text=_firing_surface_text(_REPO_ROOT),
            host_visibility=host_visibility,
        ),
    )
    assert states.get("verify-charter-filled") == "indeterminate", (
        "verify-charter-filled must resolve INDETERMINATE (host_visibility "
        "self-declaration alone is no longer sufficient corroboration) -- "
        f"got tier={states.get('verify-charter-filled')!r}. This is the "
        "measurement's headline false-positive (Critical Grounding Finding, "
        "feature-delta.md): today it falsely resolves 'armed'."
    )


def test_a_gate_with_only_prose_evidence_resolves_the_distinct_armed_prose_tier() -> (
    None
):
    """ARMED-PROSE is a real, DISTINCT tier (feature-delta.md `## Wave:
    DESIGN / [REF] Architecture & Contract Tests` four-tier table) --
    "prose-only hit ... reported DISTINCTLY, never merged into ARMED".
    Slice-03 authors ARMED-PROSE as a REACHABLE verdict state with an
    INJECTABLE input (the new `prose_text` field on `ArmedStateInputs`) --
    the real agent/skill/task scanner is slice-06's job (SCOPE BOUNDARY,
    dispatch envelope); this AT proves the tier exists and is
    distinguishable, not that the real scanner runs.

    # covers: R10
    """
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice03_fields()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    states = gate_armed_states(
        [{"gate_id": "prose-only-gate", "module": "des.cli.prose_only_gate"}],
        inputs=ArmedStateInputs(
            firing_text="",  # no CODE hit
            host_visibility={"prose-only-gate": frozenset()},
            prose_text=(
                "the nw-troubleshooter skill instructs: run "
                "`des prose-only-gate --repo-root .` before closing a bug"
            ),
        ),
    )
    assert states.get("prose-only-gate") == "armed-prose", (
        "a gate reached ONLY through prose (agent/skill/task instructing "
        "`des <verb>`) must resolve the DISTINCT 'armed-prose' tier -- got "
        f"{states.get('prose-only-gate')!r}. Never merge a prose hit into "
        "'armed' (CODE-surface-only) and never drop it into 'indeterminate' "
        "(prose IS real signal, just weaker)."
    )


def test_json_verdict_reports_all_four_tiers_as_distinct_never_merged_populations(
    tmp_path: Path, capsys
) -> None:
    """GDP-8 arity corollary: the third state (INDETERMINATE) -- and every
    other tier -- must reach the AGGREGATE. The CLI's JSON verdict must
    expose `armed`, `armed_prose`, `dormant`, and `indeterminate` as FOUR
    SEPARATE lists; collapsing any pair (e.g. armed_prose into armed, or
    indeterminate into armed) silently erases the distinction decision #1
    exists to draw, and each gate_id must appear in EXACTLY one population.

    # covers: R9
    # covers: R10
    """
    main = _import_verify_gate_armed_state()
    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [
            {"gate_id": "code-armed-gate", "host_visibility": []},
            {"gate_id": "cli-only-gate", "host_visibility": ["cli"]},
            {
                "gate_id": "dozing-gate",
                "host_visibility": [],
                "dormant": "intentionally unwired pending the SF-tier dispatch layer",
            },
        ],
    )
    flavor_dir = repo_root / "nWave" / "flavors"
    flavor_dir.mkdir(parents=True, exist_ok=True)
    (flavor_dir / "atdd_pure.yaml").write_text(
        "gate_id: code-armed-gate\n", encoding="utf-8"
    )

    exit_code = main(["--repo-root", str(repo_root)])
    captured = capsys.readouterr()
    verdict = _verdict_from(
        captured.out,
        command=f"main(['--repo-root', {str(repo_root)!r}]) (4-tier smoke test)",
    )

    for key in ("armed", "armed_prose", "dormant", "indeterminate"):
        assert key in verdict, (
            f"expected the JSON verdict to carry a distinct '{key}' "
            f"population -- got keys={sorted(verdict.keys())}: {verdict}"
        )
    assert "code-armed-gate" in verdict["armed"], verdict
    assert "dozing-gate" in verdict["dormant"], verdict
    assert "cli-only-gate" in verdict["indeterminate"], (
        "a gate corroborated ONLY by host_visibility self-declaration must "
        f"resolve indeterminate, never armed: {verdict}"
    )
    assert "cli-only-gate" not in verdict["armed"], (
        f"host_visibility alone must never populate 'armed': {verdict}"
    )
    all_populations = (
        set(verdict["armed"])
        | set(verdict["armed_prose"])
        | set(verdict["dormant"])
        | set(verdict["indeterminate"])
    )
    assert len(all_populations) == 3, (
        f"each gate_id must appear in EXACTLY one tier population, never "
        f"merged across two: {verdict}"
    )
    assert exit_code == 0, (
        "resolving every gate to a known tier (even indeterminate) is "
        "'Success (exit 0)' per the CLI contract -- pre-slice-07 there is "
        f"no reviewed baseline to fail closed against. Got {exit_code}: {verdict}"
    )


def test_gate_armed_states_reports_host_visibility_registry_membership_as_metadata_only() -> (
    None
):
    """Decision #1: host_visibility's ONLY remaining role is cross-checked
    metadata -- "does this gate_id exist as an invocable CLI verb at all"
    (surface #9, `_REGISTRY`), necessary-but-not-sufficient, NEVER wiring
    proof. Two synthetic gates, BOTH self-declaring `host_visibility: [cli]`,
    differing ONLY in whether their claimed verb is in the injected
    `registered_cli_verbs` set -- BOTH must still resolve `indeterminate`
    (self-declaration alone never suffices, registered or not), proving the
    registry cross-check is metadata, never a route to ARMED.

    # covers: R9
    """
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice03_fields()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    states = gate_armed_states(
        [
            {"gate_id": "real-verb-gate", "module": "des.cli.real_verb_gate"},
            {"gate_id": "phantom-verb-gate", "module": "des.cli.phantom_verb_gate"},
        ],
        inputs=ArmedStateInputs(
            firing_text="",  # no CODE hit for either
            host_visibility={
                "real-verb-gate": frozenset({"cli"}),
                "phantom-verb-gate": frozenset({"cli"}),
            },
            registered_cli_verbs=frozenset({"real-verb-gate"}),  # phantom absent
        ),
    )
    assert states.get("real-verb-gate") == "indeterminate", (
        "a REGISTERED CLI verb that ONLY self-declares host_visibility must "
        "still resolve indeterminate -- registry membership is "
        f"necessary-but-not-sufficient metadata, never wiring proof: {states}"
    )
    assert states.get("phantom-verb-gate") == "indeterminate", (
        f"an UNREGISTERED phantom verb must equally resolve indeterminate: {states}"
    )


# ===========================================================================
# 7. SLICE-04 NEW -- per-wave dispatch-class table + wave-yaml gate-out
#    reader (decision #2). Covers: R11, R12, R13.
# ===========================================================================


def test_wave_dispatch_class_table_classifies_the_five_waves_correctly() -> None:
    """The reviewed per-wave dispatch-class table (decision #2) must
    classify every wave with a registered wave-contract file into exactly
    one of {"registry-veto", "registry-advisory", "no-gate-out-stack"}:
    discuss/design/devops really do dispatch their gate-out stack live with
    veto power; distill's stack is declared but never dispatched; deliver's
    stack is genuinely empty (`gate_stack.gate-out: []`).

    # covers: R11
    """
    table = _import_wave_dispatch_class_table()
    assert table.get("discuss") == "registry-veto", table
    assert table.get("design") == "registry-veto", table
    assert table.get("devops") == "registry-veto", table
    assert table.get("distill") == "registry-advisory", table
    assert table.get("deliver") == "no-gate-out-stack", table


def test_wave_dispatch_class_table_never_silently_diverges_from_the_live_review_gate_out_waves_set() -> (
    None
):
    """HEADLINE regression (decision #2, DoD row 4): the reviewed
    `WAVE_DISPATCH_CLASS` table and the LIVE `_REVIEW_GATE_OUT_WAVES` set
    (`src/des/application/subagent_stop_service.py`) encode the SAME
    distinction from two different places -- a wave dispatches its gate-out
    stack with real veto power. If someone adds/removes a wave from
    `_REVIEW_GATE_OUT_WAVES` (e.g. wiring "distill" into the live invoker
    later) without updating `WAVE_DISPATCH_CLASS`, the two tables silently
    diverge and this feature's own derivation becomes stale -- exactly the
    "catalogato != cablato" trap this whole feature exists to catch,
    recurring one level up. Drives the cross-check against the REAL,
    unchanged production constant (no mock, no synthetic double).

    # covers: R12
    """
    divergences_fn = _import_wave_dispatch_class_divergences()
    from des.application.subagent_stop_service import _REVIEW_GATE_OUT_WAVES

    offenders = divergences_fn(_REVIEW_GATE_OUT_WAVES)
    assert offenders == [], (
        "WAVE_DISPATCH_CLASS's 'registry-veto' rows disagree with the LIVE "
        f"_REVIEW_GATE_OUT_WAVES set at: {offenders} -- the two must never "
        f"silently diverge (decision #2); _REVIEW_GATE_OUT_WAVES = "
        f"{sorted(_REVIEW_GATE_OUT_WAVES)}"
    )


def test_wave_yaml_gate_out_reader_reads_declared_gate_ids_from_a_waves_yaml_file(
    tmp_path: Path,
) -> None:
    """The stdlib-only wave-yaml gate-out reader must parse ONLY the
    `gate_stack: gate-out:` block -- a `gate_id` declared in the sibling
    `gate-in:` block must NOT leak into the result (proves the reader
    targets the right block, not merely any `gate_id:` line in the file).

    # covers: R13
    """
    reader = _import_wave_gate_out_gate_ids_reader()
    repo_root = tmp_path / "repo"
    waves_dir = repo_root / "nWave" / "waves"
    waves_dir.mkdir(parents=True)
    (waves_dir / "sample-wave.yaml").write_text(
        "wave: sample-wave\n"
        "gate_stack:\n"
        "  gate-in:\n"
        "    - gate_id: gate-in-only-gate\n"
        "      on_failure: block\n"
        "  gate-out:\n"
        "    - gate_id: gate-out-alpha\n"
        "      on_failure: block\n"
        "    - gate_id: gate-out-beta\n"
        "      on_failure: warn\n",
        encoding="utf-8",
    )

    gate_ids = reader(repo_root, "sample-wave")

    assert gate_ids == frozenset({"gate-out-alpha", "gate-out-beta"}), gate_ids
    assert "gate-in-only-gate" not in gate_ids, (
        f"the reader must read ONLY the gate-out block, never gate-in: {gate_ids}"
    )


def test_wave_yaml_gate_out_reader_returns_empty_set_when_gate_out_is_declared_empty(
    tmp_path: Path,
) -> None:
    """Mirrors the REAL `nWave/waves/deliver.yaml` shape (`gate_stack.gate-
    out: []`) -- a wave legitimately declaring NO gate-out stack is a clean
    empty result, never an error and never confused with an unreadable file.

    # covers: R13
    """
    reader = _import_wave_gate_out_gate_ids_reader()
    repo_root = tmp_path / "repo"
    waves_dir = repo_root / "nWave" / "waves"
    waves_dir.mkdir(parents=True)
    (waves_dir / "deliver.yaml").write_text(
        "wave: deliver\n"
        "gate_stack:\n"
        "  gate-in:\n"
        "    - gate_id: verify-deliver-entry-contract\n"
        "      on_failure: block\n"
        "  gate-out: []\n",
        encoding="utf-8",
    )

    gate_ids = reader(repo_root, "deliver")

    assert gate_ids == frozenset(), gate_ids


@pytest.mark.negative_at
def test_wave_yaml_gate_out_reader_returns_empty_set_when_the_waves_file_is_absent(
    tmp_path: Path,
) -> None:
    """An inability to find the named wave's contract file must never raise
    and must never be conflated with "this wave declares zero gate-out
    rows" being reported any differently -- both degrade to the SAME clean
    empty result (the caller's dispatch-class table is what distinguishes
    "no-gate-out-stack" from "not read yet", never this reader alone).

    # covers: R13
    """
    reader = _import_wave_gate_out_gate_ids_reader()
    repo_root = tmp_path / "repo"
    (repo_root / "nWave" / "waves").mkdir(parents=True)

    gate_ids = reader(repo_root, "nonexistent-wave")

    assert gate_ids == frozenset(), gate_ids


def test_a_gate_declared_only_in_a_registry_veto_waves_gate_out_resolves_armed() -> (
    None
):
    """A gate_id declared in a REGISTRY-VETO wave's (discuss) gate-out
    stack is a genuine independent CODE hit: that wave's gate-out stack IS
    dispatched live with real veto power (`_REVIEW_GATE_OUT_WAVES`), so a
    row appearing there is exactly as much evidence as a flavor `gate_id`
    row or a live-hook module reference.

    # covers: R13
    """
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice04_field()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    states = gate_armed_states(
        [{"gate_id": "veto-wave-gate", "module": "des.cli.veto_wave_gate"}],
        inputs=ArmedStateInputs(
            firing_text="",  # no flavor/live-hook CODE hit
            host_visibility={"veto-wave-gate": frozenset()},
            wave_gate_out_hits={"discuss": frozenset({"veto-wave-gate"})},
        ),
    )
    assert states.get("veto-wave-gate") == "armed", (
        "a gate declared in a REGISTRY-VETO wave's (discuss) gate-out stack "
        "must resolve armed from that evidence alone -- that wave's "
        f"gate-out IS dispatched live with real veto power: {states}"
    )


def test_a_gate_declared_only_in_distills_registry_advisory_gate_out_does_not_resolve_armed() -> (
    None
):
    """HEADLINE regression (feature-delta.md slice-04 Value statement, DoD
    row 4): DISTILL's gate-out stack IS declared in
    `nWave/waves/distill.yaml` (including an `on_failure: block` row,
    `check-slice-at-completeness`) but NO live invoker dispatches it --
    `"distill"` is absent from `_REVIEW_GATE_OUT_WAVES`
    (`subagent_stop_service.py`'s own module-level DISCOVERY comment: adding
    it would activate the WHOLE stack, including a block-on-failure row no
    invoker routes, hard-blocking every DISTILL return). A gate reachable
    ONLY through that advisory-only declaration must NOT resolve the SAME
    "armed" verdict a genuinely veto-dispatched wave's declaration grants --
    this is the exact contrast that proves the uniform "waves/* declares
    gate-out => armed" rule is false.

    # covers: R13
    """
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice04_field()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    states = gate_armed_states(
        [{"gate_id": "advisory-wave-gate", "module": "des.cli.advisory_wave_gate"}],
        inputs=ArmedStateInputs(
            firing_text="",  # no flavor/live-hook CODE hit
            host_visibility={"advisory-wave-gate": frozenset()},
            wave_gate_out_hits={"distill": frozenset({"advisory-wave-gate"})},
        ),
    )
    assert states.get("advisory-wave-gate") != "armed", (
        "a gate declared ONLY in DISTILL's (registry-advisory) gate-out "
        "stack must NOT resolve 'armed' -- no live invoker dispatches that "
        f"stack, so the declaration alone is not independent CODE evidence: {states}"
    )
    assert states.get("advisory-wave-gate") == "indeterminate", (
        "with zero other evidence, the advisory-only declaration must fall "
        "through to 'indeterminate' (never a fabricated NOT-ARMED verdict, "
        f"decision #4): got {states.get('advisory-wave-gate')!r}: {states}"
    )


def test_real_discuss_gate_out_declaration_grants_armed_while_the_real_distill_declaration_alone_does_not() -> (
    None
):
    """Real-tree witness (mirrors `test_verify_charter_filled_gate_resolves_
    indeterminate_never_armed_on_the_real_catalog`'s real-tree discipline):
    drives the NEW wave-yaml reader over the REAL, unchanged
    `nWave/waves/discuss.yaml` (registry-veto) and `nWave/waves/
    distill.yaml` (registry-advisory), isolating EXACTLY this new surface's
    marginal contribution by setting `firing_text=""` (no flavor/live-hook
    evidence) and leaving `prose_text` at its default (no prose evidence) --
    any tier difference observed is attributable SOLELY to the
    `wave_gate_out_hits` surface + the dispatch-class table, never to some
    other evidence channel.

    # covers: R13
    """
    gate_armed_states = _import_gate_armed_states()
    reader = _import_wave_gate_out_gate_ids_reader()
    _assert_armed_state_inputs_supports_slice04_field()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    discuss_ids = reader(_REPO_ROOT, "discuss")
    distill_ids = reader(_REPO_ROOT, "distill")
    assert discuss_ids, (
        "expected the REAL nWave/waves/discuss.yaml to declare >=1 gate-out "
        "gate_id -- if this legitimately changed, retarget this AT at "
        "discuss.yaml's current gate-out rows instead of deleting the assertion."
    )
    assert distill_ids, (
        "expected the REAL nWave/waves/distill.yaml to declare >=1 gate-out "
        "gate_id -- if this legitimately changed, retarget this AT at "
        "distill.yaml's current gate-out rows instead of deleting the assertion."
    )

    all_ids = sorted(discuss_ids | distill_ids)
    gates = [{"gate_id": gid, "module": ""} for gid in all_ids]
    states = gate_armed_states(
        gates,
        inputs=ArmedStateInputs(
            firing_text="",
            host_visibility={gid: frozenset() for gid in all_ids},
            wave_gate_out_hits={"discuss": discuss_ids, "distill": distill_ids},
        ),
    )
    for gid in discuss_ids:
        assert states.get(gid) == "armed", (
            f"'{gid}' is declared in the REAL, registry-veto discuss.yaml "
            f"gate-out stack -- must resolve armed from that evidence "
            f"alone: {states}"
        )
    for gid in distill_ids - discuss_ids:
        assert states.get(gid) != "armed", (
            f"'{gid}' is declared ONLY in the REAL, registry-advisory "
            f"distill.yaml gate-out stack -- must NOT resolve armed from "
            f"that declaration alone (no live invoker dispatches it): {states}"
        )


@pytest.mark.negative_at
def test_a_gate_declared_in_an_unclassified_waves_gate_out_hits_never_grants_armed() -> (
    None
):
    """Defensive/negative: a wave name absent from `WAVE_DISPATCH_CLASS`
    entirely (a typo, or a future wave not yet reviewed into the table) must
    NEVER be treated as registry-veto by default -- fail-CLOSED, not
    fail-open, matching decision #2's "a SMALL REVIEWED table" framing: an
    unreviewed wave earns no automatic credit.

    # covers: R13
    """
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice04_field()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    states = gate_armed_states(
        [{"gate_id": "typo-wave-gate", "module": "des.cli.typo_wave_gate"}],
        inputs=ArmedStateInputs(
            firing_text="",
            host_visibility={"typo-wave-gate": frozenset()},
            wave_gate_out_hits={"discusss": frozenset({"typo-wave-gate"})},
        ),
    )
    assert states.get("typo-wave-gate") != "armed", (
        "a wave name absent from WAVE_DISPATCH_CLASS must never grant "
        f"armed by default (fail-closed, not fail-open): {states}"
    )


# ===========================================================================
# 8. SLICE-05 NEW -- pre-commit + CI + 2-hop indirection resolver
#    (decision #3). Two new ATs, both named in the measurement's own §6.
#    Covers: R14, R15.
# ===========================================================================


def test_real_precommit_two_hop_indirection_resolves_run_slice_ats_to_armed() -> None:
    """HEADLINE regression (feature-delta.md slice-05 Value statement,
    measurement §4/§6): `.pre-commit-config.yaml` invokes `run-slice-ats`
    only THROUGH its wrapper script (`entry: python3 scripts/hooks/
    run_slice_ats_precommit.py`) -- the gate_id literal lives one hop
    further in, inside that wrapper's own `subprocess.run([..., "des",
    "run-slice-ats", ...])` call. Confirmed today: BEFORE this slice, the
    real catalog's `run-slice-ats` gate resolves `"indeterminate"` (the
    existing flat `_firing_surface_text` concatenation cannot see past the
    wrapper-script hop) even though it is genuinely, statically wired.
    Real-tree witness (mirrors `test_real_discuss_gate_out_declaration_
    grants_armed_...`'s real-tree discipline): drives the NEW reader over
    the REAL, unchanged `.pre-commit-config.yaml` + `scripts/hooks/
    run_slice_ats_precommit.py`, isolating EXACTLY this new surface's
    marginal contribution by setting `firing_text=""` (no flavor/live-hook/
    wave-gate-out evidence) -- any resolution to "armed" is attributable
    SOLELY to the `precommit_ci_indirection_hits` surface, never to some
    other evidence channel.

    # covers: R14
    """
    reader = _import_precommit_ci_indirection_reader()
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice05_field()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    hits = reader(_REPO_ROOT)
    assert "run-slice-ats" in hits, (
        "expected the REAL .pre-commit-config.yaml -> scripts/hooks/"
        "run_slice_ats_precommit.py 2-hop indirection to resolve "
        "'run-slice-ats' as a genuine independent CODE hit -- if this "
        "legitimately changed (e.g. the wrapper's subprocess.run() argv "
        f"literal was renamed), retarget this AT instead of deleting it: {hits}"
    )

    states = gate_armed_states(
        [{"gate_id": "run-slice-ats", "module": ""}],
        inputs=ArmedStateInputs(
            firing_text="",  # no flavor/live-hook/wave-gate-out CODE hit
            host_visibility={"run-slice-ats": frozenset()},
            precommit_ci_indirection_hits=hits,
        ),
    )
    assert states.get("run-slice-ats") == "armed", (
        "'run-slice-ats' is genuinely wired through the REAL 2-hop "
        "pre-commit indirection -- it must resolve 'armed' from that "
        f"evidence alone, never 'indeterminate': {states}"
    )


@pytest.mark.negative_at
def test_an_out_of_repo_importlib_shaped_indirection_mirroring_declare_done_resolves_indeterminate_never_armed(
    tmp_path: Path,
) -> None:
    """Negative-space contrast to the ARMED case above (measurement §4/§6,
    decision #3): a synthetic fixture mirroring the REAL `scripts/hooks/
    run_des_declare_done_pre_push.py` shape -- a pre-commit wrapper whose
    OWN body dispatches via `importlib.util.spec_from_file_location` to a
    path OUTSIDE the repo tree (a home-directory-relative `~/.claude/scripts/...`),
    genuinely target-machine-dependent, 100% opaque to a static reader. The
    resolver must refuse to chase past that hop -- the gate must resolve
    `"indeterminate"` (the honest "cannot verify" tier), NEVER `"armed"`
    (fabricating wiring evidence that isn't there) and never crash trying to
    interpret the dynamic dispatch as a literal.

    # covers: R15
    """
    reader = _import_precommit_ci_indirection_reader()
    gate_armed_states = _import_gate_armed_states()
    _assert_armed_state_inputs_supports_slice05_field()
    from des.cli.verify_gate_armed_state import ArmedStateInputs

    repo_root = tmp_path / "repo"
    hooks_dir = repo_root / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    (repo_root / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: declare-done-shaped-gate\n"
        "        name: declare-done-shaped gate (out-of-repo dispatch)\n"
        "        entry: python3 scripts/hooks/declare_done_shaped_wrapper.py\n"
        "        language: system\n"
        "        stages: [pre-push]\n",
        encoding="utf-8",
    )
    (hooks_dir / "declare_done_shaped_wrapper.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import importlib.util\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        '    script = Path.home() / ".claude" / "scripts" / "declare_done_shaped_gate.py"\n'
        "    if not script.is_file():\n"
        "        return 0\n"
        '    spec = importlib.util.spec_from_file_location("declare_done_shaped_gate", script)\n'
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return module.main(argv)\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    _write_catalog_and_per_gate_files(
        repo_root,
        [{"gate_id": "declare-done-shaped-gate", "host_visibility": []}],
    )

    hits = reader(repo_root)
    assert "declare-done-shaped-gate" not in hits, (
        "an out-of-repo importlib-shaped indirection must contribute NOTHING "
        f"to the resolved hits -- the resolver must never chase past a "
        f"dynamic, outside-repo-tree dispatch hop: {hits}"
    )

    states = gate_armed_states(
        [{"gate_id": "declare-done-shaped-gate", "module": ""}],
        inputs=ArmedStateInputs(
            firing_text="",
            host_visibility={"declare-done-shaped-gate": frozenset()},
            precommit_ci_indirection_hits=hits,
        ),
    )
    assert states.get("declare-done-shaped-gate") == "indeterminate", (
        "an out-of-repo importlib-shaped indirection (mirroring `des "
        "declare-done`) must resolve 'indeterminate' -- the honest "
        f"'cannot verify' tier, never fabricated: {states}"
    )
    assert states.get("declare-done-shaped-gate") != "armed", (
        "an out-of-repo importlib-shaped indirection must NEVER resolve "
        f"'armed' -- that would fabricate wiring evidence: {states}"
    )

    # Negative-space contrast (charter lines 101-104, Vera FAIL 2026-07-31):
    # the INDETERMINATE case must not look identical to "the tool never
    # looked" -- the reason text must NAME the specific out-of-repo target
    # it tried and failed to resolve, and must be visibly distinguishable
    # from a genuinely-zero-wiring baseline gate's reason (no CODE/PROSE/
    # dormant evidence of any kind, no attempted-and-refused hop at all).
    from des.cli.verify_gate_armed_state import _render_how

    baseline_gate_id = "zero-wiring-baseline-gate"
    _write_catalog_and_per_gate_files(
        repo_root,
        [
            {"gate_id": "declare-done-shaped-gate", "host_visibility": []},
            {"gate_id": baseline_gate_id, "host_visibility": []},
        ],
    )
    contrast_states = gate_armed_states(
        [
            {"gate_id": "declare-done-shaped-gate", "module": ""},
            {"gate_id": baseline_gate_id, "module": ""},
        ],
        inputs=ArmedStateInputs(
            firing_text="",
            host_visibility={
                "declare-done-shaped-gate": frozenset(),
                baseline_gate_id: frozenset(),
            },
            precommit_ci_indirection_hits=hits,
        ),
    )
    assert contrast_states.get(baseline_gate_id) == "indeterminate", (
        "sanity precondition for this contrast: the zero-wiring baseline "
        "gate (no CODE/PROSE/dormant evidence of any kind) must itself "
        f"resolve 'indeterminate': {contrast_states}"
    )

    _home = Path.home()
    out_of_repo_target = str(
        _home / ".claude" / "scripts" / "declare_done_shaped_gate.py"
    )
    reasons = _render_how(["declare-done-shaped-gate", baseline_gate_id])
    reason_out_of_repo = next(
        r for r in reasons if r.startswith("'declare-done-shaped-gate'")
    )
    reason_baseline = next(r for r in reasons if r.startswith(f"'{baseline_gate_id}'"))

    assert out_of_repo_target in reason_out_of_repo, (
        "negative-space (charter lines 101-104): the out-of-repo importlib-"
        "shaped gate's INDETERMINATE reason must NAME the specific out-of-"
        f"repo target it tried and failed to resolve ({out_of_repo_target!r}) "
        "-- a maintainer must be able to tell 'looked but unreachable' apart "
        "from 'never looked' by reading the reason alone, with no config "
        f"file open. Got reason: {reason_out_of_repo!r}"
    )
    assert out_of_repo_target not in reason_baseline, (
        "the zero-wiring baseline reason must NOT mention the out-of-repo "
        f"target -- it never attempted any dispatch at all. Got reason: "
        f"{reason_baseline!r}"
    )

    stripped_out_of_repo = reason_out_of_repo.replace(
        "declare-done-shaped-gate", "<gate>"
    )
    stripped_baseline = reason_baseline.replace(baseline_gate_id, "<gate>")
    assert stripped_out_of_repo != stripped_baseline, (
        "negative-space (charter line 101): beyond the substituted gate_id, "
        "the out-of-repo reason and the zero-wiring baseline reason must be "
        "VISIBLY DIFFERENT -- an identical generic template for both would "
        "mean the tool cannot distinguish 'the wiring was traced and gave "
        "up at a real out-of-repo hop' from 'nothing was ever traced', "
        f"which is exactly the charter's negative requirement. Out-of-repo="
        f"{reason_out_of_repo!r} baseline={reason_baseline!r}"
    )


# ===========================================================================
# 9. SLICE-06 NEW -- agent/skill/task prose surface reader, wired into the
#    real CLI path (`_gate_states_for_repo`). Covers: R16, R17.
# ===========================================================================


def test_verify_red_green_gate_resolves_armed_prose_via_the_real_cli_over_the_real_checkout() -> (
    None
):
    """HEADLINE regression (dispatch envelope; feature-delta.md slice-06
    Value statement; design/brief.md §6 slice 6's own named example):
    `verify-red-green` self-declares only `host_visibility: [cli]`, has ZERO
    code-surface hit (no flavor `gate_id` row, no live-hook module
    reference), and IS genuinely mentioned across multiple real agent/skill/
    task files (`nWave/agents/nw-acceptance-designer.md`, `nWave/skills/
    nw-distill-red-scaffolding/SKILL.md`, `nWave/tasks/nw/execute.md`,
    others) -- confirmed by direct grep before this AT was authored. Today
    (pre-slice-06) it resolves `indeterminate`, because nothing reads or
    wires real prose evidence into the CLI path. Once the real reader lands
    and is wired into `_gate_states_for_repo`, it must resolve the DISTINCT
    `armed-prose` tier -- never silently merged into `armed` and never
    missed (left under `indeterminate`).

    Drives the REAL, promoted `main()` CLI entrypoint over the REAL,
    unchanged repo tree (the live-tree witness, mirroring
    `test_new_cli_over_the_real_catalog_moves_self_declaration_only_gates_
    to_indeterminate`'s real-tree discipline) -- this reader either exists
    and is wired, or it does not, on the actual checked-in tree.

    # covers: R16
    """
    main = _import_verify_gate_armed_state()
    _import_prose_surface_text_reader()

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--repo-root", str(_REPO_ROOT)])

    verdict = _verdict_from(
        buf.getvalue(),
        command=f"main(['--repo-root', {str(_REPO_ROOT)!r}]) (real checkout, prose reader)",
    )
    assert "verify-red-green" in verdict.get("armed_prose", []), (
        "verify-red-green (host_visibility: [cli] only, zero code-surface "
        "hit, but genuinely mentioned in real agent/skill/task prose across "
        "this checkout) must resolve the DISTINCT 'armed-prose' tier once "
        f"the real prose reader is wired into the CLI path: {verdict}"
    )
    assert "verify-red-green" not in verdict.get("armed", []), (
        f"a prose-only hit must never be merged into 'armed': {verdict}"
    )
    assert "verify-red-green" not in verdict.get("indeterminate", []), (
        "with the real prose reader wired, verify-red-green must no longer "
        f"fall through to 'indeterminate': {verdict}"
    )
    assert exit_code == 0, (
        f"an armed-prose population is real signal, not a hard failure "
        f"pre-slice-07: got exit_code={exit_code}, verdict={verdict}"
    )


def test_a_new_prose_only_gate_resolves_armed_prose_through_the_real_cli_end_to_end(
    tmp_path: Path,
) -> None:
    """Synthetic end-to-end wiring proof (complements the real-tree witness
    above): a brand-new gate_id, never seen by this repo's real surfaces,
    with NO flavor row, NO live-hook reference, and NO host_visibility
    self-declaration -- its ONLY evidence anywhere is a single agent-prose
    mention. Proves the full pipeline (`_prose_surface_text` reader ->
    `ArmedStateInputs.prose_text` -> `gate_armed_states` -> the JSON
    verdict's `armed_prose` population) is wired end-to-end through `main()`,
    not merely reachable via direct construction of `ArmedStateInputs`
    (slice-03's injectable-only test already proved reachability; this AT
    proves REAL wiring).

    # covers: R16
    """
    main = _import_verify_gate_armed_state()
    _import_prose_surface_text_reader()

    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [{"gate_id": "synthetic-prose-only-gate", "host_visibility": []}],
    )
    agents_dir = repo_root / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "some-agent.md").write_text(
        "When closing a bug, run `des synthetic-prose-only-gate "
        "--repo-root .` before committing.\n",
        encoding="utf-8",
    )

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--repo-root", str(repo_root)])

    verdict = _verdict_from(
        buf.getvalue(),
        command=f"main(['--repo-root', {str(repo_root)!r}]) (synthetic prose-only gate)",
    )
    assert "synthetic-prose-only-gate" in verdict.get("armed_prose", []), (
        "a brand-new gate whose ONLY evidence anywhere is a single "
        "agent-prose mention must resolve 'armed-prose' through the REAL "
        f"main() CLI entrypoint end-to-end -- got: {verdict}"
    )
    assert "synthetic-prose-only-gate" not in verdict.get("armed", []), (
        f"a prose-only gate must never be merged into 'armed': {verdict}"
    )
    assert exit_code == 0, f"got exit_code={exit_code}, verdict={verdict}"


def test_prose_reader_ignores_a_des_verb_mention_outside_the_agent_skill_task_surfaces(
    tmp_path: Path,
) -> None:
    """NEGATIVE (scope boundary): the prose reader must be SCOPED to exactly
    the three named surface classes (`nWave/agents/*.md`, `nWave/skills/
    */SKILL.md`, `nWave/tasks/nw/*.md`) -- NEVER a blanket scan of the whole
    repo tree. A `des <verb>` mention living anywhere ELSE (a top-level
    README, a docs/ page, a test file, an ADR) must NOT produce a false
    armed-prose hit; otherwise every gate whose name happens to appear
    anywhere in any prose (extremely common in this repo's own docs/backlog/
    Mikado files) would falsely arm, defeating the whole point of a
    DISTINCT, weaker tier.

    # covers: R17
    """
    main = _import_verify_gate_armed_state()
    _import_prose_surface_text_reader()

    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [{"gate_id": "scope-boundary-gate", "host_visibility": []}],
    )
    # Mention the gate_id in a file OUTSIDE the scanned surfaces.
    (repo_root / "README.md").write_text(
        "See `des scope-boundary-gate --repo-root .` for details.\n",
        encoding="utf-8",
    )
    docs_dir = repo_root / "docs" / "notes"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "random.md").write_text(
        "Also run `des scope-boundary-gate` here.\n", encoding="utf-8"
    )

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--repo-root", str(repo_root)])

    verdict = _verdict_from(
        buf.getvalue(),
        command=f"main(['--repo-root', {str(repo_root)!r}]) (out-of-scope prose mention)",
    )
    assert "scope-boundary-gate" not in verdict.get("armed_prose", []), (
        "a des-verb mention living OUTSIDE nWave/agents|skills|tasks must "
        f"never produce a false armed-prose hit: {verdict}"
    )
    assert "scope-boundary-gate" in verdict.get("indeterminate", []), (
        "with zero evidence in the SCANNED surfaces, the gate must fall "
        f"through to indeterminate, not be falsely armed by an out-of-scope "
        f"mention: {verdict}"
    )
    assert exit_code == 0, f"got exit_code={exit_code}, verdict={verdict}"


def test_a_gate_with_both_a_code_hit_and_a_prose_hit_resolves_armed_never_armed_prose(
    tmp_path: Path,
) -> None:
    """NEGATIVE (merge-safety, GDP-8 arity corollary): a gate reachable
    through BOTH a real CODE surface (a flavor `gate_id` row) AND
    agent/skill/task prose must resolve `"armed"`, never `"armed-prose"` --
    the two tiers must never conflate for the SAME gate_id. A CODE hit is
    always the stronger, independent surface; prose evidence is additional,
    never competing, signal.

    # covers: R17
    """
    main = _import_verify_gate_armed_state()
    _import_prose_surface_text_reader()

    repo_root = tmp_path / "repo"
    _write_catalog_and_per_gate_files(
        repo_root,
        [{"gate_id": "dual-evidence-gate", "host_visibility": []}],
    )
    flavor_dir = repo_root / "nWave" / "flavors"
    flavor_dir.mkdir(parents=True, exist_ok=True)
    (flavor_dir / "atdd_pure.yaml").write_text(
        "gate_id: dual-evidence-gate\n", encoding="utf-8"
    )
    agents_dir = repo_root / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "some-agent.md").write_text(
        "Also run `des dual-evidence-gate --repo-root .` when in doubt.\n",
        encoding="utf-8",
    )

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--repo-root", str(repo_root)])

    verdict = _verdict_from(
        buf.getvalue(),
        command=f"main(['--repo-root', {str(repo_root)!r}]) (dual CODE + prose evidence)",
    )
    assert "dual-evidence-gate" in verdict.get("armed", []), (
        "a gate with a real CODE-surface hit must resolve 'armed' even when "
        f"it ALSO has a prose hit: {verdict}"
    )
    assert "dual-evidence-gate" not in verdict.get("armed_prose", []), (
        "a CODE hit and a prose hit for the SAME gate_id must never both "
        f"populate their respective tiers -- the CODE hit wins: {verdict}"
    )
    assert exit_code == 0, f"got exit_code={exit_code}, verdict={verdict}"


def test_prose_surface_reader_finds_des_verb_mentions_across_agents_skills_and_tasks_directories(
    tmp_path: Path,
) -> None:
    """Reader-level proof (mirrors `test_wave_yaml_gate_out_reader_reads_
    declared_gate_ids_from_a_waves_yaml_file`'s direct-reader-function
    discipline): the reader must UNION all three named surface classes, not
    just one -- a `des <verb>` mention living in ONLY an agent file, ONLY a
    skill file, or ONLY a task file must each be independently detectable in
    the reader's returned text, proving no surface class is silently
    dropped.

    # covers: R16
    """
    reader = _import_prose_surface_text_reader()

    repo_root = tmp_path / "repo"
    agents_dir = repo_root / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "some-agent.md").write_text(
        "run `des agent-only-gate --repo-root .`\n", encoding="utf-8"
    )
    skill_dir = repo_root / "nWave" / "skills" / "some-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "invoke `des skill-only-gate --repo-root .`\n", encoding="utf-8"
    )
    tasks_dir = repo_root / "nWave" / "tasks" / "nw"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "some-task.md").write_text(
        "call `des task-only-gate --repo-root .`\n", encoding="utf-8"
    )

    text = reader(repo_root)

    assert "des agent-only-gate" in text, (
        f"the reader must scan nWave/agents/*.md -- got text={text!r}"
    )
    assert "des skill-only-gate" in text, (
        f"the reader must scan nWave/skills/*/SKILL.md -- got text={text!r}"
    )
    assert "des task-only-gate" in text, (
        f"the reader must scan nWave/tasks/nw/*.md -- got text={text!r}"
    )
