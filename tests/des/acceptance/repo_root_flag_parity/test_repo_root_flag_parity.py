"""Acceptance tests -- D29 (Mikado): shared repo-root parser across `des` subcommands.

Mikado node D29 -- 46 `des` subcommands each resolve "the target repository
root" through their OWN `add_argument(...)` call, under FIVE mutually-exclusive
canonical names, so the operator must re-learn per command which name governs
it: `--repo` (23), `--repo-root` (14), `--project-root` (4), `--root` (3),
`--repo-dir` (1, `des commit`), plus `des run-slice-ats` which ALREADY aliases
`--repo-root`/`--repo` on one `add_argument` call
(`src/des/cli/run_slice_ats.py:312`) -- the precedent the target design
(`add_repo_root_argument(...)`) generalizes.

The node opened at "3 flags"; the measurement found 5. `--project-dir` is a
SIXTH spelling but is deliberately OUT of scope -- see the comment on
`_CANONICAL_REPO_ROOT_FLAGS`: the same name means a FEATURE directory on
`des log-phase` / `des init-log`. One name, two concepts.

Target behaviour under test: every one of those 46 subcommands accepts the
repo-root value under ALL FIVE names, and the value passed under an alias is
the one actually used (never silently dropped in favour of a default/cwd).

Driving surface (Mandate-13, Layer-2 in-process): the `des` DISPATCHER --
`des.cli.__main__ <subcommand>` via `tests.common.in_process_cli` -- the one
path a real invocation takes, and the ONLY one probed. One cached `--help`
capture per observation point answers all 5 alias questions at once. Forking
a leaf module directly is neither used nor sanctioned; `_observed_help`
records why.

Population is DERIVED, never hardcoded: `_registry_rows()` reads the LIVE
`des.cli.__main__._REGISTRY` tuple (the dispatcher's own SSOT); membership is
decided by an AST scan of each module's OWN `add_argument(...)` call sites for
one of the canonical flag literals (`_derive_repo_root_subcommands`), so the
population tracks the registry when a subcommand is added later.

Authored active-RED (45 of 46 subcommands accepted exactly ONE of the 5 names
and rejected the other 4; `run-slice-ats` accepted 2 of 5): 188 failed / 48
passed. Green since `add_repo_root_argument(...)` landed across the 46.

AT-3 is a REGRESSION PIN, not a RED assertion: `scripts/release/generate_changelog.py`
and `scripts/release/cleanup/cleanup_tags.py` use `--repo` for a GitHub
`owner/repo` SLUG (not a filesystem path) and must NEVER gain a `--repo-root`
alias. Both scripts already do not define `--repo-root` today, so AT-3 is
GREEN at authoring time -- it exists to fail loudly if a future blind sweep
ever touches these two non-`des.cli` scripts.
"""

from __future__ import annotations

import ast
import re
import sys
from functools import cache
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_module_in_process, run_script_in_process


# ---------------------------------------------------------------------------
# Repo-root discovery (walk up from this file to the checkout root).
# ---------------------------------------------------------------------------


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "des" / "cli" / "__main__.py"
        ).is_file():
            return candidate
    raise RuntimeError(
        "MISSING_FUNCTIONALITY: could not locate the nWave-dev checkout root "
        f"by walking up from {here} looking for pyproject.toml + "
        "src/des/cli/__main__.py."
    )


_REPO_ROOT = _find_repo_root()
_SRC_ROOT = _REPO_ROOT / "src"

# `--project-dir` is DELIBERATELY ABSENT from this tuple. It is NOT a synonym
# of the repo root: `des log-phase` joins it with "execution-log.json"
# (`src/des/cli/log_phase.py:167`) and `des init-log` documents it as
# `docs/feature/my-feature/deliver` -- a FEATURE directory. The same spelling
# means the repo root only on `des resolve-workflow-mode`
# (`src/des/cli/resolve_workflow_mode.py:110` -> `resolve_workflow_selection`,
# which reads the `.nwave/` substrate at the root). One name, two concepts:
# aliasing it would conflate them. That divergence is its own defect and is
# NOT what D29 repairs.
_CANONICAL_REPO_ROOT_FLAGS: tuple[str, ...] = (
    "--repo",
    "--repo-root",
    "--repo-dir",
    "--project-root",
    "--root",
)


# ---------------------------------------------------------------------------
# Boundary-safe flag-literal search -- `--repo` is a PREFIX of `--repo-root`
# and of `--repo-path`, so a naive substring search would false-positive
# "--repo" as present merely because "--repo-root" appears in the text. This
# regex requires the match not be immediately preceded/followed by a word
# character or a dash, so "--repo-root" never satisfies a search for
# "--repo" alone.
# ---------------------------------------------------------------------------


def _flag_present(text: str, flag: str) -> bool:
    pattern = re.compile(rf"(?<![\w-]){re.escape(flag)}(?![\w-])")
    return bool(pattern.search(text))


# ---------------------------------------------------------------------------
# Population derivation -- read the LIVE dispatcher registry (never a
# hardcoded name list), then AST-scan each module's own `add_argument(...)`
# call sites for one of the 4 canonical flag literals.
# ---------------------------------------------------------------------------


def _registry_rows() -> tuple[tuple[str, str], ...]:
    """(subcommand-name, module-path) pairs from the live `des` dispatcher SSOT."""
    sys.path.insert(0, str(_SRC_ROOT))
    try:
        from des.cli.__main__ import _REGISTRY
    finally:
        if str(_SRC_ROOT) in sys.path:
            sys.path.remove(str(_SRC_ROOT))
    return tuple((row.name, row.module_path) for row in _REGISTRY)


def _module_source_path(module_path: str) -> Path:
    """``des.cli.X`` -> ``src/des/cli/X.py`` (filesystem-grounded, no import)."""
    parts = module_path.split(".")
    assert parts[:2] == ["des", "cli"], (
        f"expected a des.cli.* module path, got {module_path!r}"
    )
    return _SRC_ROOT.joinpath(*parts).with_suffix(".py")


#: Every call shape through which a module can DECLARE a CLI argument. The
#: population predicate must key on the PROPERTY ("this subcommand declares a
#: repo-root flag"), never on one call SHAPE -- keying on `.add_argument`
#: alone made this derivation collapse to ZERO the moment the D29 fix routed
#: those same declarations through `add_repo_root_argument(parser, ...)`, and
#: an empty population makes the whole parity sweep vacuously SKIP rather
#: than fail. A checker is not exempt from the class it checks.
_ARG_DECLARING_CALL_NAMES = frozenset({"add_argument", "add_repo_root_argument"})


def _declared_argument_string_literals(source_path: Path) -> frozenset[str]:
    """String literals passed positionally to any argument-DECLARING call.

    Covers both the bare ``parser.add_argument("--x", ...)`` shape and the
    shared ``add_repo_root_argument(parser, "--x", ...)`` shape, so the
    population is stable across the D29 migration instead of emptying out
    when the declaration moves behind the helper.

    AST-based (not text/grep): walks the module's own source, so it is immune
    to the flag name appearing in a comment/docstring/help string elsewhere.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    literals: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id
            if isinstance(func, ast.Name)
            else None
        )
        if called not in _ARG_DECLARING_CALL_NAMES:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                literals.add(arg.value)
    return frozenset(literals)


def _derive_repo_root_subcommands() -> tuple[tuple[str, str], ...]:
    """(name, module_path) for every registry row whose module declares >=1
    of the 4 canonical repo-root-family flags via its own `add_argument(...)`.

    This is the population AT-1 sweeps -- derived from the live registry +
    each module's real source, never a hand-maintained list of names.
    """
    derived: list[tuple[str, str]] = []
    for name, module_path in _registry_rows():
        source_path = _module_source_path(module_path)
        if not source_path.is_file():
            continue
        literals = _declared_argument_string_literals(source_path)
        if literals & set(_CANONICAL_REPO_ROOT_FLAGS):
            derived.append((name, module_path))
    return tuple(derived)


_DERIVED_SUBCOMMANDS: tuple[tuple[str, str], ...] = _derive_repo_root_subcommands()


# ---------------------------------------------------------------------------
# Sub-verb descent (probe point A) -- a subcommand built on argparse
# sub-parsers (`parser.add_subparsers(...)` + `<var> = <subparsers>
# .add_parser("verb", ...)`) never renders its per-verb flags on the
# TOP-LEVEL `--help`: argparse's top-level summary shows only the verb names
# (`des feature-end --help` prints `{sign,run,run-batch}` and nothing else --
# confirmed empirically). Probing only the top level is the wrong
# OBSERVATION POINT for such a subcommand, not evidence a flag is
# unsupported. The sub-verb population is DERIVED per module by an AST scan
# (never hardcoded -- `feature-end` has 3 sub-verbs today, a future
# subcommand may have any number), and only a sub-verb whose OWN parser
# declares a repo-root-family flag is probed: a hypothetical sub-verb that
# never touches the repo root owes the property to nobody.
# ---------------------------------------------------------------------------


def _sub_verb_receiver_assignments(source_path: Path) -> tuple[tuple[str, str], ...]:
    """(verb-literal, receiver-var) for every `<var> = <expr>.add_parser("verb", ...)`."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "add_parser"
        ):
            continue
        if not value.args or not (
            isinstance(value.args[0], ast.Constant)
            and isinstance(value.args[0].value, str)
        ):
            continue
        verb = value.args[0].value
        for target in node.targets:
            if isinstance(target, ast.Name):
                pairs.append((verb, target.id))
    return tuple(pairs)


def _receiver_declares_repo_root_flag(source_path: Path, receiver: str) -> bool:
    """True iff `receiver`'s OWN parser declares a canonical repo-root flag,
    via either `receiver.add_argument("--x", ...)` or
    `add_repo_root_argument(receiver, "--x", ...)` -- mirrors
    `_ARG_DECLARING_CALL_NAMES` so a sub-verb migrated behind the shared
    helper is still detected."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id != receiver or func.attr not in _ARG_DECLARING_CALL_NAMES:
                continue
            literal_args = node.args
        elif isinstance(func, ast.Name) and func.id in _ARG_DECLARING_CALL_NAMES:
            if not node.args or not (
                isinstance(node.args[0], ast.Name) and node.args[0].id == receiver
            ):
                continue
            literal_args = node.args[1:]
        else:
            continue
        for arg in literal_args:
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and arg.value in _CANONICAL_REPO_ROOT_FLAGS
            ):
                return True
    return False


def _declaring_sub_verbs(module_path: str) -> tuple[str, ...]:
    """Sub-verb names (derived, never hardcoded) whose OWN parser declares a
    repo-root-family flag. Empty for a flat (non-sub-parser) subcommand --
    the common case, checked cheaply before the AST walk."""
    source_path = _module_source_path(module_path)
    if not source_path.is_file() or "add_subparsers" not in source_path.read_text(
        encoding="utf-8"
    ):
        return ()
    verbs = [
        verb
        for verb, receiver in _sub_verb_receiver_assignments(source_path)
        if _receiver_declares_repo_root_flag(source_path, receiver)
    ]
    return tuple(verbs)


# ---------------------------------------------------------------------------
# Observation reliability (probe point B) -- an EMPTY / non-`usage:` capture
# means the probe never reached argparse; it is NOT evidence the flag is
# unsupported. "Could not observe" is a THIRD verdict and must reach the
# assertion, never be folded into "observed and the flag is missing"
# (GDP-8 arity corollary).
#
# Every capture goes through the dispatcher (`des.cli.__main__ <name>`), the
# one path a real `des <subcommand>` invocation actually takes. See
# `_observed_help` for why the cheaper direct module fork is neither used nor
# sanctioned.
# ---------------------------------------------------------------------------


def _looks_like_help_capture(text: str) -> bool:
    return "usage:" in text.lower() and text.strip() != ""


def _dispatcher_help_capture(name: str, *argv: str) -> str:
    _exit_code, out, err = run_module_in_process(
        "des.cli.__main__", name, *argv, cwd=str(_REPO_ROOT)
    )
    return out + "\n" + err


@cache
def _observed_help(name: str, module_path: str, verb: str | None) -> tuple[str, str]:
    """(text, provenance) for `des <name> [<verb>] --help`.

    ``provenance`` is ``"dispatcher"`` or ``"unobservable"``. Cached -- one
    capture answers every canonical-name question for this (name, verb) at
    once.

    The dispatcher is the ONLY surface probed, deliberately. Forking a leaf
    module (`python -m des.cli.<subcommand_module>`) is BOTH unfaithful and
    forbidden here: unfaithful because no real `des` invocation ever takes
    that path (the single entry point dispatches `<module>.main(argv)` as a
    plain call), and it silently captures NOTHING for any module without an
    `if __name__ == "__main__":` guard -- which is how this probe first
    "observed" that `des feature-open` rejects every alias it in fact
    accepts. Forbidden because `single_entry_point` slice-03 vetoes a
    concrete registered-subcommand module-form reference anywhere in the
    authoring trees; that gate offers a `# des:allow-module-form` sanction
    for hermetic AT driving ports, and this file deliberately does NOT take
    it -- a sanction would have preserved a probe path already proven to
    lie.
    """
    argv: tuple[str, ...] = ((verb,) if verb else ()) + ("--help",)
    dispatched = _dispatcher_help_capture(name, *argv)
    if _looks_like_help_capture(dispatched):
        return dispatched, "dispatcher"
    return dispatched, "unobservable"


def _observation_points(
    name: str, module_path: str
) -> tuple[tuple[str, str, str], ...]:
    """(label, text, provenance) triples AT-1 must check `flag` against.

    A sub-parser-based subcommand yields one point per sub-verb that itself
    declares a repo-root-family flag (probe point A). A flat subcommand
    yields exactly one top-level point.
    """
    verbs = _declaring_sub_verbs(module_path)
    if verbs:
        points = []
        for verb in verbs:
            text, provenance = _observed_help(name, module_path, verb)
            points.append((f"{name} {verb}", text, provenance))
        return tuple(points)
    text, provenance = _observed_help(name, module_path, None)
    return ((name, text, provenance),)


# ---------------------------------------------------------------------------
# Population sanity -- guards the derivation itself. If this ever reports a
# number other than 46, the manual audit this AT was commissioned from is
# FALSIFIED and must be re-examined, not silently absorbed. (It already was
# once: the audit opened at 45 under 4 names, then `--repo-dir` on
# `des commit` turned up as a 5th spelling of the same concept.)
# ---------------------------------------------------------------------------


def test_registry_derives_exactly_46_repo_root_subcommands():
    names = sorted(name for name, _module_path in _DERIVED_SUBCOMMANDS)
    assert len(_DERIVED_SUBCOMMANDS) == 46, (
        "MEASUREMENT_MISMATCH: the AST-derived repo-root-family population "
        f"is {len(_DERIVED_SUBCOMMANDS)}, not the 46 the D29 Mikado node "
        f"measured. Derived names: {names}"
    )


# ---------------------------------------------------------------------------
# AT-1 -- parity, positive, the heart of D29: every derived subcommand
# accepts the repo-root value under EVERY one of the 5 canonical names.
#
# Item axis is the SUBCOMMAND (46 parametrized cases), not the cross product
# of subcommand x name (230). The property under test is PER-SUBCOMMAND
# ("this subcommand accepts the repo root under every canonical name") --
# collapsing the 5 names into one assertion per subcommand keeps that
# property intact as ONE check instead of fragmenting it into 5 independent
# parametrize cases (the `parametrize-inflation` class the project's own
# test-optimizer flags). All 230 name-vs-subcommand verifications still run
# every collection -- they are aggregated per subcommand, not dropped -- and
# a failing subcommand reports EVERY missing alias in one message instead of
# one flag at a time. Collapsed 2026-07-28 (D29 3rd correction round) to keep
# this file's contribution to the `real_repo_scan` xdist_group under the 10%
# suite-share ceiling `tests/bugs/des/test_xdist_group_real_repo_scan_swallows_the_suite.py`
# enforces -- 230 AT-1 items pushed that group to 10.5%; 46 keeps it ~8.7%.
# ---------------------------------------------------------------------------


_AT1_CASES = [
    pytest.param(name, module_path, id=name)
    for name, module_path in _DERIVED_SUBCOMMANDS
]


@pytest.mark.slow
@pytest.mark.parametrize("name, module_path", _AT1_CASES)
def test_subcommand_accepts_repo_root_value_under_every_canonical_alias(
    name: str, module_path: str
) -> None:
    points = _observation_points(name, module_path)

    unobservable = [
        (label, text)
        for label, text, provenance in points
        if provenance == "unobservable"
    ]
    if unobservable:
        detail = "\n---\n".join(f"[{label}]\n{text}" for label, text in unobservable)
        pytest.fail(
            "COULD_NOT_OBSERVE: neither the direct module fork "
            f"(`python -m {module_path}`) nor the dispatcher "
            f"(`python -m des.cli.__main__ {name}`) produced a readable "
            f"`--help` render for {', '.join(label for label, _ in unobservable)}. "
            "This is a PROBE failure -- no observation was made -- and is NOT "
            "evidence that any canonical repo-root flag is unsupported; no "
            "verdict on any flag can be drawn from an absent observation. "
            f"Captured output(s):\n{detail}",
            pytrace=False,
        )

    # Collect ALL missing (flag, label) pairs across all 5 names before
    # failing -- a single assertion names every gap at once rather than
    # stopping at the first missing alias.
    missing_by_flag: dict[str, list[str]] = {}
    for flag in _CANONICAL_REPO_ROOT_FLAGS:
        missing_labels = [
            label
            for label, text, _provenance in points
            if not _flag_present(text, flag)
        ]
        if missing_labels:
            missing_by_flag[flag] = missing_labels

    assert not missing_by_flag, (
        f"`des {name}` ({module_path}) does not recognize the following "
        "repo-root alias(es): "
        + "; ".join(
            f"{flag!r} missing on {', '.join(labels)}"
            for flag, labels in missing_by_flag.items()
        )
        + " -- add_repo_root_argument(...) has not been applied there yet. "
        "Captured --help output(s):\n"
        + "\n---\n".join(f"[{label}]\n{text}" for label, text, _ in points)
    )


# ---------------------------------------------------------------------------
# AT-2 -- negative (`_never_`): an accepted alias must not be silently
# ignored. Each probe passes the repo-root value under a NON-canonical alias
# pointing at a tmp_path that is deliberately NOT a valid target for that
# gate, and asserts the resulting verdict is the specific DOMAIN verdict that
# names THAT tmp_path -- never a fallback default/cwd, and never argparse's
# OWN "unrecognized arguments: --flag <value>" usage error, which echoes the
# raw token list (flag AND value) VERBATIM and would otherwise make
# `str(empty_dir) in combined` a false positive for an alias that is not
# recognized at all (confirmed empirically: `mode-locus-gate --repo-root
# <path>` today prints `error: unrecognized arguments: --repo-root <path>` --
# the exact path substring, from a parser that never even looked at it). The
# assertion below is deliberately three-part so it can ONLY be satisfied by
# genuine domain processing of the aliased value:
#   1. the exit code is the DOMAIN exit code (not argparse's usage-error 2),
#   2. the domain's own diagnostic PREFIX names the passed directory, and
#   3. argparse's "unrecognized arguments" echo is ABSENT.
# A parser that registers the alias but reads a DIFFERENT `dest` (silently
# falling back to a default/cwd) would fail assertion 2 even after alias
# recognition ships, so this remains a real regression guard going forward.
# ---------------------------------------------------------------------------


def test_mode_locus_gate_alias_value_reaches_the_domain_verdict_not_cwd(
    tmp_path,
) -> None:
    empty_dir = tmp_path / "not-an-nwave-checkout"
    empty_dir.mkdir()

    exit_code, out, err = run_module_in_process(
        "des.cli.mode_locus_gate",
        "--repo-root",  # non-canonical alias for mode-locus-gate's `--root`
        str(empty_dir),
        cwd=str(_REPO_ROOT),
    )
    combined = out + err

    assert "unrecognized arguments" not in combined, (
        "ALIAS_NOT_RECOGNIZED: argparse rejected --repo-root outright (its "
        f"own usage-error echo, not domain processing) -- output:\n{combined}"
    )
    assert exit_code == 1 and f"no nWave/ tree under root {empty_dir}" in combined, (
        "SILENT_ALIAS_DROP: the --repo-root alias's value did not reach "
        f"mode-locus-gate's domain verdict for {empty_dir} (exit {exit_code}). "
        f"Output:\n{combined}"
    )


def test_mode_registry_completeness_alias_value_reaches_the_domain_verdict_not_cwd(
    tmp_path,
) -> None:
    empty_dir = tmp_path / "not-an-nwave-checkout"
    empty_dir.mkdir()

    exit_code, out, err = run_module_in_process(
        "des.cli.mode_registry_completeness",
        "--project-root",  # non-canonical alias for this gate's `--root`
        str(empty_dir),
        cwd=str(_REPO_ROOT),
    )
    combined = out + err

    assert "unrecognized arguments" not in combined, (
        "ALIAS_NOT_RECOGNIZED: argparse rejected --project-root outright "
        f"(its own usage-error echo, not domain processing) -- output:\n{combined}"
    )
    assert exit_code == 1 and f"no nWave/flavors/ under root {empty_dir}" in combined, (
        "SILENT_ALIAS_DROP: the --project-root alias's value did not reach "
        f"mode-registry-completeness's domain verdict for {empty_dir} "
        f"(exit {exit_code}). Output:\n{combined}"
    )


def test_wave_clear_alias_value_reaches_the_domain_verdict_not_cwd(tmp_path) -> None:
    empty_dir = tmp_path / "no-wave-floor-here"
    empty_dir.mkdir()

    exit_code, out, err = run_module_in_process(
        "des.cli.wave_clear",
        "--reason",
        "D29 AT-2 probe -- alias-not-silently-ignored",
        "--repo",  # non-canonical alias for wave-clear's `--project-root`
        str(empty_dir),
        cwd=str(_REPO_ROOT),
    )
    combined = out + err

    assert "unrecognized arguments" not in combined, (
        "ALIAS_NOT_RECOGNIZED: argparse rejected --repo outright (its own "
        f"usage-error echo, not domain processing) -- output:\n{combined}"
    )
    assert exit_code == 0 and f"no wave floor present in {empty_dir}" in combined, (
        "SILENT_ALIAS_DROP: the --repo alias's value did not reach "
        f"wave-clear's NOOP_SUCCESS verdict for {empty_dir} (exit {exit_code}). "
        f"Output:\n{combined}"
    )


# ---------------------------------------------------------------------------
# AT-3 -- negative (exclusion pin, REGRESSION not RED): these two release
# scripts use `--repo` for a GitHub `owner/repo` slug, never a filesystem
# path, and must NEVER gain a `--repo-root` alias. Both already lack
# `--repo-root` today, so this test is GREEN at authoring time -- it exists
# to catch a future blind repo-root-parser rollout that mistakenly touches
# a non-`des.cli` script.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script_relpath",
    [
        "scripts/release/generate_changelog.py",
        "scripts/release/cleanup/cleanup_tags.py",
    ],
)
def test_release_repo_slug_scripts_never_gain_a_repo_root_alias(
    script_relpath: str,
) -> None:
    script_path = _REPO_ROOT / script_relpath
    assert script_path.is_file(), f"expected script at {script_path}"

    _exit_code, out, err = run_script_in_process(
        script_path, "--help", cwd=str(_REPO_ROOT)
    )
    combined = out + err

    assert _flag_present(combined, "--repo"), (
        f"{script_relpath} was expected to keep its `--repo` GitHub-slug "
        f"flag; --help output was:\n{combined}"
    )
    assert not _flag_present(combined, "--repo-root"), (
        f"REGRESSION: {script_relpath} gained a `--repo-root` alias for its "
        "`--repo` GitHub owner/repo SLUG flag -- these are semantically "
        "different (slug vs filesystem path) and must never be merged. "
        f"--help output was:\n{combined}"
    )
