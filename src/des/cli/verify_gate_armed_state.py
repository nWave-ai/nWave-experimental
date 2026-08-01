"""des verify-gate-armed-state -- promoted armed-state coherence gate.

Charter: docs/product/expectations/gate-armed-state-derivation/
         a-maintainer-running-des-verify-gate-armed-state-gets-a-real-catalogued-operator-invokable-cli.md
Feature-delta: docs/feature/gate-armed-state-derivation/feature-delta.md
Design brief: docs/feature/gate-armed-state-derivation/design/brief.md

SLICE-02 SCOPE: a PURE MOVE + wiring of the already-GREEN ``coherence_offenders``
reducer (previously living inside
``tests/build/f_nonbypassable_attestation/test_arch_catalog_gate_wiring.py``)
into a first-class, catalogued, operator-invokable ``des`` CLI gate mirroring
``src/des/cli/verify_catalog_coherence.py``'s shape -- ZERO verdict-logic
change. The 4-tier ARMED/ARMED-PROSE/DORMANT/INDETERMINATE verdict, the
per-wave dispatch table, the pre-commit/CI/2-hop readers, the prose reader,
and the baseline-diff are OUT OF SCOPE here -- slices 03-07, each with its own
charter.

THE COHERENCE CONTRACT (unchanged from the promoted reducer): every
``gate_id`` in ``nWave/gates/_catalog.yaml`` is EITHER
  (a) WIRED -- referenced as a firing surface in a live hook: a flavor
      ``lifecycle_events`` / ``wave_gate_stacks`` gate_id row, OR a
      hook-definitions registry / live-hook module reference, OR an
      operator-direct CLI gate (``host_visibility`` includes ``cli`` /
      ``git-hook``) --
  OR
  (b) DORMANT -- carries an explicit ``dormant: <rationale>`` key (min length
      enforced by the schema so the escape requires a real rationale).
A catalogued gate that is NEITHER wired NOR dormant is the authored-but-unwired
failure class -> the coherence check FAILS and NAMES the unwired gate.

Stdlib-only (F-D-09, no PyYAML dependency) per the DES-bundle contract
(``tests/build/acceptance/plugin/steps/test_des_bundle_steps.py::
des_no_external_deps``): a bundled ``des`` module MUST NOT depend on PyYAML.
``_catalog.yaml`` and the per-gate ``host_visibility`` lists are parsed with
line-oriented regex instead (mirroring ``verify_catalog_coherence.py``'s
established stdlib-only precedent).

Degrade-LOUD (GDP-6), never a traceback and never a silent pass, on: (1) a
missing/unreadable ``nWave/gates/`` directory (``--repo-root`` is not an
nWave-dev checkout), (2) a missing/malformed ``_catalog.yaml``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument


@dataclass(frozen=True)
class ArmedStateInputs:
    """Bundles the surface-evidence parameters ``gate_armed_states`` reduces
    over. ``host_visibility`` is CLI-existence-only metadata (decision #1,
    slice-03): necessary-but-not-sufficient, never wiring proof by itself --
    kept on the bundle for the future registry cross-check, never consulted
    to grant the ``armed``/``armed-prose`` tiers. ``prose_text`` and
    ``registered_cli_verbs`` are slice-03's new injectable surface-evidence
    fields (real readers land in slices 05/06). ``wave_gate_out_hits`` is
    slice-04's new field (decision #2): wave name -> the gate_ids that
    wave's ``_wave_gate_out_gate_ids`` reader found declared under its
    ``gate_stack: gate-out:`` block -- injected so ``gate_armed_states`` is
    drivable synthetically without a real ``nWave/waves/`` tree.
    ``precommit_ci_indirection_hits`` is slice-05's new field (decision #3):
    the gate_ids ``_precommit_ci_indirection_gate_ids`` resolved via the
    2-hop pre-commit indirection (``.pre-commit-config.yaml`` -> an in-repo
    wrapper script -> that wrapper's own ``subprocess.run([...])`` literal
    argv elements) -- injected so ``gate_armed_states`` is drivable
    synthetically without a real ``.pre-commit-config.yaml`` tree. Later
    slices grow this bundle further (reviewed INDETERMINATE baseline).
    Introducing the dataclass avoided threading a growing keyword-parameter
    list through every call site -- the long-parameter-list smell the
    feature-delta Prefactoring Assessment flagged. Pure data, no behavior.
    """

    firing_text: str
    host_visibility: dict[str, frozenset[str]]
    prose_text: str = ""
    registered_cli_verbs: frozenset[str] = frozenset()
    wave_gate_out_hits: dict[str, frozenset[str]] = field(default_factory=dict)
    precommit_ci_indirection_hits: frozenset[str] = frozenset()


class ArmedStateInputUnavailableError(Exception):
    """An input needed to evaluate a gate's armed-state is missing or
    unreadable -- typically because ``--repo-root`` is not an nWave-dev
    checkout at all (no ``nWave/gates/`` directory). ``ArmedStateCatalogMalformedError``
    is the more specific subclass for a present-but-malformed catalog file.
    """


class ArmedStateCatalogMalformedError(ArmedStateInputUnavailableError):
    """``nWave/gates/_catalog.yaml`` is missing, unreadable, or fails to parse."""


_GATES_BLOCK_MARKER_RE = re.compile(r"^gates:\s*$", re.MULTILINE)
_GATE_ENTRY_START_RE = re.compile(
    r'^\s*-\s*gate_id:\s*"?([a-z0-9][a-z0-9-]*)"?\s*$', re.MULTILINE
)
_MODULE_LINE_RE = re.compile(r"^\s*module:\s*(\S+)\s*$", re.MULTILINE)
_DORMANT_LINE_RE = re.compile(r'^\s*dormant:\s*"(.*)"\s*$', re.MULTILINE)
_HOST_VISIBILITY_BLOCK_RE = re.compile(r"^host_visibility:\s*$", re.MULTILINE)
_HOST_VISIBILITY_ITEM_RE = re.compile(r"^\s*-\s*([a-z0-9][a-z0-9_-]*)\s*$")

# Firing-surface DATA files, relative to --repo-root: a catalogued gate is
# WIRED if it is referenced as a live firing surface in ANY of these (read as
# DATA, never imported / executed).
_FLAVOR_RELATIVE_FILES = (
    Path("nWave") / "flavors" / "atdd_pure.yaml",
    Path("nWave") / "flavors" / "classic.yaml",
)
_LIVE_HOOK_RELATIVE_FILES = (
    Path("scripts") / "shared" / "hook_definitions.py",
    Path("src") / "des" / "adapters" / "drivers" / "hooks" / "subagent_stop_handler.py",
    Path("src") / "des" / "adapters" / "drivers" / "hooks" / "carpaccio_intercept.py",
    Path("src") / "des" / "application" / "feature_end_cycle_service.py",
)


_PROSE_INVOCATION_RE_TEMPLATE = r"\bdes\s+{gate_id}\b"


# ---------------------------------------------------------------------------
# Per-wave dispatch-class table (decision #2, slice-04): a wave's own
# gate_stack.gate-out declaration in nWave/waves/<wave>.yaml is NOT uniformly
# equivalent to "armed" evidence -- only a wave whose gate-out stack is
# DISPATCHED LIVE with real veto power (`_REVIEW_GATE_OUT_WAVES`,
# src/des/application/subagent_stop_service.py) grants that credit.
# "registry-veto"        -- the wave's gate-out stack dispatches live with
#                            real veto power (discuss/design/devops).
# "registry-advisory"     -- the stack is DECLARED in nWave/waves/<wave>.yaml
#                            but no live invoker dispatches it (distill).
# "no-gate-out-stack"     -- the wave genuinely declares an empty gate-out
#                            stack (deliver: gate_stack.gate-out: []).
# A REVIEWED, small table -- never grown implicitly; `wave_dispatch_class_
# divergences` below is the mechanical guard against it silently drifting
# from the live `_REVIEW_GATE_OUT_WAVES` set.
WAVE_DISPATCH_CLASS: dict[str, str] = {
    "discuss": "registry-veto",
    "design": "registry-veto",
    "devops": "registry-veto",
    "distill": "registry-advisory",
    "deliver": "no-gate-out-stack",
}


def wave_dispatch_class_divergences(
    review_gate_out_waves: frozenset[str],
) -> list[str]:
    """Cross-check (decision #2, slice-04): the reviewed ``WAVE_DISPATCH_
    CLASS`` table's ``"registry-veto"`` rows must never silently diverge
    from the LIVE ``_REVIEW_GATE_OUT_WAVES`` set
    (``src/des/application/subagent_stop_service.py``) -- both encode the
    SAME distinction (a wave dispatches its gate-out stack with real veto
    power) from two different places. Returns the sorted list of wave names
    where the two disagree, in EITHER direction: a wave the table marks
    ``"registry-veto"`` but that is absent from ``review_gate_out_waves``,
    or a wave present in ``review_gate_out_waves`` but absent from the table
    entirely, or classified as something other than ``"registry-veto"``.
    An empty list means no divergence.
    """
    offenders: set[str] = set()
    for wave, dispatch_class in WAVE_DISPATCH_CLASS.items():
        declared_veto = dispatch_class == "registry-veto"
        live_veto = wave in review_gate_out_waves
        if declared_veto != live_veto:
            offenders.add(wave)
    for wave in review_gate_out_waves:
        if WAVE_DISPATCH_CLASS.get(wave) != "registry-veto":
            offenders.add(wave)
    return sorted(offenders)


_WAVE_GATE_OUT_KEY_RE = re.compile(
    r"^([ \t]*)gate-out:[ \t]*(\[\s*\])?[ \t]*(?:#.*)?$", re.MULTILINE
)
_WAVE_GATE_OUT_ITEM_RE = re.compile(
    r'^\s*-\s*gate_id:\s*"?([a-z0-9][a-z0-9-]*)"?\s*$', re.MULTILINE
)


def _wave_gate_out_gate_ids(repo_root: Path, wave: str) -> frozenset[str]:
    """Stdlib-only line-oriented reader (F-D-09, no PyYAML) over
    ``nWave/waves/<wave>.yaml``'s ``gate_stack: gate-out:`` block (decision
    #2, slice-04) -- mirrors ``_parse_gate_host_visibility``'s established
    stdlib-regex shape. Returns the declared ``gate_id`` entries under
    ``gate-out:`` ONLY -- a ``gate_id`` declared in the sibling ``gate-in:``
    block never leaks into the result.

    Degrades to an empty frozenset -- NEVER raises -- when the wave file is
    absent, the ``gate-out:`` key is absent, or it is declared explicitly
    empty (``gate-out: []``, mirroring the real ``deliver.yaml`` shape): a
    wave legitimately declaring no gate-out stack is not distinguishable, at
    this reader alone, from a wave whose contract file was not found -- the
    caller's ``WAVE_DISPATCH_CLASS`` lookup is what tells those apart.
    """
    wave_path = repo_root / "nWave" / "waves" / f"{wave}.yaml"
    try:
        raw = wave_path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()

    key_match = _WAVE_GATE_OUT_KEY_RE.search(raw)
    if key_match is None:
        return frozenset()
    if key_match.group(2):  # inline `gate-out: []`
        return frozenset()

    indent = len(key_match.group(1))
    block_lines: list[str] = []
    for line in raw[key_match.end() :].splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            leading = len(line) - len(line.lstrip(" \t"))
            if leading <= indent:
                break
        block_lines.append(line)
    block = "".join(block_lines)
    return frozenset(m.group(1) for m in _WAVE_GATE_OUT_ITEM_RE.finditer(block))


# ---------------------------------------------------------------------------
# 2-hop pre-commit indirection resolver (decision #3, slice-05): a catalogued
# gate's argv literal often lives one hop past `.pre-commit-config.yaml`'s
# `entry:` line -- inside the in-repo WRAPPER SCRIPT that line names, in that
# wrapper's own `subprocess.run([...])` call (the real `run-slice-ats` shape:
# `.pre-commit-config.yaml` -> `scripts/hooks/run_slice_ats_precommit.py` ->
# `subprocess.run([..., "des", "run-slice-ats", ...])`). Capped at exactly
# two STATIC hops, both read as DATA (never imported/executed): a wrapper
# whose own body dispatches dynamically (e.g. an
# `importlib.util.spec_from_file_location` call resolving a path outside
# `repo_root`, mirroring `des declare-done`) has no `subprocess.run([...])`
# literal for this regex to find, so it contributes NOTHING -- never raises,
# never guesses past that hop.
_PRECOMMIT_ENTRY_LINE_RE = re.compile(r"^\s*entry:\s*(.+)$", re.MULTILINE)
_PRECOMMIT_HOOK_ID_LINE_RE = re.compile(r"^\s*-\s*id:\s*(\S+)\s*$", re.MULTILINE)
_PY_SCRIPT_TOKEN_RE = re.compile(r"(\S+\.py)\b")
_SUBPROCESS_RUN_ARGV_RE = re.compile(r"subprocess\.run\(\s*\[(.*?)\]", re.DOTALL)
_LITERAL_ARGV_ELEMENT_RE = re.compile(
    r"""^\s*["']([a-z0-9][a-z0-9_-]*)["']\s*,?\s*$""", re.MULTILINE
)
# The out-of-repo dynamic-dispatch shapes the resolver refuses to chase --
# an `importlib.util.spec_from_file_location(...)` call resolving a path
# outside `repo_root` (mirroring `run_des_declare_done_pre_push.py`).
# Matched textually (never imported/executed) purely to NAME the refused
# target in the INDETERMINATE reason -- neither grants "armed" credit, they
# only make the refusal legible to the reader instead of silent. Two
# distinct shapes are recognized, in order of preference: (1) a quoted
# string path literal passed directly as a `spec_from_file_location(...)`
# argument (a `/` or a `.py` suffix distinguishes the path arg from the
# `name` arg), (2) a `Path.home() / "seg" / "seg" / ...` chain assigned to
# a variable that then flows into the call. Shape (1) is the GENERAL case;
# shape (2) is one specific way of constructing a path that never appears
# as a literal at the call site itself.
_SPEC_FROM_FILE_LOCATION_CALL_RE = re.compile(
    r"spec_from_file_location\((.*?)\)", re.DOTALL
)
_QUOTED_STRING_RE = re.compile(r'["\']([^"\']+)["\']')
_PATH_HOME_CHAIN_RE = re.compile(r'Path\.home\(\)((?:\s*/\s*"[^"]+")+)')
_QUOTED_SEGMENT_RE = re.compile(r'"([^"]+)"')


def _out_of_repo_dispatch_target(script_text: str) -> str | None:
    """Best-effort NAME of the out-of-repo target a dynamic
    ``importlib.util.spec_from_file_location(...)`` dispatch resolves to --
    for the INDETERMINATE reason text only, NEVER to grant ``"armed"``
    credit. Returns ``None`` when neither recognized shape is found -- the
    caller then leaves the gate with the generic zero-evidence reason,
    unchanged from before this detection existed.

    Only proceeds once ``spec_from_file_location(`` genuinely appears in the
    script -- a script with no such call has no dynamic-dispatch target to
    name, regardless of what other quoted strings it happens to contain.
    The path-literal search then runs over the WHOLE script text, not just
    the call's own parentheses: a wrapper commonly assigns the path to a
    variable a line or two earlier (``target_path = "..."; spec_from_file_
    location("name", target_path)``) rather than inlining it at the call
    site -- confirmed missed by an earlier, call-scoped-only version of this
    search (2026-07-31 examine). The ``Path.home()``-chain shape already
    scanned the whole text for the same reason; the plain string-literal
    shape is now symmetric with it.
    """
    if _SPEC_FROM_FILE_LOCATION_CALL_RE.search(script_text) is None:
        return None
    # Try the Path.home()-chain shape FIRST: it is the more precise pattern
    # when present, and its own quoted segments (e.g. a trailing ".py"
    # filename segment) would otherwise be mistaken by the generic scan
    # below for the WHOLE path, losing the joined Path.home()/.../segments
    # value the chain actually resolves to.
    chain_match = _PATH_HOME_CHAIN_RE.search(script_text)
    if chain_match is not None:
        segments = _QUOTED_SEGMENT_RE.findall(chain_match.group(1))
        return str(Path.home().joinpath(*segments))
    for candidate in _QUOTED_STRING_RE.findall(script_text):
        if "/" in candidate or candidate.endswith(".py"):
            return candidate
    return None


# Per-gate "attempted-but-refused" out-of-repo target, keyed by the
# `.pre-commit-config.yaml` hook `id:` (by convention, the catalogued
# gate_id) -- populated as a side effect of the LAST
# `_precommit_ci_indirection_gate_ids` call, so `_render_how` can name the
# specific unreachable target instead of rendering the same generic
# zero-evidence reason for both "never looked" and "looked, hit a real but
# unreachable hop" (negative-space requirement, decision #3). Cleared and
# rebuilt on every call -- never accumulates across repo_roots.
_PRECOMMIT_CI_INDIRECTION_REFUSALS: dict[str, str] = {}


def _precommit_ci_indirection_gate_ids(repo_root: Path) -> frozenset[str]:
    """Stdlib-only 2-hop pre-commit indirection reader (decision #3,
    slice-05). Hop 1: every ``entry:`` line in ``.pre-commit-config.yaml``
    that names an in-repo ``.py`` wrapper script (resolved relative to
    ``repo_root``). Hop 2: that wrapper's OWN text, read as DATA (never
    imported/executed), regex-searched for a ``subprocess.run([...])``
    call's literal, non-interpolated quoted-string argv elements. Returns
    the union of every such literal across every wrapper script found.

    Degrades to an empty frozenset -- NEVER raises -- when
    ``.pre-commit-config.yaml`` or a named wrapper script is missing or
    unreadable, or when a wrapper's own body has no ``subprocess.run([...])``
    literal to find (the out-of-repo ``importlib``-dispatch shape): the
    resolver refuses to chase past a hop it cannot statically resolve,
    rather than raising or fabricating a hit.
    """
    _PRECOMMIT_CI_INDIRECTION_REFUSALS.clear()
    config_path = repo_root / ".pre-commit-config.yaml"
    try:
        config_text = config_path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()

    hits: set[str] = set()
    for entry_match in _PRECOMMIT_ENTRY_LINE_RE.finditer(config_text):
        script_match = _PY_SCRIPT_TOKEN_RE.search(entry_match.group(1))
        if script_match is None:
            continue
        script_path = repo_root / script_match.group(1)
        try:
            script_text = script_path.read_text(encoding="utf-8")
        except OSError:
            continue
        argv_hits: set[str] = set()
        for run_match in _SUBPROCESS_RUN_ARGV_RE.finditer(script_text):
            argv_hits.update(_LITERAL_ARGV_ELEMENT_RE.findall(run_match.group(1)))
        if argv_hits:
            hits.update(argv_hits)
            continue
        # No static subprocess.run(...) literal found -- before giving up,
        # name WHY: an out-of-repo importlib-shaped dynamic-dispatch hop
        # (mirroring `des declare-done`) contributes no hit, but its target
        # is recorded for `_render_how` under the hook's own `id:` (by
        # convention, the catalogued gate_id) so the INDETERMINATE reason
        # can say "traced and refused" instead of "never looked".
        target = _out_of_repo_dispatch_target(script_text)
        if target is None:
            continue
        hook_id_match = None
        for candidate in _PRECOMMIT_HOOK_ID_LINE_RE.finditer(
            config_text, 0, entry_match.start()
        ):
            hook_id_match = candidate
        if hook_id_match is None:
            continue
        _PRECOMMIT_CI_INDIRECTION_REFUSALS[hook_id_match.group(1)] = target
    return frozenset(hits)


def gate_armed_states(
    gates: list[dict],
    *,
    inputs: ArmedStateInputs,
) -> dict[str, str]:
    """The PURE 4-tier trust-policy reducer (the SUT, @contract-shape:pure-
    function; slice-03, decision #1). Over an arbitrary catalogue (a list of
    gate entries), returns the per-gate tier in {"armed", "armed-prose",
    "dormant", "indeterminate"}:

      - "armed" -- an independent CODE-surface hit: a flavor ``gate_id`` row
        OR a live-hook module reference.
      - "armed-prose" -- no CODE hit, but a prose hit (an agent/skill/task
        instructing ``des <gate_id>``) -- a DISTINCT, weaker tier, never
        merged into "armed".
      - "dormant" -- no CODE/PROSE hit, but a non-empty ``dormant:``
        rationale excuses it (Locked Decision L-4, unchanged).
      - "indeterminate" -- everything else, INCLUDING a gate whose only
        evidence is ``host_visibility`` self-declaration (decision #1:
        self-declaration is CLI-existence-only metadata, never sufficient
        wiring proof by itself, registered CLI verb or not) and a gate with
        zero evidence of any kind. A static reducer can never manufacture a
        hard NOT-ARMED verdict (decision #4) -- INDETERMINATE is a WARNING,
        not a hard failure, until a reviewed baseline (slice-07) fail-closes
        it.

    INJECTED inputs (catalogue gates + the ``ArmedStateInputs`` surface-
    evidence bundle) so the reducer can be driven over BOTH the live shipped
    surface (the regression guardrail) AND a synthetic fixture (the
    FLAG+NAME witness) -- distinct-fixture-per-verdict discipline.
    """
    firing_text = inputs.firing_text
    prose_text = inputs.prose_text
    # decision #2 (slice-04): a gate_id declared under a REGISTRY-VETO wave's
    # gate-out hits is a genuine independent CODE hit; the SAME shape of
    # evidence under a registry-advisory (or unclassified -- fail-CLOSED)
    # wave's hits grants no such credit.
    veto_wave_gate_ids: set[str] = set()
    for wave, gate_ids in inputs.wave_gate_out_hits.items():
        if WAVE_DISPATCH_CLASS.get(wave) == "registry-veto":
            veto_wave_gate_ids.update(gate_ids)
    states: dict[str, str] = {}
    for entry in gates:
        gid = entry["gate_id"]
        module = entry.get("module", "")
        code_hit = (
            bool(re.search(rf"gate_id:\s*{re.escape(gid)}\b", firing_text))
            or (bool(module) and module in firing_text)
            or gid in veto_wave_gate_ids
            or gid in inputs.precommit_ci_indirection_hits
        )
        if code_hit:
            states[gid] = "armed"
            continue
        prose_hit = bool(
            prose_text
            and re.search(
                _PROSE_INVOCATION_RE_TEMPLATE.format(gate_id=re.escape(gid)),
                prose_text,
            )
        )
        if prose_hit:
            states[gid] = "armed-prose"
            continue
        rationale = entry.get("dormant")
        if rationale and rationale.strip():  # non-empty rationale -> excused
            states[gid] = "dormant"
            continue
        states[gid] = "indeterminate"
    return states


def coherence_offenders(
    gates: list[dict],
    *,
    inputs: ArmedStateInputs,
) -> list[str]:
    """Backward-compatible view over ``gate_armed_states``: the gate-ids
    resolving to the ``indeterminate`` tier (the authored-but-unwired-or-
    unproven failure class). Preserved unchanged in name and shape so the
    pre-slice-03 fixtures that were never evidenced by ``host_visibility``
    alone keep passing byte-for-byte.
    """
    return [
        gid
        for gid, tier in gate_armed_states(gates, inputs=inputs).items()
        if tier == "indeterminate"
    ]


# --------------------------------------------------------------------------
# Stdlib-only (F-D-09) readers over --repo-root -- no PyYAML dependency,
# parsed with line-oriented regex (mirroring verify_catalog_coherence.py).
# --------------------------------------------------------------------------


def _require_gates_dir(repo_root: Path) -> Path:
    gates_dir = repo_root / "nWave" / "gates"
    if not gates_dir.is_dir():
        raise ArmedStateInputUnavailableError(
            "cannot read the nWave gate catalog directory -- this repo_root "
            "does not look like an nWave-dev checkout"
        )
    return gates_dir


def _parse_catalog_entries(repo_root: Path) -> list[dict]:
    """Stdlib-only line-oriented parse of ``_catalog.yaml`` gate entries.

    Each returned dict carries ``gate_id``, ``module`` (empty string if
    absent), and ``dormant`` (only present when the entry declares a
    rationale). Raises ``ArmedStateCatalogMalformedError`` when the file is
    unreadable, has no top-level ``gates:`` block, or yields zero
    ``- gate_id: <id>`` entries under it.
    """
    catalog_path = repo_root / "nWave" / "gates" / "_catalog.yaml"
    try:
        raw = catalog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArmedStateCatalogMalformedError(
            f"cannot read catalog file {catalog_path}: {exc}"
        ) from exc
    if not _GATES_BLOCK_MARKER_RE.search(raw):
        raise ArmedStateCatalogMalformedError(
            f"{catalog_path} has no top-level 'gates:' block -- malformed catalog"
        )
    starts = list(_GATE_ENTRY_START_RE.finditer(raw))
    if not starts:
        raise ArmedStateCatalogMalformedError(
            f"{catalog_path} declares a 'gates:' block but no gate_id entries "
            "could be parsed from it -- malformed catalog"
        )

    entries: list[dict] = []
    for index, match in enumerate(starts):
        gate_id = match.group(1)
        block_end = starts[index + 1].start() if index + 1 < len(starts) else len(raw)
        block = raw[match.end() : block_end]
        module_match = _MODULE_LINE_RE.search(block)
        entry: dict = {
            "gate_id": gate_id,
            "module": module_match.group(1) if module_match else "",
        }
        dormant_match = _DORMANT_LINE_RE.search(block)
        if dormant_match is not None:
            entry["dormant"] = dormant_match.group(1)
        entries.append(entry)
    return entries


def _parse_gate_host_visibility(repo_root: Path, gate_id: str) -> frozenset[str]:
    """The per-gate file's ``host_visibility`` set (empty if no per-gate file
    or no ``host_visibility:`` block). Stdlib-only line-oriented parse."""
    per_gate_path = repo_root / "nWave" / "gates" / f"{gate_id}.yaml"
    try:
        raw = per_gate_path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    block_match = _HOST_VISIBILITY_BLOCK_RE.search(raw)
    if block_match is None:
        return frozenset()
    values: list[str] = []
    for line in raw[block_match.end() :].splitlines():
        item_match = _HOST_VISIBILITY_ITEM_RE.match(line)
        if item_match is not None:
            values.append(item_match.group(1))
            continue
        if line.strip() == "":
            continue
        break
    return frozenset(values)


def _firing_surface_text(repo_root: Path) -> str:
    """Concatenated DATA of every live firing surface (flavors + live hooks),
    resolved relative to ``repo_root`` -- never the running process's own
    checkout -- so a synthetic fixture repo under a throwaway ``--repo-root``
    is evaluated on its OWN (absent) firing surfaces, never the real one."""
    parts: list[str] = []
    for relative in (*_FLAVOR_RELATIVE_FILES, *_LIVE_HOOK_RELATIVE_FILES):
        candidate = repo_root / relative
        if candidate.exists():
            parts.append(candidate.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


_PROSE_SURFACE_GLOBS = (
    Path("nWave") / "agents" / "*.md",
    Path("nWave") / "skills" / "*" / "SKILL.md",
    Path("nWave") / "tasks" / "nw" / "*.md",
)


def _prose_surface_text(repo_root: Path) -> str:
    """Concatenated DATA of every agent/skill/task prose file under
    ``repo_root`` -- ``nWave/agents/*.md``, ``nWave/skills/*/SKILL.md``, and
    ``nWave/tasks/nw/*.md`` ONLY (slice-06) -- mirroring
    ``_firing_surface_text``'s concatenation-and-search shape. SCOPED to
    exactly these three surface classes: a ``des <verb>`` mention living
    anywhere else (README, docs/, tests/, ADRs) must never be scanned, or
    every gate whose name happens to appear in any prose anywhere would
    falsely resolve ``armed-prose``."""
    parts: list[str] = []
    for pattern in _PROSE_SURFACE_GLOBS:
        for candidate in sorted(repo_root.glob(str(pattern))):
            if candidate.exists():
                parts.append(candidate.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _gate_states_for_repo(repo_root: Path) -> dict[str, str]:
    """Wires the stdlib-only readers into the pure ``gate_armed_states``
    reducer over ``repo_root``.

    Raises ``ArmedStateInputUnavailableError`` (or its
    ``ArmedStateCatalogMalformedError`` subclass) when an input surface is
    missing or malformed -- callers degrade this LOUD, never silently.
    """
    _require_gates_dir(repo_root)
    gates = _parse_catalog_entries(repo_root)
    host_visibility = {
        gate["gate_id"]: _parse_gate_host_visibility(repo_root, gate["gate_id"])
        for gate in gates
    }
    return gate_armed_states(
        gates,
        inputs=ArmedStateInputs(
            firing_text=_firing_surface_text(repo_root),
            host_visibility=host_visibility,
            precommit_ci_indirection_hits=_precommit_ci_indirection_gate_ids(repo_root),
            prose_text=_prose_surface_text(repo_root),
        ),
    )


def _render_how(indeterminate: list[str]) -> list[str]:
    how: list[str] = []
    for gate_id in indeterminate:
        refused_target = _PRECOMMIT_CI_INDIRECTION_REFUSALS.get(gate_id)
        if refused_target is not None:
            how.append(
                f"'{gate_id}' resolves indeterminate -- the 2-hop pre-commit/"
                "CI indirection resolver traced this gate's wrapper script "
                "but refused to chase past a dynamically-dispatched, "
                f"out-of-repo target ({refused_target}): no independent "
                "CODE-surface hit, no prose hit, and no non-empty `dormant: "
                "<rationale>` corroborate it either. Wire it into a real "
                "firing surface, add prose evidence, or annotate "
                f"nWave/gates/{gate_id}.yaml's catalog row with a non-empty "
                "`dormant:` rationale."
            )
            continue
        how.append(
            f"'{gate_id}' resolves indeterminate -- no independent CODE-surface "
            "hit (flavor gate_id row / live-hook module reference) and no "
            "prose hit or non-empty `dormant: <rationale>`. host_visibility "
            "self-declaration alone is no longer sufficient corroboration "
            "(decision #1): wire the gate into a real firing surface, add "
            f"prose evidence, or annotate nWave/gates/{gate_id}.yaml's catalog "
            "row with a non-empty `dormant:` rationale."
        )
    return how


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-gate-armed-state",
        description=(
            "Derive whether each catalogued gate is wired into a real "
            "invocation surface or dormant-excused; name any authored-but-"
            "unwired gate."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        type=str,
        default=".",
        help=("Repo root holding nWave/gates/ (default: cwd)."),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    try:
        states = _gate_states_for_repo(repo_root)
    except ArmedStateInputUnavailableError as exc:
        how = [
            "point --repo-root at a real nWave-dev checkout (it must hold "
            "an nWave/gates/ catalog directory); if you believe you are "
            "already inside one, fix or restore nWave/gates/_catalog.yaml "
            "so it parses with a top-level 'gates:' block and >=1 "
            "'- gate_id: <id>' entry."
        ]
        print(
            f"verify-gate-armed-state: {exc} -- this check only evaluates "
            "an nWave-dev checkout. " + how[0],
            file=sys.stderr,
        )
        verdict = {
            "event": "GateArmedStateChecked",
            "verdict": "indeterminate",
            "reason": f"cannot evaluate gate armed-state: {exc}",
            "how": how,
            "offenders": [],
        }
        print(json.dumps(verdict))
        return 1

    armed = sorted(gid for gid, tier in states.items() if tier == "armed")
    armed_prose = sorted(gid for gid, tier in states.items() if tier == "armed-prose")
    dormant = sorted(gid for gid, tier in states.items() if tier == "dormant")
    indeterminate = sorted(
        gid for gid, tier in states.items() if tier == "indeterminate"
    )

    # Success (exit 0): every catalogued gate resolves to one of the four
    # tiers. An INDETERMINATE population is reported as a WARNING annotation,
    # never a hard failure, until a reviewed baseline (slice-07) fail-closes
    # it -- only a structurally-unreadable input (the except branch above)
    # exits non-zero.
    verdict = {
        "event": "GateArmedStateChecked",
        "verdict": "coherent" if not indeterminate else "indeterminate-present",
        "reason": (
            "every catalogued gate resolved to a known tier; "
            f"{len(indeterminate)} indeterminate (WARNING, not a hard "
            "failure pre-baseline)."
        ),
        "how": _render_how(indeterminate),
        "armed": armed,
        "armed_prose": armed_prose,
        "dormant": dormant,
        "indeterminate": indeterminate,
        "offenders": indeterminate,
    }
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
