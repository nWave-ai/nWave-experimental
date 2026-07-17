"""des.cli.dormant_seam_gate -- the OSS dormant-seam runtime gate (leg a, slice-01).

THE walking skeleton (DISCUSS D2, DESIGN Per-Slice Companion slice-01): a net-new
effectful ``src/des`` public symbol with NO production call-site is named in a
LOUD INDETERMINATE warning, surfaced through the real gate entry point, WITHOUT
blocking the wave (OSS hooks-only, non-halting -- an ACL over the SF
Published-Language).

Shape mirrors ``des.cli.walking_skeleton_gate`` (DESIGN R7): an importable
``des.cli`` module run as a subprocess (the same shape ``des.cli.walking_skeleton_gate``
uses); ``main(argv)`` entry; a single-line JSON ``DormantSeamVerdict`` on stdout; a loud
human-readable warning on stderr; an exit-code contract.

Arguments::

    --feature-dir <dir>        (required) the feature directory (carried through
                               to the audit-ledger / human surface; the delta is
                               read from the repo, not this dir, for slice-01)
    --repo-root <dir>          (default ".") the repository the net-new delta is
                               measured in (layout-independent invocation)
    --delta-base-ref <ref>     (default: resolved from local git state via
                               resolve_default_base_ref; unresolvable -> a loud
                               cannot-evaluate INDETERMINATE naming this flag)
                               the base ref the net-new delta is measured against
                               (git diff --diff-filter=A {base_ref}...HEAD,
                               behind ChangedSymbolPort)

Exit codes (DESIGN D-5)::

    0  clean (no dormant seam) OR a dormant-seam INDETERMINATE warning
       (NON-HALTING -- the dormant-found case stays exit 0; the warning never
       blocks the wave, KPI-2 guardrail)
    2  malformed input (usage error)
    3  cannot-evaluate (git/parse degrade-LOUD INDETERMINATE -- distinct from the
       dormant-found exit-0 warning)

COMPOSITION ROOT / IMPERATIVE SHELL (DESIGN boundary contract): this module owns
ALL I/O -- the net-new delta read (via ``ChangedSymbolPort``, git behind the
adapter ONLY), the source-surface read (parse the added ``src`` modules for public
effectful symbols + resolve their production call-sites), and the warn emission.
The pure detector ``dormant_seam.detect`` receives plain-data and returns a
verdict; it has no git/IO/``ast`` in its import graph (so "the rule silently
shells out to git" is structurally non-representable). slice-01 parses the added
modules HERE in the shell (added-FILE granularity, DESIGN OQ-1 floor); the
binding-resolved precision (slice-03) and the two escapes (slice-02) layer on
this seam later.

Stdlib-only at import time (the ``des.cli`` bundle-scan contract): the rule + port
imports are stdlib + ``des``; ``ast`` is used HERE in the shell to read the source
surface, never in the rule.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

from des.adapters.driven.git.git_changed_symbol_adapter import GitChangedSymbolAdapter
from des.adapters.driven.git.git_subprocess import resolve_default_base_ref
from des.cli.human_surface import Verdict, print_human_summary
from des.ports.driven_ports.changed_symbol_port import (
    ChangedSymbolPort,
    ChangedSymbols,
    Indeterminate,
)
from des.testarch.rules.dormant_seam import (
    DormantSeamVerdict,
    EffectfulSymbol,
    detect,
)


# Callee shapes that mark a function body as EFFECTFUL (an I/O / mutation side
# effect), generalizing the ``technical_call_smell`` denylist shape to write/IO
# callees (DESIGN D-3). A public function whose body issues one of these performs
# a side effect, so a dormant (uncalled) one is load-bearing-but-unreached -- the
# witness the gate fires on. Matched against the bare attribute/name of the call.
_EFFECTFUL_CALLEE_NAMES: frozenset[str] = frozenset(
    {
        "write_text",
        "write_bytes",
        "write",
        "writelines",
        "mkdir",
        "makedirs",
        "open",
        "unlink",
        "rmtree",
        "remove",
        "rename",
        "replace",
        "touch",
        "run",
        "Popen",
        "check_output",
        "check_call",
        "call",
        "append",  # ledger / audit-event append (an effect on a record store)
    }
)

# The source roots whose added modules are scanned for net-new effectful public
# symbols + production call-sites. The gate evaluates ``src`` production code
# (DISCUSS D4 -- a public effectful ``src/**`` symbol). ``tests/**`` call-sites do
# NOT count as production call-sites (a symbol called only by its own tests is
# still dormant in production).
_SRC_PREFIX = "src/"
_TEST_PREFIX = "tests/"

# The net-new manifest carrying registry registrations (DESIGN D-3 / R6). The gate
# resolves entry-point group bindings from the feature's ADDED ``pyproject.toml``
# SOURCE, NOT ``importlib.metadata.entry_points`` (which reads INSTALLED package
# metadata, not the synthetic net-new delta). A symbol registered under an
# ``[project.entry-points.<group>]`` table is WIRED-by-dispatch -- it has no direct
# source call-site by design, so the resolved registration must enter the call-site
# set BEFORE the detector runs (mirroring the real ``discovery.py`` resolve-and-probe
# seam on source rather than installed metadata).
#
# STDLIB-ONLY (AD-54 DES-bundle invariant): the table is read with a narrow line-scan
# (the same ``re`` line-scan shape ``run_contract_gate._scan_gate_jobs`` and the
# owned-residue marker scan use) -- NO ``tomllib`` / ``tomli`` dependency, so the
# ``src/des/**`` bundle stays stdlib-only and the parser works on Python 3.10.
_PYPROJECT_NAME = "pyproject.toml"

# A TOML section header line: ``[section]`` / ``[ "quoted.dotted" ]``. The entry-
# point section is ``[project.entry-points."<group>"]`` (or unquoted-group form).
# Any header NOT under ``project.entry-points`` (e.g. ``[project]``, ``[build-
# system]``) closes an open entry-point section -- the key=value scan only runs
# while inside an entry-point section.
_TOML_SECTION_HEADER = re.compile(r"^\s*\[(?P<header>[^\]]+)\]\s*$")
_ENTRY_POINTS_SECTION = re.compile(r"^project\.entry-points(?:\.|$)")

# A ``key = "value"`` registration line beneath an entry-point section. The value is
# the ``module.path:Symbol`` reference (single- or double-quoted). A malformed line
# (no quoted value, no ``:Symbol`` suffix) simply does not match and is skipped
# (degrade-soft, never crash).
_ENTRY_POINT_REGISTRATION = re.compile(
    r"""^\s*[^=\s]+\s*=\s*["'](?P<value>[^"']+)["']\s*(?:\#.*)?$"""
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the dormant-seam gate CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="des dormant-seam-gate",
        description=(
            "Warn (non-halting) when a net-new effectful src symbol has no "
            "production call-site (a dormant seam)."
        ),
    )
    parser.add_argument(
        "--feature-dir",
        required=True,
        help="The feature directory under gate (carried to the human surface).",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="The repository root the net-new delta is measured in.",
    )
    parser.add_argument(
        "--delta-base-ref",
        default=None,
        help="The base ref the net-new delta is measured against "
        "(git diff --diff-filter=A {base_ref}...HEAD). Omitted -> resolved "
        "from local git state (resolve_default_base_ref); unresolvable -> a "
        "loud cannot-evaluate INDETERMINATE naming this flag.",
    )
    return parser


def _module_dotted_name(repo_relative_path: str) -> str:
    """The dotted module name of an added ``src/**`` python file.

    ``src/des/probe_dormant_module.py`` -> ``des.probe_dormant_module``;
    ``src/des/pkg/__init__.py`` -> ``des.pkg``. The ``src/`` root and the ``.py``
    suffix are stripped; an ``__init__`` leaf collapses to its package. This is
    the identity stem the symbol's resolved identity is built on.
    """
    without_root = repo_relative_path[len(_SRC_PREFIX) :]
    without_suffix = without_root[: -len(".py")]
    parts = without_suffix.split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_effectful_body(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True iff ``function``'s body issues at least one effectful (I/O) call.

    A call whose bare callee name (the ``Name`` id or the trailing ``Attribute``
    attr) is in ``_EFFECTFUL_CALLEE_NAMES`` -- e.g. ``Path(t).write_text(...)``
    (attr ``write_text``) or ``open(p)`` (name ``open``). A pure function with no
    such call is not effectful and is never a dormant-seam candidate.
    """
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and _callee_leaf(node.func) in (
            _EFFECTFUL_CALLEE_NAMES
        ):
            return True
    return False


def _callee_leaf(func: ast.expr) -> str:
    """The bare leaf callee name of a call: ``foo`` / ``x.foo`` -> ``foo``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _public_effectful_symbols(
    module_dotted: str, tree: ast.Module
) -> list[EffectfulSymbol]:
    """The net-new effectful PUBLIC top-level symbols a module defines.

    A top-level ``def``/``async def`` whose name is public (no leading ``_``) and
    whose body is effectful. The resolved identity is ``{module}.{name}`` -- the
    module-qualified join key the detector matches call-sites against.
    """
    return [
        EffectfulSymbol(identity=f"{module_dotted}.{node.name}", name=node.name)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
        and _is_effectful_body(node)
    ]


# The owned-residue marker syntax DESIGN D-4 line-scans (mirroring the narrow
# ``run_contract_gate._scan_gate_jobs`` line-scan): a trailing line comment of the
# form ``# dormant-ok: <F-id>``. The F-id is free text (an unbounded domain, C6);
# the value is captured verbatim and trailing whitespace trimmed. The marker is a
# COMMENT (discarded by the AST), so it is read from the raw source text -- the
# def-line carrying the marker binds it to that function's identity.
_DORMANT_OK_MARKER = re.compile(r"#\s*dormant-ok:\s*(?P<f_id>\S+)")
_DEF_NAME = re.compile(r"^\s*(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\b")


def _owned_residue_markers(module_dotted: str, source: str) -> dict[str, str]:
    """Map ``{module}.{def_name}`` to the F-id of its ``# dormant-ok:`` marker.

    Scans each line of the module source for a ``def`` whose line carries a
    trailing ``# dormant-ok: <F-id>`` comment, binding the owned-residue F-id to
    that function's module-qualified identity (the same join key the symbol
    surface uses). Only def-lines are considered -- a stray ``# dormant-ok:``
    comment that does not annotate a def binds to nothing.
    """
    markers: dict[str, str] = {}
    for line in source.splitlines():
        def_match = _DEF_NAME.match(line)
        if def_match is None:
            continue
        marker_match = _DORMANT_OK_MARKER.search(line)
        if marker_match is None:
            continue
        identity = f"{module_dotted}.{def_match.group('name')}"
        markers[identity] = marker_match.group("f_id")
    return markers


def _resolved_call_site_identities(
    parsed_modules: dict[str, ast.Module],
    symbols_by_name: dict[str, list[EffectfulSymbol]],
) -> set[str]:
    """The symbol identities reached by a production call-site (binding-resolved).

    For each parsed added module, resolve its ``from <mod> import <name>``
    bindings, then for every call to a bound name in any FUNCTION other than the
    symbol's own defining module, record the resolved identity. A call in the
    symbol's own module does NOT count (the witness contract: a call-site OUTSIDE
    the symbol's own module). slice-01 resolves the direct ``from-import`` +
    bare-name-call shape; entry-point / registry resolution layers on this in
    slice-03.
    """
    called: set[str] = set()
    for caller_module, tree in parsed_modules.items():
        bindings = _import_bindings(tree)
        module_bindings = _module_bindings(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            identity = _resolve_call_identity(
                node.func, bindings, module_bindings, symbols_by_name, caller_module
            )
            if identity is not None:
                called.add(identity)
    return called


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """Map each ``from <mod> import <name>`` local name to its resolved identity.

    ``from des.probe_dormant_module import absorb_ready_refs`` binds the local
    name ``absorb_ready_refs`` to identity ``des.probe_dormant_module.
    absorb_ready_refs`` (an alias ``import x as y`` binds ``y``). Only
    ``from``-imports with an explicit module are resolved (the direct-call wiring
    shape slice-01 exercises).
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                bindings[local] = f"{node.module}.{alias.name}"
    return bindings


def _module_bindings(tree: ast.Module) -> dict[str, str]:
    """Map each plain ``import <module>`` local name to its dotted module name.

    ``from des import probe_escape_module`` binds the local name
    ``probe_escape_module`` to module ``des.probe_escape_module`` (the
    package-relative module import the indirect-wiring floor uses), and
    ``import des.probe_escape_module as m`` binds ``m`` to that module. The
    indirect attribute-call form (``module.symbol()``) resolves the call's value
    name through this map, then joins ``.symbol`` to reach the identity (slice-02
    escape (a) wiring floor).
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name
                bindings[local] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                bindings[local] = f"{node.module}.{alias.name}"
    return bindings


def _resolve_call_identity(
    func: ast.expr,
    bindings: dict[str, str],
    module_bindings: dict[str, str],
    symbols_by_name: dict[str, list[EffectfulSymbol]],
    caller_module: str,
) -> str | None:
    """The candidate symbol identity a call resolves to (outside its own module).

    Two wiring shapes resolve to a production call-site:

      * DIRECT (slice-01) -- a bare-name call (``absorb_ready_refs(...)``)
        resolves through the caller's ``from``-import bindings to a
        module-qualified identity.
      * INDIRECT (slice-02 floor) -- an attribute call on an imported module
        (``probe_escape_module.stage_owned_residue(...)``) resolves the value
        name through the caller's plain-``import`` bindings, then joins ``.attr``.

    In both shapes the identity counts as a production call-site only when it names
    a known net-new symbol DEFINED in a module OTHER than the caller (the witness
    contract). Returns ``None`` otherwise.
    """
    identity = _candidate_identity(func, bindings, module_bindings)
    if identity is None:
        return None
    name = identity.rsplit(".", 1)[-1]
    for symbol in symbols_by_name.get(name, ()):  # name-keyed candidates
        if symbol.identity == identity and not identity.startswith(f"{caller_module}."):
            return identity
    return None


def _candidate_identity(
    func: ast.expr,
    bindings: dict[str, str],
    module_bindings: dict[str, str],
) -> str | None:
    """The module-qualified identity a call's callee binds to (direct or indirect).

    ``Name`` -> resolved through ``from``-import bindings (direct). ``Attribute``
    on a ``Name`` -> the value name resolved through plain-``import`` module
    bindings, joined with the trailing attr (indirect attribute-call wiring).
    """
    if isinstance(func, ast.Name):
        return bindings.get(func.id)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        module = module_bindings.get(func.value.id)
        if module is not None:
            return f"{module}.{func.attr}"
    return None


def _entry_point_call_site_identities(
    delta: ChangedSymbols, repo_root: Path
) -> set[str]:
    """Resolve registry-registered symbols from the feature's net-new pyproject(s).

    For each added ``pyproject.toml`` in the delta, line-scan every
    ``[project.entry-points.<group>]`` section and map each ``module.path:Symbol``
    registration value to the symbol's module-qualified identity
    (``module.path.Symbol``) -- the same join key the source call-site resolution
    builds. A registered symbol is WIRED-by-dispatch: its identity enters the
    resolved call-site set so the detector does not false-flag it dormant.

    Robust by degrade-don't-crash (C6a): an unreadable pyproject, or a registration
    line that does not match the ``key = "module:Symbol"`` shape, is SKIPPED without
    crashing -- a partial manifest never hard-fails the gate (the dormant-found /
    clean lanes stay reachable).
    """
    resolved: set[str] = set()
    for repo_relative in delta.paths:
        if Path(repo_relative).name != _PYPROJECT_NAME:
            continue
        manifest_path = repo_root / repo_relative
        try:
            source = manifest_path.read_text(encoding="utf-8")
        except OSError:
            continue
        resolved.update(_entry_point_identities_from_source(source))
    return resolved


def _entry_point_identities_from_source(source: str) -> set[str]:
    """The resolved identities of every entry-point registration in one manifest.

    Stdlib-only line-scan (no toml parser, AD-54 bundle-stdlib-only): walk the
    source line by line; a section header toggles whether the following
    ``key = "value"`` lines are inside a ``[project.entry-points.<group>]`` section.
    While inside one, each registration value is joined to its identity. A
    non-matching line (blank, comment, malformed registration) is skipped
    (degrade-soft).
    """
    identities: set[str] = set()
    in_entry_points = False
    for line in source.splitlines():
        header = _TOML_SECTION_HEADER.match(line)
        if header is not None:
            in_entry_points = _is_entry_points_header(header.group("header"))
            continue
        if not in_entry_points:
            continue
        registration = _ENTRY_POINT_REGISTRATION.match(line)
        if registration is None:
            continue
        identity = _registration_identity(registration.group("value"))
        if identity is not None:
            identities.add(identity)
    return identities


def _is_entry_points_header(header: str) -> bool:
    """True iff a TOML section header names a ``project.entry-points`` (sub)table.

    The dotted header may quote its trailing group segment
    (``project.entry-points."nwave.lang.adapter"``); the quotes are stripped before
    the prefix match so a quoted-group section is recognised. A header that is not a
    ``project.entry-points`` (sub)table (``[project]``, ``[build-system]``, ...)
    closes any open entry-point section.
    """
    normalized = header.replace('"', "").replace("'", "").strip()
    return _ENTRY_POINTS_SECTION.match(normalized) is not None


def _registration_identity(value: str) -> str | None:
    """Join a ``module.path:Symbol`` registration value to ``module.path.Symbol``.

    Returns ``None`` for a value that is not the canonical ``module:Symbol`` shape
    (exactly one ``:`` with a non-empty module and symbol).
    """
    if value.count(":") != 1:
        return None
    module, symbol = value.split(":")
    if not module or not symbol:
        return None
    return f"{module}.{symbol}"


def _evaluate(
    delta_port: ChangedSymbolPort, repo_root: Path, base_ref: str
) -> DormantSeamVerdict | Indeterminate:
    """Evaluate the dormant-seam gate over the feature's net-new delta.

    Reads the net-new ADDED-files delta via the port (git behind the adapter
    ONLY); a git failure surfaces the LOUD ``Indeterminate`` (degrade-LOUD, never a
    silent empty pass). Parses each added ``src/**`` python module for net-new
    effectful public symbols + resolves their production call-sites, ALSO resolving
    registry registrations from any added ``pyproject.toml`` entry-point group into
    the call-site set (a dispatched symbol with no source call-site is WIRED, not
    dormant), then hands the plain-data surfaces to the pure detector.
    """
    delta = delta_port.changed_symbols(repo_root, base_ref)
    if isinstance(delta, Indeterminate):
        return delta

    parsed = _parse_added_src_modules(delta, repo_root)
    trees = {module_dotted: tree for module_dotted, (tree, _) in parsed.items()}
    symbols = [
        symbol
        for module_dotted, tree in trees.items()
        for symbol in _public_effectful_symbols(module_dotted, tree)
    ]
    symbols_by_name: dict[str, list[EffectfulSymbol]] = {}
    for symbol in symbols:
        symbols_by_name.setdefault(symbol.name, []).append(symbol)

    call_sites = _resolved_call_site_identities(trees, symbols_by_name)
    call_sites |= _entry_point_call_site_identities(delta, repo_root)
    markers: dict[str, str] = {}
    for module_dotted, (_, source) in parsed.items():
        markers.update(_owned_residue_markers(module_dotted, source))
    return detect(symbols, call_sites, markers)


def _parse_added_src_modules(
    delta: ChangedSymbols, repo_root: Path
) -> dict[str, tuple[ast.Module, str]]:
    """Parse every added ``src/**`` python module into ``{dotted_name: (tree, source)}``.

    Skips ``tests/**`` (test call-sites are not production call-sites) and any
    non-``src`` / non-``.py`` path. A module that cannot be read or parsed is
    skipped (slice-01 floor -- a parse failure on a single added file does not
    crash the whole gate; the cannot-evaluate degrade-LOUD lane is the git-level
    delta failure, slice-02+). The raw ``source`` text is retained alongside the
    tree so the owned-residue marker line-scan (escape b -- the marker is a comment
    the AST discards) reuses the single read.
    """
    parsed: dict[str, tuple[ast.Module, str]] = {}
    for repo_relative in delta.paths:
        if not repo_relative.startswith(_SRC_PREFIX) or not repo_relative.endswith(
            ".py"
        ):
            continue
        if repo_relative.startswith(_TEST_PREFIX):
            continue
        source_path = repo_root / repo_relative
        try:
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=repo_relative)
        except (OSError, SyntaxError):
            continue
        parsed[_module_dotted_name(repo_relative)] = (tree, source)
    return parsed


def _emit_verdict(verdict: DormantSeamVerdict, feature_dir: Path) -> None:
    """Emit the single-line JSON verdict (stdout) + a loud human warning (stderr).

    A flagged seam => ``verdict: "indeterminate"`` (the non-halting warn-loud
    verdict) naming every dormant symbol bound to its dormant-semantics ``kind``;
    a clean delta => ``verdict: "clean"`` and NO warning (non-vacuity: the warning
    is call-site-bound, never always-on). An otherwise-dormant seam cleared by a
    ``# dormant-ok: <F-id>`` owned-residue marker (escape b) is recorded in
    ``escapes`` -- naming the symbol AND its owning F-id -- and the F-id is named on
    the loud stderr surface too (never-silent: the suppression is visible to the
    human and machine-findable). The JSON NEVER carries a block/refuse decision
    (KPI-2 guardrail).
    """
    flagged = verdict.flagged
    payload: dict[str, object] = {
        "event": "DormantSeamGateVerdict",
        "verdict": "indeterminate" if flagged else "clean",
        "feature_dir": str(feature_dir),
        "dormant_symbols": [
            {"symbol": seam.symbol, "identity": seam.identity, "kind": seam.kind}
            for seam in verdict.dormant_symbols
        ],
        "escapes": [
            {
                "symbol": escape.symbol,
                "identity": escape.identity,
                "escaped_via": escape.escaped_via,
                "f_id": escape.f_id,
            }
            for escape in verdict.escapes
        ],
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    if verdict.escapes:
        # Never-silent contract: name the owning F-id on the loud surface (the
        # human sees WHICH residue was cleared), but do NOT name the cleared
        # symbol here -- a cleared seam must not appear in the dormant warning
        # surface; its full identity stays in the machine-readable ``escapes``
        # record above.
        owned = ", ".join(
            f"owned residue {escape.f_id} (via {escape.escaped_via})"
            for escape in verdict.escapes
        )
        print_human_summary(
            Verdict.DEGRADED,
            f"dormant seam(s) cleared by owned-residue marker (auditable, never "
            f"silent): {owned}",
        )

    if not flagged:
        return
    named = ", ".join(
        f"{seam.symbol} ({seam.kind})" for seam in verdict.dormant_symbols
    )
    print_human_summary(
        Verdict.DEGRADED,
        f"dormant seam(s) with no production call-site (warn-only, wave not "
        f"blocked): {named}",
    )


def _emit_usage_error(message: str) -> None:
    """Print a usage-error JSON payload to stdout (exit 2)."""
    print(
        json.dumps(
            {"event": "DormantSeamGateUsageError", "reason": message},
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _emit_cannot_evaluate(reason: str, feature_dir: Path) -> None:
    """Emit the cannot-evaluate INDETERMINATE (exit 3) -- delta degrade-LOUD.

    Distinct from the dormant-found exit-0 INDETERMINATE warning: this is the
    git/parse-level degrade-LOUD lane (the net-new delta could not be established).
    The verdict is still ``indeterminate`` (never a fabricated clean pass), with a
    loud human reason on stderr, but exit 3 marks it cannot-evaluate.
    """
    print(
        json.dumps(
            {
                "event": "DormantSeamGateVerdict",
                "verdict": "indeterminate",
                "feature_dir": str(feature_dir),
                "reason": reason,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    print_human_summary(
        Verdict.DEGRADED,
        f"dormant-seam gate could not establish the net-new delta: {reason}",
    )


# The DISTINCT, self-explaining cannot-evaluate reason (GDP-3 what/why/how)
# emitted when `--delta-base-ref` is omitted AND `resolve_default_base_ref`
# cannot resolve the repo's default branch from local git state. Deliberately
# NEVER the generic `GitChangedSymbolAdapter` "git diff failed (exit 128)"
# plumbing string -- a base-ref-resolution failure is a DIFFERENT cause from a
# git-diff failure, and must be named as such.
_UNRESOLVABLE_DEFAULT_BASE_REF_REASON = (
    "the repository's default branch could not be resolved (no "
    "refs/remotes/origin/HEAD symref and no master/main candidate ref found "
    "in local git state) -- pass --delta-base-ref <ref> to name the base ref "
    "the feature's net-new delta is measured against"
)


def main(argv: list[str] | None = None) -> int:
    """Run the dormant-seam gate; return the non-halting exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    feature_dir = Path(args.feature_dir).resolve()
    repo_root = Path(args.repo_root).resolve()

    if not feature_dir.is_dir():
        _emit_usage_error(f"feature dir does not exist: {feature_dir}")
        return 2

    base_ref = args.delta_base_ref
    if base_ref is None:
        base_ref = resolve_default_base_ref(repo_root)
        if base_ref is None:
            _emit_cannot_evaluate(_UNRESOLVABLE_DEFAULT_BASE_REF_REASON, feature_dir)
            return 3

    outcome = _evaluate(GitChangedSymbolAdapter(), repo_root, base_ref)
    if isinstance(outcome, Indeterminate):
        _emit_cannot_evaluate(outcome.reason, feature_dir)
        return 3

    _emit_verdict(outcome, feature_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
