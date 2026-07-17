"""Regression AT (RCA-confirmed) -- the walking-skeleton gate hardcodes
``--delta-base-ref`` default to the literal ``"master"``
(``src/des/cli/walking_skeleton_gate.py:95``). On any repository whose
default branch is not literally named ``master`` (``main``, ``trunk``, ...)
``git diff --diff-filter=A --name-only master...HEAD`` exits 128 (unknown
revision) inside ``GitFeatureDeltaAdapter.added_paths`` -> the adapter
degrades to ``Indeterminate("git diff failed (exit 128): ...")`` -> the gate
emits an INDETERMINATE verdict on a feature the gate never actually looked
at. A repo not named ``master`` becomes a second-class citizen of this gate
purely on repo-naming, not on the feature's merits.

Charter (the oracle this file makes executable):
``docs/product/expectations/fix-walking-skeleton-gate-base-ref-agnostic/
a-contributor-on-a-main-default-repo-gets-a-real-walking-skeleton-verdict.md``

The fix that WILL land (so this file RED-fails for the bug, not an
ImportError): a new ``resolve_default_base_ref(repo) -> str | None``
resolver, tiered --

  1. ``git symbolic-ref --short refs/remotes/origin/HEAD`` (the remote's
     declared default branch, e.g. ``origin/trunk``);
  2. a candidate probe over ``origin/master``, ``origin/main``, ``master``,
     ``main`` (in that order);
  3. ``None`` when nothing resolves.

``--delta-base-ref``'s argparse default becomes ``None``; ``main()`` calls
the resolver when the flag is omitted. An unresolvable repo gets a DISTINCT
loud ``Indeterminate`` naming the unresolvable-default-branch cause and the
``--delta-base-ref`` remediation -- never the generic
``"git diff failed (exit 128)"`` plumbing string, and never a silent PASS.

Driving surface (Mandate-13/16, driving-port-only): the REAL walking-skeleton
gate CLI, invoked via the single entry point as a genuine subprocess
(``python -m des.cli walking-skeleton-gate --feature-dir ...
--repo-root <fixture> [--delta-base-ref ...]``) -- the exact shape
``des feature-end`` uses. No production module is imported and called
directly; every assertion reads the printed single-line JSON verdict + the
process exit code, never the SUT's internals.

Each fixture git repo is a throwaway, hermetic, single-commit-or-two
work-tree built fresh under ``tmp_path`` via explicit ``git -C <tmp_path>``-
equivalent subprocess calls (``cwd=`` pinned to the fixture) -- GIT SAFETY:
never a bare ``git config``/``git commit`` against the real project repo,
never any write outside ``tmp_path``.

Author-only: this file authors the regression AT. Implementing
``resolve_default_base_ref`` and wiring it into ``walking_skeleton_gate.py``
/ ``dormant_seam_gate.py`` is the crafter's job (DELIVER), not this file's.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


# Single entry-point invocation form: `python -m des.cli walking-skeleton-gate`
# (the `des <subcommand>` shape). The single-entry-point migration (AT-07)
# forbids every runtime-authoring callsite from using the legacy dotted
# module-form invocation; drive the gate through the entry point instead.
_GATE_ENTRY = ("des.cli", "walking-skeleton-gate")

# The exact substring the CURRENT (buggy) adapter embeds in its Indeterminate
# reason on a git-diff plumbing failure (`GitFeatureDeltaAdapter.added_paths`).
# The fix must NEVER surface this raw plumbing string to the caller when the
# base ref is genuinely resolvable -- and, on genuine unresolvability, must
# replace it with a DISTINCT, self-explaining message (never reuse this one).
_GENERIC_GIT_DIFF_FAILURE_MARKER = "git diff failed (exit 128)"

_FALSE_GREEN_VERDICTS = frozenset({"pass", "not_applicable"})


# --- fixture-repo staging helpers (PRECONDITION setup only) -----------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one `git` command against the throwaway fixture repo at `cwd`.

    Raises on failure (staging must succeed) EXCEPT for the read-only
    `rev-parse`/`remote`/`symbolic-ref --short` query forms the tests use to
    inspect the fixture -- callers that need the output pass the completed
    process back themselves via `_git_output`.
    """
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in fixture staging (exit "
            f"{completed.returncode}): {completed.stderr.strip()[:300]}"
        )
    return completed


def _git_output(cwd: Path, *args: str) -> str:
    """The stdout of a read-only `git` query against the fixture repo."""
    return _git(cwd, *args).stdout.strip()


def _commit(repo: Path, relative_path: str, content: str, message: str) -> None:
    """Write `relative_path` and commit it -- one staging step, one commit."""
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _init_repo(root: Path, *, default_branch: str) -> Path:
    """A fresh git work-tree on `default_branch` with one seed commit."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", default_branch)
    _git(root, "config", "user.email", "regression@nwave.test")
    _git(root, "config", "user.name", "regression")
    _commit(root, "README.md", "seed\n", "chore: seed the fixture repo")
    return root


# --- driving-port invocation (the REAL CLI, over a genuine subprocess) ------


def _run_gate(
    feature_dir: Path,
    repo_root: Path,
    *,
    extra_args: list[str] | None = None,
) -> tuple[int, dict[str, Any], str]:
    """Invoke the real walking-skeleton gate CLI as a subprocess.

    Mirrors `des feature-end`'s own invocation shape via the single entry
    point: `python -m des.cli walking-skeleton-gate --feature-dir ...
    --repo-root ...`. `cwd`
    is pinned to `repo_root` (a real git work-tree carrying its own `.git/`)
    so the import-time freshness gate's `.git/`-adjacency autoskip fires off
    the FIXTURE's own history, independent of wherever this test suite
    happens to run from.

    Returns `(exit_code, parsed_verdict_json, stderr_text)`.
    """
    argv = [
        sys.executable,
        "-m",
        *_GATE_ENTRY,
        "--feature-dir",
        str(feature_dir),
        "--repo-root",
        str(repo_root),
        *(extra_args or []),
    ]
    completed = subprocess.run(argv, cwd=str(repo_root), capture_output=True, text=True)
    return completed.returncode, _last_json_object(completed.stdout), completed.stderr


def _last_json_object(stdout: str) -> dict[str, Any]:
    """The last single-line JSON object the gate printed on stdout.

    Never returns an empty dict silently -- an unparseable/empty stdout is
    itself a test failure (a setup/collection-shaped problem, not the
    business-logic RED this file targets).
    """
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise AssertionError(
        f"gate printed no parseable JSON verdict on stdout: {stdout!r}"
    )


# --- tests --------------------------------------------------------------


def test_main_default_branch_resolves_to_real_verdict(tmp_path: Path) -> None:
    """Positive #1 (the PRIMARY RED) -- a legitimate feature on a
    `main`-default repo gets a real, content-derived verdict, never the
    exit-128 plumbing failure disguised as INDETERMINATE.

    The fixture repo ALSO configures an `origin` remote pointing at an
    unreachable, non-existent URL (never fetched from) -- proving the fix
    resolves the default branch from LOCAL git state only, never dialing the
    network. The feature branch adds an ordinary source file (no
    installable-signature file), so once the base ref resolves the gate's
    OWN delta-derived applicability logic honestly computes NOT_APPLICABLE
    (a genuine, content-driven verdict -- not a build/install PASS, which
    would need the full artifact-build machinery out of scope for this
    regression AT).
    """
    repo = _init_repo(tmp_path / "repo", default_branch="main")
    _git(repo, "remote", "add", "origin", "https://example.invalid/never-fetched.git")
    _git(repo, "checkout", "-q", "-b", "feature/topic")
    _commit(repo, "src/thing.py", "X = 1\n", "feat: ordinary source change")
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()

    exit_code, verdict, _stderr = _run_gate(feature_dir, repo)

    assert verdict.get("verdict") != "indeterminate", (
        "a legitimate feature on a main-default repo must get a real "
        f"verdict, not INDETERMINATE: {verdict}"
    )
    diagnostic = str(verdict.get("diagnostic", ""))
    assert _GENERIC_GIT_DIFF_FAILURE_MARKER not in diagnostic, (
        "the gate must not surface the raw git exit-128 plumbing failure "
        f"once the base ref genuinely resolves: {diagnostic!r}"
    )
    assert verdict.get("verdict") == "not_applicable", verdict
    assert exit_code == 0, (exit_code, verdict)


def test_non_master_non_main_default_branch_never_forces_indeterminate(
    tmp_path: Path,
) -> None:
    """Negative anti-hardcode-swap -- a repo whose default branch is neither
    `master` nor `main` (here: `trunk`), with the remote's `origin/HEAD`
    symref pointing at it, still resolves via the symref tier -- a real
    verdict, never INDETERMINATE. Guards against a lazy `master` -> `main`
    string swap: a fix that only special-cases those two literals has not
    actually fixed the bug, it has moved it.
    """
    repo = _init_repo(tmp_path / "repo", default_branch="trunk")
    base_sha = _git_output(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/trunk", base_sha)
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    _commit(repo, "src/thing.py", "X = 1\n", "feat: ordinary source change")
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()

    exit_code, verdict, _stderr = _run_gate(feature_dir, repo)

    assert verdict.get("verdict") != "indeterminate", (
        "a non-master/non-main default branch resolved via the origin/HEAD "
        f"symref must never force an INDETERMINATE verdict: {verdict}"
    )
    diagnostic = str(verdict.get("diagnostic", ""))
    assert _GENERIC_GIT_DIFF_FAILURE_MARKER not in diagnostic, (
        f"hardcoding master/main only moves the bug, never fixes it: {diagnostic!r}"
    )
    assert verdict.get("verdict") == "not_applicable", verdict
    assert exit_code == 0, (exit_code, verdict)


def test_unresolvable_default_branch_degrades_loud_and_never_silently_passes(
    tmp_path: Path,
) -> None:
    """Negative degrade-LOUD -- a repo with NO origin/HEAD symref and no
    `master`/`main`/`trunk` ref anywhere is genuinely unresolvable. The gate
    must produce a LOUD, DISTINCTLY-named Indeterminate (naming the
    unresolvable-default-branch cause + the `--delta-base-ref` remediation,
    GDP-3) -- never a false-green PASS/NOT_APPLICABLE, and never a bare
    reuse of the generic `"git diff failed (exit 128)"` plumbing string
    (that would mean the fix never actually named the real cause).
    """
    repo = _init_repo(tmp_path / "repo", default_branch="wip-only")
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()

    exit_code, verdict, _stderr = _run_gate(feature_dir, repo)

    assert verdict.get("verdict") == "indeterminate", (
        f"an unresolvable default branch must refuse to decide: {verdict}"
    )
    assert exit_code == 4, (exit_code, verdict)
    diagnostic = str(verdict.get("diagnostic", ""))
    assert diagnostic, (
        "an INDETERMINATE verdict must NAME its cause, never an empty reason"
    )
    assert _GENERIC_GIT_DIFF_FAILURE_MARKER not in diagnostic, (
        "a base-ref-resolution failure must be named DISTINCTLY, never "
        f"reported as the raw git-diff plumbing failure: {diagnostic!r}"
    )
    lowered = diagnostic.lower()
    assert (
        "default branch" in lowered or "base ref" in lowered or "base-ref" in lowered
    ), (
        f"the loud Indeterminate must name the unresolvable-default-branch "
        f"cause: {diagnostic!r}"
    )
    assert "--delta-base-ref" in diagnostic, (
        f"the loud Indeterminate must name the --delta-base-ref remediation "
        f"(GDP-3 what/why/how): {diagnostic!r}"
    )
    assert verdict.get("verdict") not in _FALSE_GREEN_VERDICTS, (
        f"an unresolvable base ref must never be silently waved through: {verdict}"
    )


def test_local_only_clone_without_origin_still_resolves_default_branch(
    tmp_path: Path,
) -> None:
    """Negative no-origin-dependency -- a fully local-only clone (ZERO
    remotes configured, zero network access possible) whose LOCAL default
    branch is `main` still resolves via the local candidate tier -- a real
    verdict, never INDETERMINATE, and no attempt to reach the network
    causes a failure or a hang.
    """
    repo = _init_repo(tmp_path / "repo", default_branch="main")
    remotes = _git_output(repo, "remote")
    assert remotes == "", "fixture sanity: this repo must configure NO remote at all"
    _git(repo, "checkout", "-q", "-b", "feature/topic")
    _commit(repo, "src/thing.py", "X = 1\n", "feat: ordinary source change")
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()

    exit_code, verdict, _stderr = _run_gate(feature_dir, repo)

    assert verdict.get("verdict") != "indeterminate", (
        "a local-only clone with no origin remote must still resolve its "
        f"own local default branch: {verdict}"
    )
    diagnostic = str(verdict.get("diagnostic", ""))
    assert _GENERIC_GIT_DIFF_FAILURE_MARKER not in diagnostic, diagnostic
    assert verdict.get("verdict") == "not_applicable", verdict
    assert exit_code == 0, (exit_code, verdict)


def test_genuine_violation_on_main_default_repo_still_fails_the_gate(
    tmp_path: Path,
) -> None:
    """Negative anti-gaming -- a feature that GENUINELY violates the gate
    (ships a brand-new installable root with no walking-skeleton AT and no
    manifest declaration) must still FAIL on a `main`-default repo, exactly
    as it would on a `master`-default one. The base-ref fix must not become
    a new escape hatch that turns every main-repo verdict green.
    """
    repo = _init_repo(tmp_path / "repo", default_branch="main")
    _git(repo, "checkout", "-q", "-b", "feature/ships-undeclared-installer")
    _commit(
        repo,
        "new_pkg/pyproject.toml",
        '[project]\nname = "added-pkg"\nversion = "0.0.0"\n',
        "feat: ships a new installable without declaring a walking skeleton",
    )
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()

    exit_code, verdict, _stderr = _run_gate(feature_dir, repo)

    assert verdict.get("verdict") == "fail", (
        "a feature that genuinely ships an undeclared installable on a "
        f"main-default repo must FAIL, not be waved through: {verdict}"
    )
    assert exit_code == 1, (exit_code, verdict)
    diagnostic = str(verdict.get("diagnostic", ""))
    assert "new_pkg/pyproject.toml" in diagnostic, diagnostic
    assert verdict.get("verdict") not in (_FALSE_GREEN_VERDICTS | {"indeterminate"}), (
        "the base-ref fix must not let a genuine violation dodge via a "
        f"false green or an indeterminate shrug: {verdict}"
    )


def test_dangling_origin_head_symref_degrades_loud_not_raw_exit128(
    tmp_path: Path,
) -> None:
    """Negative dangling-symref -- `origin/HEAD` is a symref that DECLARES a
    target (`refs/remotes/origin/trunk`) but that target ref was never
    fetched/created (common on shallow / single-branch / partial clones).
    Tier-1 of the resolver must not trust the symref's target BLINDLY: it
    must verify the target actually resolves to a commit before returning
    it. Today's bug -- the resolver returns the symref target unverified,
    `git diff origin/trunk...HEAD` then exits 128, and the gate leaks the
    raw plumbing string. The fix falls through past the dangling symref to
    the candidate probe, then to the DISTINCT loud Indeterminate (never the
    raw exit-128 string) when nothing resolves.
    """
    repo = _init_repo(tmp_path / "repo", default_branch="trunk")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    # Deliberately do NOT create refs/remotes/origin/trunk -- the symref's
    # declared target is left dangling/unresolvable.
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()

    exit_code, verdict, _stderr = _run_gate(feature_dir, repo)

    assert verdict.get("verdict") == "indeterminate", (
        f"a dangling origin/HEAD symref must refuse to decide: {verdict}"
    )
    assert exit_code == 4, (exit_code, verdict)
    diagnostic = str(verdict.get("diagnostic", ""))
    assert _GENERIC_GIT_DIFF_FAILURE_MARKER not in diagnostic, (
        "a dangling origin/HEAD symref target must never surface as the "
        f"raw git-diff exit-128 plumbing string: {diagnostic!r}"
    )
    lowered = diagnostic.lower()
    assert (
        "default branch" in lowered or "base ref" in lowered or "base-ref" in lowered
    ), (
        f"the loud Indeterminate must name the unresolvable-default-branch "
        f"cause: {diagnostic!r}"
    )
    assert "--delta-base-ref" in diagnostic, (
        f"the loud Indeterminate must name the --delta-base-ref remediation "
        f"(GDP-3 what/why/how): {diagnostic!r}"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
