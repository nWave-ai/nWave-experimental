"""Mikado D86 -- the skill-normative gate must not hold its own repair hostage.

`des skill-normative-gate` exits INDETERMINATE (4) on any could-not-verify
clause (an absent/undecodable skill asset, or a non-discriminating marker),
and the PreToolUse Write/Edit intercept (`pre_write_handler.py`,
`_evaluate_skill_normative_intercept`) blocks on ANY non-zero exit. One
could-not-verify clause anywhere in the manifest therefore locked EVERY edit
under `nWave/skills/**` -- including the edit that would recreate the very
asset the gate names, and independent of which skill that edit touches.

Measured 2026-07-30 (fixture verbatim in the dispatch brief): a manifest
naming `ghost-skill` (no `SKILL.md`) makes the gate print
`INDETERMINATE: 2 clause(s)` and exit 4; through the real PreToolUse hook, an
Edit to a completely unrelated, healthy skill file is refused with
`gate exit 4`.

THE FIX THAT IS NOT THE FIX. Making INDETERMINATE non-blocking would unblock
every edit by making the gate meaningless -- "I looked and it is bad" and "I
cannot see whether it is bad" are different facts. This suite pins a RATCHET
instead (`des.application.skill_normative_gate_ratchet`, reusing the EXISTING
gate-agnostic `des.domain.gate_ratchet.decide_ratchet` /
`undecidable_baseline` -- the same decision `validate_mikado_tree_coherence.py`
already applies, commit 4a84eba0e): the decision is on the DELTA of the
INDETERMINATE population against HEAD, findings stay printed and counted, and
FAIL keeps blocking absolutely at any count.

Drives the REAL CLI (`des.cli.skill_normative_gate.main`) against REAL git
checkouts built with the `git` binary (a test fixture builder, never a
production dependency -- `src/des/` still reads `.git/` in pure Python, see
`des.adapters.driven.git.git_commit_contents`/`git_commit_reachability`).
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from pathlib import Path

from des.cli import skill_normative_gate as gate_module


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "gate-ratchet@test.local")
    _git(repo, "config", "user.name", "Gate Ratchet Test")
    return repo


def _write_manifest(repo: Path, clauses: list[dict[str, str]]) -> Path:
    manifest_dir = repo / "nWave" / "data"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "skill-normative-clauses.json"
    manifest_path.write_text(json.dumps({"clauses": clauses}))
    return manifest_path


def _write_skill(repo: Path, skill: str, text: str) -> None:
    skill_dir = repo / "nWave" / "skills" / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(text)


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _base_repo(tmp_path: Path) -> tuple[Path, Path]:
    """One healthy clause + two INDEPENDENT ghost clauses, committed at HEAD.

    The ghost clauses each name their OWN skill (`ghost-skill-a` /
    `ghost-skill-b`), never a shared one -- repairing one must not accidentally
    change the other's readability, which a shared asset would (creating the
    file would make BOTH clauses' assets readable at once).
    """
    repo = _init_repo(tmp_path)
    _write_skill(repo, "healthy-skill", "Marker: the healthy clause marker phrase\n")
    manifest = _write_manifest(
        repo,
        [
            {
                "skill": "healthy-skill",
                "clause_id": "c-healthy",
                "marker": "the healthy clause marker phrase",
            },
            {
                "skill": "ghost-skill-a",
                "clause_id": "c-ghost-a",
                "marker": "a ghost marker phrase alpha",
            },
            {
                "skill": "ghost-skill-b",
                "clause_id": "c-ghost-b",
                "marker": "a ghost marker phrase bravo",
            },
        ],
    )
    _commit_all(repo, "baseline: healthy + two independent ghost clauses")
    return repo, manifest


def _run_gate(repo: Path, manifest: Path) -> tuple[int, str]:
    argv = ["--manifest", str(manifest), "--root", str(repo)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = gate_module.main(argv)
    return code, buf.getvalue()


# ---------------------------------------------------------------------------
# (a) growth is REFUSED, and the refusal NAMES the new finding
# ---------------------------------------------------------------------------


def test_adding_a_new_indeterminate_clause_is_refused_and_named(
    tmp_path: Path,
) -> None:
    repo, manifest = _base_repo(tmp_path)
    data = json.loads(manifest.read_text())
    data["clauses"].append(
        {
            "skill": "ghost-skill-c",
            "clause_id": "c-ghost-c",
            "marker": "a ghost marker phrase charlie",
        }
    )
    manifest.write_text(json.dumps(data))

    code, out = _run_gate(repo, manifest)

    assert code == 4, out
    assert "RATCHET BLOCK" in out
    assert "ghost-skill-c" in out
    assert "c-ghost-c" in out
    # the pre-existing findings must not be blamed for the refusal
    assert "Pre-existing findings are not what refused this" in out


# ---------------------------------------------------------------------------
# (b) an unrelated change with an unchanged population is ALLOWED, loudly
# ---------------------------------------------------------------------------


def test_unrelated_change_with_unchanged_population_is_allowed(
    tmp_path: Path,
) -> None:
    repo, manifest = _base_repo(tmp_path)
    (repo / "README.md").write_text("an unrelated change\n")

    code, out = _run_gate(repo, manifest)

    assert code == 0, out
    assert "RATCHET ALLOW" in out
    assert "NOT a clean pass" in out
    # both pre-existing findings still print -- allowed is not silence
    assert "ghost-skill-a" in out
    assert "ghost-skill-b" in out


# ---------------------------------------------------------------------------
# (c) repairing ONE finding while another remains is ALLOWED
# ---------------------------------------------------------------------------


def test_repairing_one_finding_while_another_remains_is_allowed(
    tmp_path: Path,
) -> None:
    repo, manifest = _base_repo(tmp_path)
    _write_skill(repo, "ghost-skill-a", "a ghost marker phrase alpha\n")

    code, out = _run_gate(repo, manifest)

    assert code == 0, out
    assert "RATCHET ALLOW" in out
    # ghost-skill-a is repaired: gone from the printed INDETERMINATE section
    assert "c-ghost-a" not in out
    # ghost-skill-b is untouched: still printed as a live finding
    assert "c-ghost-b" in out


# ---------------------------------------------------------------------------
# (d) a genuine FAIL is never ratcheted, at any count
# ---------------------------------------------------------------------------


def test_genuine_fail_is_never_ratcheted(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write_skill(repo, "healthy-skill", "Marker: the healthy clause marker phrase\n")
    manifest = _write_manifest(
        repo,
        [
            {
                "skill": "healthy-skill",
                "clause_id": "c-healthy",
                "marker": "the healthy clause marker phrase",
            }
        ],
    )
    _commit_all(repo, "healthy baseline")
    _write_skill(repo, "healthy-skill", "marker deleted\n")

    code, out = _run_gate(repo, manifest)

    assert code == 1, out
    assert "FAIL" in out
    assert "RATCHET" not in out


def test_reject_wins_over_the_third_state_d2(tmp_path: Path) -> None:
    """(d2) -- the exact silent-pass the ratchet must never create.

    A genuine reject (a readable skill with its marker deleted) coexists with
    an UNRELATED unreadable clause. Before gate-ratchet-skill-normative this
    combination was already INDETERMINATE (verdict precedence discarded the
    reject); the ratchet's fix made an unchanged INDETERMINATE population
    exit 0 -- which, without this fix, would let ANY reject through as long
    as one unrelated clause anywhere in the manifest is unverifiable. Pins
    the reject-wins rule: exit 1, FAIL printed, the unreadable clause STILL
    printed (GDP-8: the third state reaches the aggregate), and no RATCHET
    line anywhere -- a reject is never ratcheted, at any indeterminate count.
    """
    repo = _init_repo(tmp_path)
    _write_skill(repo, "healthy-skill", "Marker: the healthy clause marker phrase\n")
    manifest = _write_manifest(
        repo,
        [
            {
                "skill": "healthy-skill",
                "clause_id": "c-healthy",
                "marker": "the healthy clause marker phrase",
            },
            {
                "skill": "ghost-skill-a",
                "clause_id": "c-ghost-a",
                "marker": "a ghost marker phrase alpha",
            },
        ],
    )
    _commit_all(repo, "healthy + one unrelated ghost clause")
    _write_skill(repo, "healthy-skill", "marker deleted\n")

    code, out = _run_gate(repo, manifest)

    assert code == 1, out
    assert "FAIL" in out
    assert "c-healthy" in out
    # GDP-8: the third state still reaches the aggregate -- printed, not hidden
    assert "c-ghost-a" in out
    assert "RATCHET" not in out


def test_non_discriminating_marker_does_not_hide_a_reject_elsewhere(
    tmp_path: Path,
) -> None:
    """Item 6: a non-discriminating marker shares the same reject-wins rule.

    Before the fix, `_non_discriminating` short-circuited `evaluate()` before
    `_check_assets` ever ran for ANY clause -- a non-discriminating marker
    anywhere in the manifest hid every reject in the corpus (and, after the
    ratchet, would have made that reject ratchetable). A reject on a
    genuinely discriminating, genuinely readable clause must still win.
    """
    repo = _init_repo(tmp_path)
    _write_skill(repo, "healthy-skill", "Marker: the healthy clause marker phrase\n")
    manifest = _write_manifest(
        repo,
        [
            {
                "skill": "healthy-skill",
                "clause_id": "c-healthy",
                "marker": "the healthy clause marker phrase",
            },
            {
                "skill": "single-token-skill",
                "clause_id": "c-single",
                "marker": "onlyoneword",
            },
        ],
    )
    _commit_all(repo, "healthy + one non-discriminating clause")
    _write_skill(repo, "healthy-skill", "marker deleted\n")

    code, out = _run_gate(repo, manifest)

    assert code == 1, out
    assert "FAIL" in out
    assert "c-healthy" in out
    assert "non-discriminating" in out
    assert "RATCHET" not in out


# ---------------------------------------------------------------------------
# negative: a SWAP (drop one, add a different one) keeps the total flat but
# must still be REFUSED -- a count-only ratchet would let this through
# ---------------------------------------------------------------------------


def test_swap_with_unchanged_total_is_still_refused(tmp_path: Path) -> None:
    repo, manifest = _base_repo(tmp_path)
    data = json.loads(manifest.read_text())
    for clause in data["clauses"]:
        if clause["clause_id"] == "c-ghost-b":
            clause["clause_id"] = "c-ghost-b2"
    manifest.write_text(json.dumps(data))

    code, out = _run_gate(repo, manifest)

    assert code == 4, out
    assert "RATCHET BLOCK" in out
    assert "c-ghost-b2" in out
    # the total is unchanged (2 -> 2): a count-only ratchet would have allowed
    assert "2 before this change, 2 now" in out


# ---------------------------------------------------------------------------
# negative: an unresolvable HEAD refuses the baseline, fail-closed
# ---------------------------------------------------------------------------


def test_unresolvable_head_refuses_the_baseline(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")  # zero commits: HEAD does not resolve
    manifest = _write_manifest(
        repo,
        [
            {
                "skill": "ghost-skill-a",
                "clause_id": "c-ghost-a",
                "marker": "a ghost marker phrase alpha",
            }
        ],
    )

    code, out = _run_gate(repo, manifest)

    assert code == 4, out
    assert "RATCHET CANNOT DECIDE" in out
    assert "HEAD does not resolve" in out
