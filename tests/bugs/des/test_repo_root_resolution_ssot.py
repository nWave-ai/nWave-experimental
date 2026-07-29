"""Regression AT -- three hand-rolled repo-root resolvers drifted from the
SSOT ``des.domain.repo_path_resolver.resolve_repo_root``.

SSOT (``src/des/domain/repo_path_resolver.py:28``)::

    def resolve_repo_root(override: str | None) -> Path:
        if override:
            return Path(override)
        env = os.environ.get("NWAVE_REPO_ROOT")
        if env:
            return Path(env)
        return Path.cwd()

Three hand-rolled copies drifted from it:

* ``des.cli.mode_locus_gate._repo_root`` (``src/des/cli/mode_locus_gate.py:84``)
* ``des.cli.mode_registry_completeness._repo_root``
  (``src/des/cli/mode_registry_completeness.py:69``, byte-identical body to
  the above)
* ``scripts.cli.cohort_classifier._repo_root``
  (``scripts/cli/cohort_classifier.py:44`` -- takes NO argument; the module
  declares no ``--repo-root``-family flag at all)

TWO DRIFT AXES pinned here:

1. **FALLBACK axis.** The SSOT falls back to ``Path.cwd()``; all three
   copies fall back to ``Path(__file__).resolve().parents[N]``. That
   ancestor walk is anchored to the MODULE's own location, not the process's
   working directory -- so on the INSTALLED layout
   (``~/.claude/lib/python/des/cli/``) it resolves to ``~/.claude/lib``, and
   invoked from an unrelated cwd it silently scans the WRONG tree while
   still exiting 0 (a false all-clear, not a refusal).
2. **GUARD axis.** The SSOT tests ``if override:`` (falsy-safe: ``None`` and
   ``""`` both fall through to env then cwd). ``mode_locus_gate`` /
   ``mode_registry_completeness`` test ``if root_arg is not None:`` instead,
   so an explicit empty string (``--root ''``) short-circuits to a literal
   ``Path('.')`` rather than falling through. (``cohort_classifier`` takes no
   argument, so only axis 1 applies to it.)

The three copies agree with the SSOT on exactly ONE of the three input
classes exercised below (``NWAVE_REPO_ROOT`` set) -- pinned as a
non-regression guard on that already-correct sibling branch (see the
"pin the correct behaviour of neighbouring branches" rule).

RED now: all three resolvers disagree with the SSOT on the unset-env /
empty-string legs. GREEN once the crafter routes ``_repo_root`` in each
module through ``resolve_repo_root``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli import mode_locus_gate, mode_registry_completeness
from des.domain.repo_path_resolver import resolve_repo_root
from scripts.cli import cohort_classifier


# ---------------------------------------------------------------------------
# Axis 1 -- FALLBACK: env unset + no flag must resolve to Path.cwd(), never a
# __file__-relative ancestor walk that is immune to the process's cwd.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_hand_rolled_repo_root_resolution_matches_ssot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``NWAVE_REPO_ROOT`` unset and no flag, every hand-rolled resolver
    must agree with the SSOT's ``Path.cwd()`` fallback -- not a
    ``__file__``-relative ancestor walk that ignores the process cwd
    entirely and, once installed, lands outside any real repo.
    """
    monkeypatch.delenv("NWAVE_REPO_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    expected = resolve_repo_root(None)
    assert expected == tmp_path  # sanity: the SSOT itself follows cwd

    observed = {
        "mode_locus_gate._repo_root(None)": mode_locus_gate._repo_root(None),
        "mode_registry_completeness._repo_root(None)": (
            mode_registry_completeness._repo_root(None)
        ),
        "cohort_classifier._repo_root()": cohort_classifier._repo_root(),
    }
    mismatched = {
        name: str(value) for name, value in observed.items() if value != expected
    }
    assert not mismatched, (
        "WHAT: the hand-rolled repo-root resolvers disagree with the SSOT "
        f"resolve_repo_root(None) == {expected!s} under a bare cwd with no "
        "NWAVE_REPO_ROOT override. WHY: each copy falls back to "
        "Path(__file__).resolve().parents[N] instead of Path.cwd() -- on "
        "the INSTALLED layout (~/.claude/lib/python/des/cli/) that ancestor "
        "walk lands OUTSIDE any real repo, so a scan silently covers the "
        "wrong tree and still exits 0. HOW: route "
        "des.cli.mode_locus_gate._repo_root, "
        "des.cli.mode_registry_completeness._repo_root, and "
        "scripts.cli.cohort_classifier._repo_root through "
        "des.domain.repo_path_resolver.resolve_repo_root. "
        f"Mismatched: {mismatched!r}"
    )


def test_mode_locus_gate_main_scans_the_cwd_tree_not_a_file_relative_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Driving-port-level pin: ``mode-locus-gate`` with no ``--root``/env
    override must scan the CWD's OWN ``nWave/`` tree.

    Pre-fix, ``_repo_root(None)`` resolves ``Path(__file__).resolve()
    .parents[3]`` -- THIS checkout's repo root -- regardless of cwd, so
    invoked from an unrelated directory it silently reports on the wrong
    tree and exits 0 even though the INTENDED target tree (``tmp_path``)
    carries a real offender.
    """
    monkeypatch.delenv("NWAVE_REPO_ROOT", raising=False)
    skills_dir = tmp_path / "nWave" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "offender.md").write_text("mode: classic\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = mode_locus_gate.main([])
    out = capsys.readouterr().out

    assert exit_code == 2, (
        "WHAT: mode-locus-gate must scan the CWD's own nWave/ tree "
        f"({tmp_path}) and find the seeded offender there (exit 2). WHY: "
        "pre-fix, _repo_root() falls back to "
        "Path(__file__).resolve().parents[3] -- this SOURCE checkout's "
        "root -- regardless of cwd, so it scans the wrong tree entirely and "
        "reports a false all-clear. HOW: route _repo_root through "
        "des.domain.repo_path_resolver.resolve_repo_root. "
        f"exit_code={exit_code!r}, stdout={out!r}"
    )
    assert "offender.md" in out, f"expected the seeded offender in stdout, got: {out!r}"


def test_mode_registry_completeness_main_never_reports_a_fabricated_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Driving-port-level pin, content-keyed (not exit-code-keyed): a wrong
    root does not merely change WHETHER the gate reports defects, it can
    make it report FABRICATED ones -- both the correct-root run and the
    wrong-root run can exit 2 with a nonzero defect count, so an exit-code
    parity check alone cannot tell them apart. This asserts on the DEFECT
    TEXT: only the tmp_path fixture's seeded, uniquely-named defect may
    appear, and the verdict must be for exactly that one flavor.

    Pre-fix, ``_repo_root(None)`` ignores cwd and resolves THIS checkout's
    real ``nWave/flavors/`` registry regardless of where the gate is
    invoked from -- so a scan intended for ``tmp_path`` instead reports on
    (and about) an entirely different, unrelated tree.
    """
    monkeypatch.delenv("NWAVE_REPO_ROOT", raising=False)
    flavors_dir = tmp_path / "nWave" / "flavors"
    flavors_dir.mkdir(parents=True)
    (flavors_dir / "fixture-only-flavor.yaml").write_text(
        "display_name: Fixture Only Flavor\n"
        "default: true\n"
        "selection: fixture-only-selection\n"
        "skill_load_set:\n"
        "  - placeholder\n"
        "deliver_phase_shape: fixture-only-phase\n",
        encoding="utf-8",
    )  # deliberately omits `descriptor` -- the one seeded, discriminating defect
    monkeypatch.chdir(tmp_path)

    exit_code = mode_registry_completeness.main([])
    out = capsys.readouterr().out

    assert exit_code == 2, (
        "WHAT: mode-registry-completeness must check the CWD's own "
        f"nWave/flavors/ registry ({tmp_path}) and find the seeded "
        "'missing descriptor' defect there (exit 2). WHY: pre-fix, "
        "_repo_root() falls back to Path(__file__).resolve().parents[3] -- "
        "this SOURCE checkout's root -- regardless of cwd, so it checks a "
        "different registry entirely. HOW: route _repo_root through "
        "des.domain.repo_path_resolver.resolve_repo_root. "
        f"exit_code={exit_code!r}, stdout={out!r}"
    )
    assert "fixture-only-flavor: missing required mode field 'descriptor'" in out, (
        "WHAT: the verdict must name the fixture's OWN seeded defect "
        "('fixture-only-flavor: missing required mode field descriptor'), "
        "not some other tree's defects. WHY: pre-fix, both the correct-root "
        "and wrong-root runs can exit 2 with a nonzero defect count -- exit "
        "code alone cannot distinguish 'checked the right tree' from "
        "'fabricated a verdict about the wrong one', which is exactly why "
        "this drifted unnoticed. HOW: route _repo_root through "
        f"des.domain.repo_path_resolver.resolve_repo_root. stdout={out!r}"
    )
    assert "fixture-only-flavor" in out and "atdd_pure" not in out, (
        "WHAT: the verdict must be about the fixture's 'fixture-only-flavor' "
        "flavor ONLY -- it must NEVER mention this checkout's REAL "
        "'atdd_pure' flavor. WHY: a wrong-root run silently substitutes "
        "THIS checkout's real registry for the intended target, producing a "
        "verdict about a tree the operator never asked to check. "
        f"stdout={out!r}"
    )


# ---------------------------------------------------------------------------
# Axis 2 -- GUARD: an explicit empty-string root must fall through to
# env-then-cwd, not short-circuit to a literal Path('.').
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_empty_string_root_falls_through_to_env_then_cwd_not_a_literal_dot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit empty-string root (a real shape argparse can produce via
    ``--root ''``) must NOT short-circuit -- the SSOT's ``if override:``
    falls through to env then cwd on any falsy value, but
    ``mode_locus_gate`` / ``mode_registry_completeness`` guard with
    ``if root_arg is not None:``, so ``""`` returns a literal ``Path('.')``
    instead of falling through.
    """
    monkeypatch.delenv("NWAVE_REPO_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    expected = resolve_repo_root("")
    assert expected == tmp_path  # sanity: "" is falsy -> env -> cwd on the SSOT

    observed = {
        "mode_locus_gate._repo_root('')": mode_locus_gate._repo_root(""),
        "mode_registry_completeness._repo_root('')": (
            mode_registry_completeness._repo_root("")
        ),
    }
    mismatched = {
        name: str(value) for name, value in observed.items() if value != expected
    }
    assert not mismatched, (
        "WHAT: an empty-string --root/--repo-root must fall through to "
        f"env-then-cwd (SSOT resolve_repo_root('') == {expected!s}), not "
        "short-circuit to a literal Path('.'). WHY: these two copies guard "
        "with `if root_arg is not None:` instead of the SSOT's falsy-safe "
        "`if override:`, so an empty string is treated as an explicit "
        "override. HOW: route both through "
        "des.domain.repo_path_resolver.resolve_repo_root. "
        f"Mismatched: {mismatched!r}"
    )


# ---------------------------------------------------------------------------
# Sibling-branch pin -- the one input class where all four already agree
# must keep agreeing after the fix (no regression on the correct leg).
# ---------------------------------------------------------------------------


def test_env_override_already_agrees_with_ssot_non_regression_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``NWAVE_REPO_ROOT``-set resolution already agrees across all three
    hand-rolled copies and the SSOT -- pinned so the fix does not regress
    the one input class that was already correct."""
    env_root = tmp_path / "env-declared-root"
    env_root.mkdir()
    monkeypatch.setenv("NWAVE_REPO_ROOT", str(env_root))
    monkeypatch.chdir(tmp_path)  # deliberately DIFFERENT from env_root

    expected = resolve_repo_root(None)
    assert expected == env_root

    observed = {
        "mode_locus_gate._repo_root(None)": mode_locus_gate._repo_root(None),
        "mode_registry_completeness._repo_root(None)": (
            mode_registry_completeness._repo_root(None)
        ),
        "cohort_classifier._repo_root()": cohort_classifier._repo_root(),
    }
    mismatched = {
        name: str(value) for name, value in observed.items() if value != expected
    }
    assert not mismatched, (
        "WHAT: NWAVE_REPO_ROOT-set resolution must keep agreeing with the "
        f"SSOT ({expected!s}) after the fix -- this leg already worked "
        f"pre-fix. WHY it would matter: a routing mistake could regress "
        "this working leg while fixing the other two. "
        f"Mismatched: {mismatched!r}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
