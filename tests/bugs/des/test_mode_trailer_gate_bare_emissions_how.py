"""Regression (GDP-3): three sibling DES gate CLIs emit a bare
INDETERMINATE/usage-error stderr line (WHAT only, no HOW) on their
cannot-evaluate / precondition-failed branches. An operator hitting the
condition today must investigate source to learn the remediation.

Charter: ``docs/product/expectations/fix-mode-trailer-gate-bare-emissions-how/
the-three-mode-trailer-gate-bare-lines-name-how.md``.

Found (bare emission sites, no ``Fix:``/HOW):
  * ``src/des/cli/verify_commit_trailers.py:188`` -- a commit with no
    ``Slice-Id`` trailer emits
    ``INDETERMINATE: no Slice-Id trailer -- nothing to audit`` (exit 7).
  * ``src/des/cli/mode_locus_gate.py:169`` -- a ``--root`` with no ``nWave/``
    tree emits ``mode-locus-gate: no nWave/ tree under root <root>`` (exit 1).
  * ``src/des/cli/mode_registry_completeness.py:229`` -- a ``--root`` with no
    ``nWave/flavors/`` dir emits
    ``mode-registry-completeness: no nWave/flavors/ under root <root>``
    (exit 1).

The fix direction (charter, NOT implemented here): each bare line gains a
plain-text ``Fix:`` remediation -- gate 1 routes to ``des commit-slice``
(stamps the ``Slice-Id`` trailer); gate 2 routes to passing ``--root`` at the
tree containing ``nWave/`` (or running from the repo root); gate 3 routes to
ensuring ``nWave/flavors/`` exists with ``*.yaml`` flavor files.

CRITICAL CONSTRAINT (preserved, do NOT change): each gate's exit code stays
unchanged (7 / 1 / 1) and a condition that does NOT fire emits no spurious
``Fix:`` line.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.{verify_commit_trailers,mode_locus_gate,
mode_registry_completeness}.main()`` CLI drivers, captured via ``capsys`` --
mirrors the sibling regression AT
``tests/bugs/des/test_slice_at_completeness_incomplete_names_how.py`` (the
GDP-3 pattern this one follows).

Fixtures: a real tmp git repo (gate 1, ``verify_commit_trailers`` reads
``Path.cwd()`` -- ``monkeypatch.chdir`` into the fixture repo) and plain tmp
directory trees (gates 2/3, driven purely via ``--root``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.cli.mode_locus_gate import main as mode_locus_gate_main
from des.cli.mode_registry_completeness import main as mode_registry_completeness_main
from des.cli.verify_commit_trailers import main as verify_commit_trailers_main


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _has_fix_marker(text: str) -> bool:
    """True iff *text* carries the ``Fix:`` remediation marker.

    ``Fix:`` is absent from every bare message today -- a stable single
    marker to assert on across all three gates without risking a
    false-positive match against words already present in the bare text
    (e.g. gate 3's bare line already contains the substring ``flavors``).
    """
    return "Fix:" in text


# ===========================================================================
# POSITIVE ATs -- active-RED today (one per gate)
# ===========================================================================


def test_verify_commit_trailers_no_slice_id_names_a_how(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A commit with no ``Slice-Id``/``Step-Id`` trailer stays INDETERMINATE
    (floor intact -- exit 7, already true today). The stderr line must ALSO
    carry a ``Fix:`` HOW routing to ``des commit-slice`` (the tool that
    stamps the trailer) -- this is MISSING today (RED for the right reason:
    a semantic assertion on the absent HOW, not a crash or collection
    error).
    """
    repo = tmp_path / "no_trailer_repo"
    _git_init(repo)
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    commit = _commit_all(
        repo, "initial commit, no trailer\n\nthis body carries no slice trailer\n"
    )

    monkeypatch.chdir(repo)
    exit_code = verify_commit_trailers_main(["--commit", commit])
    stderr = capsys.readouterr().err

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 7, (
        "a commit with no Slice-Id trailer must stay cannot-evaluate "
        f"INDETERMINATE (exit 7) -- got exit_code={exit_code}; stderr={stderr!r}"
    )
    assert "no Slice-Id trailer" in stderr, stderr

    # HOW -- MISSING today. verify_commit_trailers.py:188 emits only
    # `INDETERMINATE: {_NO_SLICE_ID_REASON}`; no Fix: marker exists.
    assert _has_fix_marker(stderr), (
        "the no-Slice-Id INDETERMINATE must carry a `Fix:` HOW routing to "
        f"`des commit-slice` -- stderr carries no remediation: {stderr!r}"
    )
    assert "commit-slice" in stderr, (
        f"the HOW must name the producing tool `des commit-slice` -- stderr={stderr!r}"
    )


def test_mode_locus_gate_no_nwave_tree_names_a_how(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``--root`` with no ``nWave/`` tree stays refused (floor intact --
    exit 1, already true today). The stderr line must ALSO carry a ``Fix:``
    HOW guiding the operator to pass ``--root`` at the tree containing
    ``nWave/`` (or run from the repo root) -- this is MISSING today (RED for
    the right reason).
    """
    root = tmp_path / "no_nwave_root"
    root.mkdir()

    exit_code = mode_locus_gate_main(["--root", str(root)])
    stderr = capsys.readouterr().err

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 1, (
        f"a --root with no nWave/ tree must stay refused (exit 1) -- "
        f"got exit_code={exit_code}; stderr={stderr!r}"
    )
    assert "no nWave/ tree under root" in stderr, stderr

    # HOW -- MISSING today. mode_locus_gate.py:169 emits only
    # `mode-locus-gate: no nWave/ tree under root {root}`; no Fix: marker.
    assert _has_fix_marker(stderr), (
        "the no-nWave/-tree refusal must carry a `Fix:` HOW guiding the "
        "operator to pass --root at the tree containing nWave/ (or run "
        f"from the repo root) -- stderr carries no remediation: {stderr!r}"
    )
    assert "--root" in stderr or "repo root" in stderr, (
        "the HOW must name the concrete remediation (`--root` / repo root) "
        f"-- stderr={stderr!r}"
    )


def test_mode_registry_completeness_no_flavors_dir_names_a_how(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``--root`` with no ``nWave/flavors/`` dir stays refused (floor
    intact -- exit 1, already true today). The stderr line must ALSO carry a
    ``Fix:`` HOW guiding the operator to ensure ``nWave/flavors/`` exists
    with ``*.yaml`` flavor files -- this is MISSING today (RED for the right
    reason).
    """
    root = tmp_path / "no_flavors_root"
    root.mkdir()

    exit_code = mode_registry_completeness_main(["--root", str(root)])
    stderr = capsys.readouterr().err

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 1, (
        f"a --root with no nWave/flavors/ dir must stay refused (exit 1) -- "
        f"got exit_code={exit_code}; stderr={stderr!r}"
    )
    assert "no nWave/flavors/ under root" in stderr, stderr

    # HOW -- MISSING today. mode_registry_completeness.py:229-231 emits only
    # `mode-registry-completeness: no nWave/flavors/ under root {root}`; no
    # Fix: marker exists.
    assert _has_fix_marker(stderr), (
        "the no-nWave/flavors/-dir refusal must carry a `Fix:` HOW guiding "
        "the operator to ensure nWave/flavors/ exists with *.yaml flavor "
        f"files -- stderr carries no remediation: {stderr!r}"
    )
    assert ".yaml" in stderr, (
        f"the HOW must name the concrete *.yaml flavor-file remediation -- "
        f"stderr={stderr!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, green today AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_mode_locus_gate_success_never_carries_a_how(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``--root`` that DOES contain an ``nWave/`` tree holding a REAL
    scanned family (``nWave/skills/``) with a REAL scannable file
    (``.md``) carrying no naked mode literal clears the gate (exit 0,
    ``no naked mode literal found``) with NO spurious ``Fix:`` line -- the
    HOW remediation belongs only to the refusal path, never leaking into a
    passing run. Must stay green both BEFORE and AFTER the fix.

    The fixture MUST contain a genuine scanned family + file -- an
    ``nWave/`` tree with zero families inside it is a scan of NOTHING, not
    a clean tree, and is pinned separately (never as success) by
    ``test_mode_locus_gate_zero_families_is_indeterminate_not_success``
    below.
    """
    root = tmp_path / "clean_root"
    skills_dir = root / "nWave" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "example-skill.md").write_text(
        "# Example Skill\n\n"
        "Does something ordinary. No mode literals appear in this file.\n",
        encoding="utf-8",
    )

    exit_code = mode_locus_gate_main(["--root", str(root)])
    captured = capsys.readouterr()

    assert exit_code == 0, (
        "a --root with a clean nWave/skills/ family must clear (exit 0) -- "
        f"got exit_code={exit_code}; stdout={captured.out!r}; stderr={captured.err!r}"
    )
    assert "no naked mode literal found" in captured.out, captured.out
    assert not _has_fix_marker(captured.out), (
        f"a passing run must never carry a spurious `Fix:` line: {captured.out!r}"
    )
    assert not _has_fix_marker(captured.err), (
        f"a passing run must never carry a spurious `Fix:` line: {captured.err!r}"
    )


@pytest.mark.negative_at
def test_mode_locus_gate_zero_families_is_indeterminate_not_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``--root`` whose ``nWave/`` tree exists but holds NONE of the
    scanned families (``skills``/``agents``/``tasks``) must NEVER report the
    exit-0 clean verdict. Today ``mode_locus_gate.py`` (``_scanned_files``)
    silently ``continue``s past every missing family dir and falls through
    to ``no naked mode literal found`` (exit 0) -- indistinguishable from a
    genuinely scanned-and-clean tree. A scan of zero files is not evidence
    of cleanliness; it must surface as a LOUD, non-zero refusal naming the
    missing families, carrying a ``Fix:`` HOW -- mirroring the sibling
    ``mode-registry-completeness`` gate's ``no flavor files under {dir}``
    branch (``mode_registry_completeness.py:234-242``).

    RED today by design: the crafter, not this AT, makes it GREEN.
    """
    root = tmp_path / "no_families_root"
    (root / "nWave").mkdir(parents=True)

    exit_code = mode_locus_gate_main(["--root", str(root)])
    captured = capsys.readouterr()

    assert exit_code != 0, (
        "a --root whose nWave/ tree holds ZERO of the scanned families "
        "(skills/agents/tasks) must never report the exit-0 clean verdict "
        f"-- got exit_code=0; stdout={captured.out!r}; stderr={captured.err!r}"
    )
    assert "no naked mode literal found" not in captured.out, (
        "zero families scanned is not evidence of a clean tree -- the "
        f"clean-success line must not appear here: stdout={captured.out!r}"
    )
    assert _has_fix_marker(captured.out) or _has_fix_marker(captured.err), (
        "the zero-families refusal must carry a `Fix:` HOW naming the "
        f"missing scanned families -- stdout={captured.out!r}; "
        f"stderr={captured.err!r}"
    )
