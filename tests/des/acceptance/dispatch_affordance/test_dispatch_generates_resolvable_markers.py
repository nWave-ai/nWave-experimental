"""`des dispatch` must GENERATE an envelope whose markers resolve where they
are CONSUMED -- never one it already knows the hook will refuse, and never one
the operator has to finish by hand.

Two defects, one module (`src/des/cli/dispatch.py`), one shared shape: the
generator holds every fact needed to emit a gate-valid marker block, and emits
an incomplete one anyway.

DEFECT 1 -- a relative `--repo-root` is echoed VERBATIM into DES-PROJECT-ROOT
(GDP-1: intercept BEFORE the effort it guards is spent).
`main()` resolves the project axis through `resolve_repo_root`
(`src/des/domain/repo_path_resolver.py:28`), which returns `Path(override)`
with no absolutization, and `_build_prompt` stamps `str(declared_project_root)`
into the marker (`dispatch.py:1183`). So `des dispatch --repo-root .` exits 0
and prints `<!-- DES-PROJECT-ROOT : . -->`. The refusal arrives only at the
DISPATCH, when `resolve_declared_project_root`
(`src/des/adapters/drivers/hooks/project_root_validator.py:121`) rejects it as
`declared-project-root-not-absolute` -- after the whole prompt (skills, task
context, quality gates) has been assembled and paid for. The question that
refusal asks ("absolute with respect to WHAT?") is entirely answerable at
GENERATION time: the generator knows its own cwd, and `os.path.abspath` is
pure Python + filesystem (no `git`, no external CLI -- the portability
constraint holds).

DEFECT 2 -- the swarm-isolation marker is never generated (GDP-5: cost on the
SYSTEM, not the operator; GDP-2: the affordance belongs at the AUTHORING
surface, not in the refusal). A slice N>1 developed in an isolated parallel
worktree cannot see its predecessor's `SliceCommitVerified` record, so the M8
carpaccio order check blocks it unless the prompt carries
`<!-- DES-SWARM-ISOLATED-DISPATCH : <justification> -->`
(`carpaccio_intercept.py:595`, parsed by `DesMarkerParser` via
`_SWARM_ISOLATED_PATTERN`, `des_marker_parser.py:313`). The mechanism EXISTS
and is correct; `des dispatch` simply has no way to ask for the marker, so the
operator hand-edits every generated prompt.

WHY A FLAG AND NOT AN INFERENCE (the design constraint this AT set pins):
swarm isolation is a FACT THE CALLER DECLARES, never one the tool guesses from
an inferred signal (a `.git` file vs directory, a path shape, an env var).
Gates decide on declared facts; a guessed exemption would silently disarm an
ordering check nobody asked to disarm. So the fix is an explicit
`--swarm-isolated --swarm-justification "<text>"` pair that the generator
TRANSFORMS into the marker -- the declaration stays the operator's, the
assembly cost moves to the system. `--repo-root` is the opposite case: the
value was already declared, so the system normalizes it itself.

Driving surface (driving-port-only, default IN-PROCESS): the REAL `des
dispatch` CLI via `tests/common/in_process_cli.run_cli_in_process` (the
in-process analogue of `python -m des.cli.__main__ dispatch ...`), against
THIS checkout's real `nWave/dispatch/atdd_pure.yaml` + `vendors.yaml` SSOT --
the prompt builder is never mocked.

SECOND-AXIS VERIFICATION (GDP-8 witness corollary -- the checker is not exempt
from the class it checks): "the marker is absolute" is not asserted only by
re-running `os.path.isabs` (the same predicate the fix would use, so a shared
bug would stay invisible). The generated marker value is fed to the REAL
hook-side consumer, `resolve_declared_project_root`, and the assertion is that
it does NOT refuse with `ROOT_NOT_ABSOLUTE`. Likewise the swarm marker is read
back through the REAL `DesMarkerParser` the hook uses, not by substring alone.
The consumer-side assertion is deliberately narrowed to the absoluteness rule
so it stays truthful where `git` is unavailable (rules 3/4 of that validator
shell out to `git` and would then refuse for a DIFFERENT, named reason).

RED-for-right-reason: `--swarm-isolated` is not a recognized option today, so
argparse exits 2 with EMPTY stdout -- the assertions below read that stdout
and fail with a semantic `AssertionError` naming the absent marker, never a
crash or a collection error. The `--repo-root .` cases DO reach prompt
assembly (exit 0) and fail on the marker's VALUE (`.` instead of an absolute
path) -- again a semantic AssertionError.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process

from des.adapters.drivers.hooks.project_root_validator import (
    ROOT_NOT_ABSOLUTE,
    resolve_declared_project_root,
)
from des.domain.des_marker_parser import DesMarkerParser


_REPO_ROOT = Path(__file__).resolve().parents[4]

_PROJECT_ROOT_MARKER = re.compile(r"<!--\s*DES-PROJECT-ROOT\s*:\s*(\S+)\s*-->")

_SWARM_JUSTIFICATION = (
    "slice-03 developed in isolated worktree wt/lane-x; predecessor "
    "SliceCommitVerified lands at integration"
)


def _run_dispatch(argv: list[str], *, cwd: Path = _REPO_ROOT) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process under *cwd*."""
    return run_cli_in_process(["dispatch", *argv], cwd=cwd)


def _base_argv(*, repo_root: str | None = None) -> list[str]:
    argv = [
        "--mode",
        "atdd_pure",
        "--project-id",
        "dispatch-affordance-demo",
        "--slice",
        "slice-03",
        "--phase",
        "A_GREEN",
    ]
    if repo_root is not None:
        argv += ["--repo-root", repo_root]
    return argv


def _project_root_marker_value(stdout: str) -> str | None:
    match = _PROJECT_ROOT_MARKER.search(stdout)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# DEFECT 1 -- DES-PROJECT-ROOT must be generated already-resolvable.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relative_spelling", [".", "./", "./docs/.."])
def test_dispatch_normalizes_a_relative_repo_root_into_an_absolute_marker(
    relative_spelling: str,
) -> None:
    """POSITIVE (the bug, active-RED today): every relative spelling of
    `--repo-root` naming THIS checkout must be stamped as the one absolute
    path it denotes, resolved against the generator's own cwd. Parametrized
    over three spellings that all denote the same tree (bare dot, trailing
    slash, a `..` traversal) so the assertion pins NORMALIZATION, not one
    special-cased literal.
    """
    exit_code, stdout, stderr = _run_dispatch(_base_argv(repo_root=relative_spelling))

    marker_value = _project_root_marker_value(stdout)
    assert marker_value == str(_REPO_ROOT), (
        "expected `des dispatch --repo-root "
        f"{relative_spelling}` (run from {_REPO_ROOT}) to stamp the ABSOLUTE "
        f"project root {str(_REPO_ROOT)!r} into the DES-PROJECT-ROOT marker -- "
        f"got {marker_value!r} (exit_code={exit_code}, stderr={stderr!r}). "
        "The generator echoes --repo-root verbatim today, so the hook refuses "
        "the envelope with 'declared-project-root-not-absolute' only AFTER the "
        "whole prompt has been assembled."
    )


@pytest.mark.parametrize("relative_spelling", [".", "./"])
def test_generated_project_root_marker_passes_the_hook_side_absoluteness_rule(
    relative_spelling: str,
) -> None:
    """POSITIVE (active-RED today), SECOND AXIS: the emitted marker value is
    handed to the REAL hook-side consumer (`resolve_declared_project_root`)
    and must NOT be refused with `declared-project-root-not-absolute`.

    This is the property that actually matters -- an envelope the consumer
    accepts -- checked through the consumer itself rather than by re-running
    the same `isabs` predicate the fix would use.
    """
    exit_code, stdout, stderr = _run_dispatch(_base_argv(repo_root=relative_spelling))

    marker_value = _project_root_marker_value(stdout)
    assert marker_value is not None, (
        "expected a DES-PROJECT-ROOT marker in the generated prompt when "
        f"--repo-root was declared -- got stdout={stdout!r} "
        f"(exit_code={exit_code}, stderr={stderr!r})"
    )

    resolution = resolve_declared_project_root(marker_value, str(_REPO_ROOT))
    assert resolution.reason != ROOT_NOT_ABSOLUTE, (
        "the generated DES-PROJECT-ROOT marker "
        f"{marker_value!r} is refused by the hook-side validator as "
        f"{ROOT_NOT_ABSOLUTE!r}: {resolution.detail}. `des dispatch` must not "
        "emit an envelope it already knows the consuming gate will reject -- "
        "that question is answerable at generation time."
    )


def test_an_absolute_repo_root_is_stamped_unchanged() -> None:
    """CONTROL (GREEN today, must stay GREEN): an already-absolute
    `--repo-root` is carried through byte-identically. Normalization must be a
    widening for relative inputs, never a rewrite of a value the caller
    already declared unambiguously.
    """
    exit_code, stdout, stderr = _run_dispatch(_base_argv(repo_root=str(_REPO_ROOT)))

    assert exit_code == 0, (
        f"an absolute --repo-root must dispatch cleanly -- got {exit_code}, "
        f"stderr={stderr!r}"
    )
    assert _project_root_marker_value(stdout) == str(_REPO_ROOT), (
        f"expected the absolute --repo-root {str(_REPO_ROOT)!r} stamped "
        f"unchanged -- got {_project_root_marker_value(stdout)!r}"
    )


@pytest.mark.negative_at
def test_a_relative_repo_root_never_reaches_the_marker_verbatim() -> None:
    """NEGATIVE AT (the wrong outcome must NOT be produced): `--repo-root .`
    must never yield an envelope that carries the literal `.` and exits 0 in
    silence. Either the value is normalized or the invocation is refused --
    what is forbidden is the third state actually shipped today: a
    successfully generated envelope the consuming gate is already known to
    reject.
    """
    exit_code, stdout, stderr = _run_dispatch(_base_argv(repo_root="."))

    assert "DES-PROJECT-ROOT : ." not in stdout, (
        "the generated prompt carries the relative marker "
        "'<!-- DES-PROJECT-ROOT : . -->' verbatim -- a silently-invalid "
        f"envelope. stdout={stdout!r} (exit_code={exit_code}, "
        f"stderr={stderr!r})"
    )

    marker_value = _project_root_marker_value(stdout)
    if marker_value is not None:
        assert Path(marker_value).is_absolute(), (
            f"a DES-PROJECT-ROOT marker was emitted with the RELATIVE value "
            f"{marker_value!r} -- relative to what is exactly the question the "
            "consuming hook cannot answer."
        )


# ---------------------------------------------------------------------------
# DEFECT 2 -- DES-SWARM-ISOLATED-DISPATCH must be generable, on an explicit
# DECLARATION, never on an inferred signal.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "justification",
    [
        _SWARM_JUSTIFICATION,
        "isolated bugfix worktree: predecessor record folds in at integration",
    ],
)
def test_dispatch_emits_the_swarm_isolated_marker_when_the_caller_declares_it(
    justification: str,
) -> None:
    """POSITIVE (the bug, active-RED today): `--swarm-isolated
    --swarm-justification "<text>"` must put
    `<!-- DES-SWARM-ISOLATED-DISPATCH : <text> -->` in the generated prompt,
    so a slice N>1 dispatched from an isolated worktree passes the M8 order
    check BY CONSTRUCTION instead of being hand-patched by the operator.

    Read back through the REAL `DesMarkerParser` (the hook's own parser), not
    a substring check alone -- the justification must arrive at the consumer
    intact, embedded punctuation included.
    """
    exit_code, stdout, stderr = _run_dispatch(
        [
            *_base_argv(repo_root=str(_REPO_ROOT)),
            "--swarm-isolated",
            "--swarm-justification",
            justification,
        ]
    )

    assert f"DES-SWARM-ISOLATED-DISPATCH : {justification}" in stdout, (
        "expected the generated prompt to carry "
        f"'DES-SWARM-ISOLATED-DISPATCH : {justification}' so "
        "carpaccio_intercept defers the M8 order check to integration -- got "
        f"stdout={stdout!r} (exit_code={exit_code}, stderr={stderr!r}). "
        "`--swarm-isolated` does not exist on `des dispatch` yet."
    )

    parsed = DesMarkerParser().parse(stdout)
    assert parsed.swarm_isolated_justification == justification, (
        "the hook's own DesMarkerParser must read back the EXACT declared "
        f"justification {justification!r} -- got "
        f"{parsed.swarm_isolated_justification!r}"
    )


@pytest.mark.negative_at
def test_dispatch_does_not_emit_the_swarm_isolated_marker_by_default() -> None:
    """NEGATIVE AT (control -- GREEN today, must stay GREEN): an ordinary
    dispatch must NEVER carry the swarm-isolation exemption. The marker
    disarms an ordering check, so it may appear only where the caller declared
    the isolation -- never inferred from cwd shape, worktree layout, or any
    other ambient signal.
    """
    exit_code, stdout, stderr = _run_dispatch(_base_argv(repo_root=str(_REPO_ROOT)))

    assert exit_code == 0, (
        f"a plain dispatch must succeed -- got {exit_code}, stderr={stderr!r}"
    )
    assert "DES-SWARM-ISOLATED-DISPATCH" not in stdout, (
        "an undeclared dispatch must never carry the swarm-isolation "
        f"exemption marker -- got stdout={stdout!r}"
    )
    assert DesMarkerParser().parse(stdout).swarm_isolated_justification is None, (
        "the hook's parser must see NO swarm-isolation justification on an "
        "undeclared dispatch"
    )


@pytest.mark.negative_at
def test_dispatch_rejects_swarm_isolation_declared_without_a_justification() -> None:
    """NEGATIVE AT (active-RED today): `--swarm-isolated` with no
    justification must be REFUSED at generation, not silently emitted as an
    empty marker.

    `DesMarkerParser._SWARM_ISOLATED_PATTERN` requires at least one character,
    so an empty justification fails CLOSED at the hook -- the order check
    blocks with a message about the PREDECESSOR's missing ledger record, which
    names nothing about the malformed declaration. Refusing here, where the
    declaration is authored, is the only place the operator can act on it.
    """
    exit_code, stdout, stderr = _run_dispatch(
        [*_base_argv(repo_root=str(_REPO_ROOT)), "--swarm-isolated"]
    )

    assert exit_code != 0, (
        "declaring swarm isolation without a justification must be refused at "
        f"generation -- got exit_code={exit_code} with stdout={stdout!r}"
    )
    assert "DES-SWARM-ISOLATED-DISPATCH" not in stdout, (
        f"a refused declaration must not leave a marker behind -- got stdout={stdout!r}"
    )
    assert "--swarm-justification" in stderr, (
        "the refusal must name the cure (`--swarm-justification <text>`) -- "
        f"got stderr={stderr!r}"
    )


@pytest.mark.negative_at
def test_dispatch_rejects_a_justification_without_the_isolation_declaration() -> None:
    """NEGATIVE AT (active-RED today): `--swarm-justification` passed WITHOUT
    `--swarm-isolated` must be refused, never silently dropped.

    Silently ignoring it would hand back an envelope missing the exemption the
    operator believes they requested -- the failure then surfaces at the M8
    order check, far from its cause (GDP-6: no silent-wrong).
    """
    exit_code, stdout, stderr = _run_dispatch(
        [
            *_base_argv(repo_root=str(_REPO_ROOT)),
            "--swarm-justification",
            _SWARM_JUSTIFICATION,
        ]
    )

    assert exit_code != 0, (
        "a justification without --swarm-isolated must be refused, not "
        f"dropped -- got exit_code={exit_code} with stdout={stdout!r}, "
        f"stderr={stderr!r}"
    )
    assert "--swarm-isolated" in stderr, (
        "the refusal must name the missing declaration (`--swarm-isolated`) "
        f"-- got stderr={stderr!r}"
    )
