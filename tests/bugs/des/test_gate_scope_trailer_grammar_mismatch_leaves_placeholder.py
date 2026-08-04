"""Regression: `des commit-slice` writes the `Gate-Scope:` trailer with a
LOOSE grammar and reads it back with a STRICT one -- the two diverge and
produce a silent-wrong commit that LOOKS well-formed but attests nothing.

Charter: ``docs/product/expectations/fix-gate-scope-constants-dedup/``.

Sites (``src/des/cli/commit_slice.py`` / ``src/des/cli/run_contract_gate.py``):

* ``commit_slice._GATE_SCOPE_LINE_RE = re.compile(r"^Gate-Scope:.*$", ...)``
  -- LOOSE, matches ANY ``Gate-Scope:`` line regardless of payload shape.
  Used by ``_amend_trailer`` (``count=1``) to rewrite the placeholder onto
  the real committed-scope digest after the first commit lands.
* ``run_contract_gate._GATE_SCOPE_TRAILER_RE =
  re.compile(r"^Gate-Scope:\\s*([0-9a-f]{64})\\s*$")`` -- STRICT, requires a
  64-hex payload. Used by ``extract_gate_scope``, which in turn backs the
  ``commit_slice.main()`` pre-flight guard that refuses a caller-supplied
  ``--message`` already carrying a ``Gate-Scope:`` trailer.

Repro (ORIGINAL diagnosis, historical -- see the 2026-08-04 status note
below the two amend tests for the current, correct behaviour): a
caller-supplied ``--message`` body containing a NON-hex ``Gate-Scope:
pending`` line was NOT caught by the pre-flight guard (the guard read
STRICT: ``extract_gate_scope`` returns ``None`` for a non-hex payload, so
the "already carries a trailer" refusal never fired). The message proceeded
to ``_commit_with_placeholder``, which APPENDS the real all-zero placeholder
trailer onto the SAME message -- the commit carried two ``Gate-Scope:``
lines, the caller's fake one first and the mechanical placeholder second.
``_amend_trailer`` then substituted the placeholder onto the digest using
the LOOSE regex with ``count=1``: the substitution hit the FIRST matching
line (the caller's fake ``pending`` line, since it also matched the loose
``.*`` payload), rewriting THAT line to the real digest -- and left the
mechanically appended all-zero placeholder as the trailer block's LAST, and
therefore authoritative, ``Gate-Scope:`` line. The shipped commit looked
well-formed (every ``Gate-Scope:`` line matched the STRICT 64-hex shape) yet
its final mechanical trailer attested NOTHING: it was still the placeholder.

**Status (2026-08-04): this exact adversarial vehicle is now unreachable.**
Defect C (see the "Defect C" section further down) widened the pre-flight
guard to refuse ANY caller-supplied ``Gate-Scope:``-prefixed line, anywhere
in ``--message``, before any git mutation happens -- so a caller can no
longer smuggle a fake ``Gate-Scope: pending`` line into a commit at all. The
two amend tests immediately below were rewritten accordingly: they now
drive a LEGITIMATE (clean) ``--message`` through ``commit_slice.main()`` and
assert the surviving property the charter's Intent still requires -- the
all-zero placeholder must never survive as the value baked into a real,
final trailer -- via the one route still reachable now that the adversarial
one is correctly refused upstream.

Driving surface (Mandate-13, driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.commit_slice.main()`` CLI driver, captured via ``capsys``.
The commit's resulting message is read back with a real ``git log -1
--format=%B`` -- never hand-reconstructed -- so the assertion exercises the
actual production regex behaviour, not a restated copy of it.

Fixture reuse (do NOT hand-roll a new harness): ``provision_commit_slice_repo``
(the shared git-repo-template helper) + the AT-EXEMPT ``@prefactoring`` lane
(``LANE_PROFILES["prefactoring"]``) -- the SAME cheapest E1+E2+E3-clearing
shape already proven GREEN by
``tests/bugs/des/test_commit_slice_writes_verified_record.py``, reused
verbatim here so this AT's only new variable is the crafted ``--message``.

Two EXAMINE-found extensions (2026-08-03), driven through
``des.cli.run_contract_gate`` on real temporary git repos:

* Defect A -- ``extract_gate_scope`` (``run_contract_gate.py``) never checks
  WHERE a ``Gate-Scope:`` line sits: it returns the FIRST line in the whole
  commit message matching the STRICT 64-hex grammar, wherever it is. A
  trailer buried mid-body with non-trailer prose following it is therefore
  wrongly treated as the real trailer, and two ``Gate-Scope:`` lines in one
  message wrongly resolve via first-match instead of refusing an ambiguous
  commit. Measured on this repo's own 4000-commit history: 564 commits carry
  a ``Gate-Scope:`` line, 17 have non-trailer text AFTER the last one and
  ALL 17 are ``(cherry picked from commit <sha>)`` (git's own
  ``cherry-pick -x`` tail) -- those must keep verifying; only 1
  (``9ab9fa580aa7``) carries two ``Gate-Scope:`` lines and must NOT verify.
* Defect B -- ``run-contract-gate --verify-gate-scope`` on a nonexistent
  ``--repo`` raises a bare ``FileNotFoundError`` from
  ``test_runner_port._unrecognized_reason`` (``target_root.iterdir()`` on a
  path that does not exist), instead of a structured refusal like the
  sibling ``des verify-slice-commit`` already produces on the identical
  input.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from des.cli.commit_slice import main as commit_slice_main
from des.cli.run_contract_gate import main as run_contract_gate_main
from tests.des._helpers.commit_slice_git_template import provision_commit_slice_repo


_FEATURE_ID = "fix-gate-scope-constants-dedup-regression"
_PREDECESSOR = "slice-01"
_ENTERING = "slice-02"

# A legitimate first-commit message: no caller-supplied Gate-Scope: line at
# all. Since Defect C, this is the ONLY kind of --message that ever reaches
# commit_slice.main()'s git-mutating path with a Gate-Scope:-shaped line
# still able to appear in the final commit -- the mechanical placeholder
# commit-slice itself stamps, later amended to the real digest. This
# isolates the amend mechanism (does the placeholder get replaced?) from
# the separately pinned, now-retired guard defect (Defect C tests below).
_LEGITIMATE_FIRST_COMMIT_MESSAGE = (
    "fix(gate-scope): a legitimate first commit for this slice\n"
    "\n"
    "no caller-supplied trailer -- the mechanical placeholder and its\n"
    "later amend are the only source of any Gate-Scope: line here.\n"
)

_ALL_ZERO_PLACEHOLDER = "0" * 64
_GATE_SCOPE_LINE_RE = re.compile(r"^Gate-Scope:\s*(\S*)\s*$", re.MULTILINE)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    provision_commit_slice_repo(root)


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


def _write_feature_delta_with_prefactoring_entering_slice(repo: Path) -> None:
    """Mirrors ``test_commit_slice_writes_verified_record.py``'s identical
    helper verbatim: ``_PREDECESSOR`` is a real AT-bearing row,
    ``_ENTERING`` is ``@prefactoring``-annotated (EXEMPT), the cheapest
    fixture that clears E1+E2+E3 without a real feature-scoped contract-gate
    subprocess."""
    delta_dir = repo / "docs" / "feature" / _FEATURE_ID
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_PREDECESSOR} | the predecessor slice ships a real scenario | "
        "pending | | a real AT-bearing slice |\n"
        f"| {_ENTERING} | a behavior-preserving refactor introduces the seam | "
        "pending | @prefactoring | a green-to-green prefactoring |\n",
        encoding="utf-8",
    )


def _commit_predecessor_with_at(repo: Path) -> None:
    feat_dir = repo / "tests" / "acceptance" / _FEATURE_ID.replace("-", "_")
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / f"{_PREDECESSOR}.feature").write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: the predecessor slice's behaviour\n\n"
        f"  @{_PREDECESSOR}\n"
        "  Scenario: the predecessor delivers its observable outcome\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): predecessor behaviour\n\nSlice-Id: {_PREDECESSOR}",
    )


def _mark_predecessor_verified(repo: Path) -> None:
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    AtCompletionLedger(_FEATURE_ID, repo).append_gate_event(
        event="SliceCommitVerified", slice_id=_PREDECESSOR
    )


def _author_entering_slice_production_change(repo: Path) -> None:
    prod_file = repo / "src" / "app" / "module.py"
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text(
        "def helper() -> str:\n    return 'refactored, same behaviour'\n",
        encoding="utf-8",
    )


# ===========================================================================
# Main regression AT -- amend mechanism, driven via a LEGITIMATE --message
# (rewritten 2026-08-04, see the module docstring's 2026-08-04 status note:
# the ORIGINAL adversarial vehicle is now refused upstream by Defect C)
# ===========================================================================


def test_gate_scope_amend_never_leaves_the_placeholder_as_final_trailer(
    tmp_path: Path, capsys
) -> None:
    """On a slice's first commit -- a LEGITIMATE `--message` carrying no
    caller-supplied `Gate-Scope:` line at all -- the FINAL `Gate-Scope:`
    trailer on the shipped commit must carry the real committed-scope
    digest, never the all-zero placeholder `des commit-slice` stamps before
    the real digest is known.

    Discriminates against: `_amend_trailer` regressing to a no-op (or any
    change that stops the real digest from replacing the mechanical
    placeholder) -- proved empirically by monkeypatching `_amend_trailer`
    to a no-op in an ephemeral, uncommitted probe run and observing this
    exact assertion fail (see dispatch report); production code was never
    touched to demonstrate this, only monkeypatched for the duration of
    that one probe.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _LEGITIMATE_FIRST_COMMIT_MESSAGE
    )

    assert exit_code == 0, (
        f"expected the slice commit to land -- exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event

    final_message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    trailer_values = _GATE_SCOPE_LINE_RE.findall(final_message)
    assert trailer_values, (
        f"expected at least one Gate-Scope: line in the shipped commit "
        f"message, found none. full message={final_message!r}"
    )

    final_trailer_value = trailer_values[-1]
    assert final_trailer_value != _ALL_ZERO_PLACEHOLDER, (
        "the FINAL Gate-Scope: trailer on the shipped commit is the all-zero "
        "placeholder digest -- it attests NOTHING despite the commit looking "
        "well-formed. The amend step (_amend_trailer) must replace the "
        "mechanical placeholder with the real committed-scope digest before "
        f"reporting success. full message={final_message!r}, all "
        f"Gate-Scope: values found={trailer_values!r}"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", final_trailer_value), (
        f"expected the final Gate-Scope: trailer to be a well-formed 64-hex "
        f"digest, got {final_trailer_value!r}. full message={final_message!r}"
    )


# ===========================================================================
# Negative AT -- the wrong output must never survive in the shipped commit
# (rewritten 2026-08-04 -- same legitimate --message as above)
# ===========================================================================


@pytest.mark.negative_at
def test_gate_scope_placeholder_digest_never_survives_anywhere_in_final_commit(
    tmp_path: Path, capsys
) -> None:
    """Stronger, message-wide instance of the same honesty invariant: the
    all-zero placeholder digest must not appear ANYWHERE in the shipped
    commit's message, as a `Gate-Scope:` trailer or otherwise -- not merely
    "not as the first line".
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _LEGITIMATE_FIRST_COMMIT_MESSAGE
    )
    assert exit_code == 0, (
        f"expected the slice commit to land -- exit_code={exit_code!r}, event={event!r}"
    )

    final_message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    assert _ALL_ZERO_PLACEHOLDER not in final_message, (
        "the all-zero Gate-Scope placeholder digest must NEVER survive in "
        "the message of a commit `des commit-slice` reports as shipped -- "
        f"observed it still present. full message={final_message!r}"
    )


# ===========================================================================
# Defect A -- extract_gate_scope never checks trailer POSITION (EXAMINE find)
# ===========================================================================
#
# Driving surface: `des.cli.run_contract_gate.main` (`--verify-gate-scope`),
# on a real, freshly-provisioned git repo. Each case commits an EMPTY change
# (`git commit --allow-empty`) carrying a crafted message, so the tree stays
# byte-identical to the base template and the freshly re-derived
# committed-scope digest at verify-time is guaranteed to match the digest
# embedded in the crafted message -- isolating the assertion to the trailer
# POSITION/uniqueness defect alone, never a digest-mismatch false signal.
# The valid digest embedded in each message is fetched through the REAL
# `--committed-scope-digest` production mode (never hand-recomputed).


def _committed_scope_digest(repo: Path, capsys) -> str:
    """The real committed-scope digest of `repo`'s current HEAD, fetched
    through the production `--committed-scope-digest` mode itself."""
    exit_code = run_contract_gate_main(
        ["--repo", str(repo), "--committed-scope-digest"]
    )
    stdout = capsys.readouterr().out
    assert exit_code == 0, (
        f"--committed-scope-digest refused unexpectedly on the freshly "
        f"provisioned repo -- exit_code={exit_code!r}, stdout={stdout!r}"
    )
    digest_line = stdout.splitlines()[0].strip()
    assert re.fullmatch(r"[0-9a-f]{64}", digest_line), (
        f"expected a 64-hex digest as the first stdout line of "
        f"--committed-scope-digest, got {digest_line!r}"
    )
    return digest_line


def _provision_repo_with_valid_digest(tmp_path: Path, capsys) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    _init_repo(repo)
    digest = _committed_scope_digest(repo, capsys)
    return repo, digest


def _commit_empty_with_message(repo: Path, message: str) -> None:
    _git(repo, "commit", "--allow-empty", "-q", "-m", message)


def _verify_gate_scope_head(repo: Path, capsys) -> tuple[int, dict]:
    exit_code = run_contract_gate_main(
        ["--repo", str(repo), "--verify-gate-scope", "--commit", "HEAD"]
    )
    event = _last_json_event(capsys.readouterr().out)
    return exit_code, event


def test_gate_scope_trailer_buried_mid_body_is_never_verified(
    tmp_path: Path, capsys
) -> None:
    """A `Gate-Scope:` line sitting mid-BODY, with non-trailer prose both
    BEFORE and AFTER it, must be treated as ABSENT -- never as the commit's
    real trailer.

    RED for the right reason: `extract_gate_scope` has no notion of "trailer
    block" -- it returns the FIRST line in the WHOLE message matching the
    strict 64-hex grammar, wherever it sits, so `--verify-gate-scope`
    wrongly reports this buried line as VERIFIED today.
    """
    repo, digest = _provision_repo_with_valid_digest(tmp_path, capsys)
    message = (
        "fix(gate-scope): repro a trailer buried mid-body\n"
        "\n"
        f"Gate-Scope: {digest}\n"
        "\n"
        "unrelated prose that follows the Gate-Scope: line, proving it sits "
        "mid-body rather than in the message's final trailer block.\n"
    )
    _commit_empty_with_message(repo, message)

    exit_code, event = _verify_gate_scope_head(repo, capsys)

    assert exit_code != 0, (
        "a Gate-Scope: line buried mid-body with non-trailer prose AFTER it "
        f"must never verify -- got exit_code=0, event={event!r}. WHAT: the "
        "commit was accepted as sealed. WHY: extract_gate_scope scans the "
        "whole message for the first strict-grammar match, blind to "
        "position. HOW: extract_gate_scope must require the matching line "
        "to sit in the message's final trailer block."
    )
    assert event.get("event") != "GateScopeVerified", (
        "the position-blind extractor accepted a mid-body Gate-Scope: line "
        f"as if it were the real trailer -- event={event!r}"
    )


@pytest.mark.negative_at
def test_gate_scope_duplicate_trailer_lines_are_never_silently_resolved(
    tmp_path: Path, capsys
) -> None:
    """Two `Gate-Scope:` lines in one commit message (a real digest followed
    by the all-zero placeholder) must NEVER resolve to a silent "verified"
    via first-match -- nobody can tell which trailer attests the commit, so
    refusing is the only honest answer.

    RED for the right reason: `extract_gate_scope` returns the FIRST match
    and never notices the second line exists, so `--verify-gate-scope`
    wrongly reports this ambiguous commit as VERIFIED today (matches this
    repo's own history: `9ab9fa580aa7` carries exactly this shape).
    """
    repo, digest = _provision_repo_with_valid_digest(tmp_path, capsys)
    message = (
        "fix(gate-scope): repro duplicate Gate-Scope: lines\n"
        "\n"
        f"Gate-Scope: {digest}\n"
        f"Gate-Scope: {_ALL_ZERO_PLACEHOLDER}\n"
    )
    _commit_empty_with_message(repo, message)

    exit_code, event = _verify_gate_scope_head(repo, capsys)

    assert exit_code != 0, (
        "two Gate-Scope: lines in the same message must never verify via "
        f"first-match -- got exit_code=0, event={event!r}. WHAT: an "
        "ambiguous commit was accepted as sealed. WHY: extract_gate_scope "
        "returns on the first strict-grammar match and never inspects "
        "whether a second one exists. HOW: extract_gate_scope must detect "
        "more than one trailer-block Gate-Scope: line and refuse, never "
        "pick the first silently."
    )
    assert event.get("event") != "GateScopeVerified", (
        "first-match silently picked the real digest and ignored the "
        f"second (placeholder) line entirely -- event={event!r}"
    )


def test_gate_scope_trailer_followed_only_by_cherry_pick_line_still_verifies(
    tmp_path: Path, capsys
) -> None:
    """Sibling-branch pin (protects real history): 17 of the 564
    Gate-Scope-bearing commits in this repo's own history carry EXACTLY a
    trailing `(cherry picked from commit <sha>)` line after the Gate-Scope:
    trailer -- git's own `cherry-pick -x` appends it. The position fix must
    keep tolerating this shape; it must NOT regress to rejecting these 17
    legitimate commits by requiring the trailer to be the message's
    absolute last line.

    Already GREEN today (pins the direction the fix must not break).
    """
    repo, digest = _provision_repo_with_valid_digest(tmp_path, capsys)
    message = (
        "fix(gate-scope): repro trailer followed only by a cherry-pick line\n"
        "\n"
        f"Gate-Scope: {digest}\n"
        "(cherry picked from commit abc1234def5678900000000000000000000000a)\n"
    )
    _commit_empty_with_message(repo, message)

    exit_code, event = _verify_gate_scope_head(repo, capsys)

    assert exit_code == 0, (
        "a Gate-Scope: trailer followed ONLY by a git-appended cherry-pick "
        f"line must still verify -- got exit_code={exit_code!r}, "
        f"event={event!r}"
    )
    assert event == {
        "event": "GateScopeVerified",
        "commit": "HEAD",
        "gate_scope_digest": digest,
    }, event


def test_gate_scope_normal_trailing_trailer_still_verifies(
    tmp_path: Path, capsys
) -> None:
    """Sibling-branch pin: the ordinary shape (trailer is the message's
    absolute last line) must keep verifying -- already GREEN today.
    """
    repo, digest = _provision_repo_with_valid_digest(tmp_path, capsys)
    message = (
        "fix(gate-scope): repro the normal trailing trailer shape\n"
        "\n"
        f"Gate-Scope: {digest}\n"
    )
    _commit_empty_with_message(repo, message)

    exit_code, event = _verify_gate_scope_head(repo, capsys)

    assert exit_code == 0, (
        f"a normal trailing Gate-Scope: trailer must verify -- "
        f"got exit_code={exit_code!r}, event={event!r}"
    )
    assert event == {
        "event": "GateScopeVerified",
        "commit": "HEAD",
        "gate_scope_digest": digest,
    }, event


# ===========================================================================
# Defect B -- --verify-gate-scope on a nonexistent --repo raises a bare
# traceback instead of a structured refusal (EXAMINE find)
# ===========================================================================


def test_run_contract_gate_verify_gate_scope_never_crashes_on_missing_repo(
    tmp_path: Path, capsys
) -> None:
    """`--repo` pointing at a path that does not exist must degrade LOUD --
    a structured refusal -- never a bare, uncaught traceback.

    RED for the right reason: today `--verify-gate-scope` on a nonexistent
    `--repo` raises `FileNotFoundError` from
    `test_runner_port._unrecognized_reason` (`target_root.iterdir()` on a
    path that does not exist), propagating uncaught through
    `_maybe_route_digest_through_runner` / `_mode_verify_gate_scope` /
    `main`. The sibling command `des verify-slice-commit` already handles
    the IDENTICAL input cleanly (`{"event": "MalformedInput", ...}`, exit
    2) -- `run-contract-gate` must match that discipline instead of
    crashing.
    """
    missing_repo = tmp_path / "does-not-exist-lane"
    assert not missing_repo.exists()

    try:
        exit_code = run_contract_gate_main(
            [
                "--repo",
                str(missing_repo),
                "--verify-gate-scope",
                "--commit",
                "HEAD",
            ]
        )
    except Exception as exc:  # the observable DEFECT is exactly an uncaught exception
        pytest.fail(
            "des run-contract-gate --verify-gate-scope on a nonexistent "
            f"--repo must never raise a bare traceback -- got "
            f"{type(exc).__name__}: {exc}. WHAT: the CLI crashed instead of "
            "refusing cleanly. WHY: test_runner_port._unrecognized_reason "
            "calls target_root.iterdir() on a path that does not exist. "
            "HOW: detect the missing --repo before resolving a test runner "
            "and emit a structured refusal, mirroring des "
            "verify-slice-commit's MalformedInput handling on the "
            "identical input."
        )
        return

    event = _last_json_event(capsys.readouterr().out)
    assert exit_code != 0, (
        f"a nonexistent --repo must never report success -- "
        f"exit_code={exit_code!r}, event={event!r}"
    )
    assert "error" in event, (
        "the refusal must name WHAT failed in a structured 'error' field "
        f"-- event={event!r}"
    )


# ===========================================================================
# Defect C -- the pre-flight guard reuses extract_gate_scope's STRICT,
# position-aware grammar to answer a DIFFERENT, PERMISSIVE question
# (2026-08-04 regression, introduced by Defect A's own fix)
# ===========================================================================
#
# `commit_slice.main`'s pre-flight guard (~line 2309) asks: "does the
# caller-supplied --message already look like it carries a Gate-Scope:
# trailer?" -- a question that must be answered PERMISSIVELY: ANY line
# starting with `Gate-Scope:`, in ANY position, with ANY payload, must be
# refused before any git mutation happens. `extract_gate_scope` answers a
# DIFFERENT question -- "which digest attests THIS shipped commit?" -- and
# (correctly, for THAT question, since Defect A's fix above) is STRICT:
# the matching line must sit in the message's final trailer block AND carry
# a well-formed 64-hex payload. Reusing the strict reader for the
# permissive guard collapses the two questions:
#
#   * a well-formed 64-hex Gate-Scope: line that is NOT the final trailer
#     (prose follows it) fails the STRICT position check and sails past
#     the guard untouched (case 1 below) -- this is a fresh regression
#     Defect A's own position-narrowing introduced: before that fix,
#     `extract_gate_scope` was position-blind and DID catch this shape;
#     narrowing it for the reader's own (correct) purpose blinded the
#     guard as an unintended side effect;
#   * a non-hex Gate-Scope: line (e.g. `Gate-Scope: pending`) fails the
#     STRICT grammar check regardless of position and ALSO sails past the
#     guard (case 2 below) -- this one is NOT a fresh regression: measured
#     empirically, `extract_gate_scope`'s hex-only grammar never caught a
#     non-hex payload even before Defect A's fix, so the guard has NEVER
#     rejected this shape. Both close under the SAME remedy: the guard
#     must stop asking `extract_gate_scope`'s strict, position-scoped
#     question and instead detect any `Gate-Scope:`-prefixed line directly.
#
# Sibling-branch pins (cases 3-4 below) protect the guard's already-correct
# behaviour: a well-formed trailing trailer must keep being refused, and a
# clean message -- including one that merely MENTIONS "Gate-Scope"
# mid-sentence, never starting a line with it -- must keep producing a
# valid commit. A commit message has every right to talk ABOUT the
# mechanism; only a line that literally STARTS with `Gate-Scope:` is
# treated as a caller-supplied trailer attempt (interpretation pinned here
# for the ambiguous "clean message" case per dispatch instruction).


def _run_commit_slice_with_message(
    tmp_path: Path, capsys, message: str
) -> tuple[int, dict, Path]:
    """Shared provisioning helper (never hand-rolled): identical
    fixture-reuse setup (repo template + predecessor slice + prefactoring
    entering slice), with the `--message` payload as a parameter so every
    case in this file -- the amend tests above and the guard-scope cases
    below -- shares one setup path instead of duplicating git plumbing."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta_with_prefactoring_entering_slice(repo)
    _commit_predecessor_with_at(repo)
    _mark_predecessor_verified(repo)
    _author_entering_slice_production_change(repo)

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _ENTERING,
            "--message",
            message,
        ]
    )
    event = _last_json_event(capsys.readouterr().out)
    return exit_code, event, repo


def _head_commit_count(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--count", "HEAD").strip())


# `provision_commit_slice_repo` ships ONE pre-existing "base: walking
# skeleton" commit in its shared template, on top of which
# `_commit_predecessor_with_at` adds the predecessor slice commit -- so the
# repo already carries 2 commits BEFORE `commit_slice_main` ever runs in
# `_run_commit_slice_with_message`. A refused (guard-blocked) attempt must
# leave the count at this baseline; an accepted attempt must land exactly
# one more on top of it.
_BASELINE_COMMIT_COUNT = 2


# --- case 1: well-formed 64-hex Gate-Scope: line, NOT the final trailer ---

_NON_TRAILING_VALID_HEX_MESSAGE = (
    "fix(gate-scope): repro a non-trailing well-formed trailer line\n"
    "\n"
    f"Gate-Scope: {'a' * 64}\n"
    "\n"
    "prose that follows the Gate-Scope: line above, proving it sits\n"
    "mid-body rather than in the message's final trailer block.\n"
)


def test_commit_slice_guard_rejects_a_well_formed_gate_scope_line_mid_body(
    tmp_path: Path, capsys
) -> None:
    """The pre-flight guard must refuse a caller-supplied `--message` that
    embeds a well-formed (64-hex) `Gate-Scope:` line ANYWHERE, not only
    when it sits in the message's final trailer block.

    RED for the right reason: the guard calls `extract_gate_scope`, which
    (correctly, for its OWN question) requires the matching line to sit in
    the message's final trailer block. A non-trailing well-formed line
    sails past the guard, the commit proceeds untouched, and the caller's
    line survives in the shipped commit body alongside the mechanically
    appended real trailer.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _NON_TRAILING_VALID_HEX_MESSAGE
    )

    assert exit_code == 2, (
        "a --message embedding a well-formed Gate-Scope: line mid-body "
        f"(not the final trailer) must be refused before any git mutation "
        f"-- got exit_code={exit_code!r}, event={event!r}. WHAT: the guard "
        "let a caller-supplied Gate-Scope: line through. WHY: the guard "
        "reuses extract_gate_scope, which requires the matching line to "
        "sit in the message's final trailer block -- a non-trailing line "
        "is invisible to it. HOW: the guard must detect ANY line starting "
        "with 'Gate-Scope:' regardless of position or payload shape, "
        "independent of extract_gate_scope's trailer-block scoping."
    )
    assert event.get("event") == "MalformedInput", event
    assert event.get("error"), (
        f"the refusal must name a non-empty, useful error -- event={event!r}"
    )
    assert _head_commit_count(repo) == _BASELINE_COMMIT_COUNT, (
        "no new commit may land when the guard should have refused the "
        f"input -- repo has {_head_commit_count(repo)} commits, expected "
        f"the baseline {_BASELINE_COMMIT_COUNT} (template + predecessor)"
    )


# --- case 2: non-hex `Gate-Scope: pending` line, any position ---
# (pre-existing defect, NOT introduced by Defect A -- pinned here per the
# dispatch's explicit note that the same fix must close it)

_NON_HEX_TRAILING_MESSAGE = (
    "fix(gate-scope): repro a non-hex trailing Gate-Scope: line\n"
    "\n"
    "Gate-Scope: pending\n"
)

_NON_HEX_MID_BODY_MESSAGE = (
    "fix(gate-scope): repro a non-hex mid-body Gate-Scope: line\n"
    "\n"
    "Gate-Scope: pending\n"
    "\n"
    "prose that follows the non-hex line above, proving the guard must\n"
    "refuse it at any position, not only as a final trailer.\n"
)


def test_commit_slice_guard_rejects_a_non_hex_gate_scope_line_as_final_trailer(
    tmp_path: Path, capsys
) -> None:
    """The pre-flight guard must refuse a non-hex `Gate-Scope: pending`
    line even when it sits exactly where a real trailer would.

    RED for the right reason -- and NOT a fresh regression: measured
    empirically, `extract_gate_scope`'s STRICT 64-hex grammar has NEVER
    matched a non-hex payload, position notwithstanding, so this shape has
    ALWAYS sailed past the guard, both before and after Defect A's
    position fix. This is the second, pre-existing defect the same
    guard-widening remedy closes.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _NON_HEX_TRAILING_MESSAGE
    )

    assert exit_code == 2, (
        "a --message ending in a non-hex 'Gate-Scope: pending' line must "
        f"be refused before any git mutation -- got exit_code={exit_code!r}, "
        f"event={event!r}. WHAT: the guard let a non-hex Gate-Scope: line "
        "through. WHY: the guard reuses extract_gate_scope's STRICT "
        "64-hex-only grammar, which was never designed to catch a "
        "malformed payload -- it correctly reports 'no real trailer here' "
        "for its OWN question, but the guard needs a different, permissive "
        "answer. HOW: the guard must detect ANY line starting with "
        "'Gate-Scope:' regardless of payload shape, independent of "
        "extract_gate_scope's strict-hex grammar."
    )
    assert event.get("event") == "MalformedInput", event
    assert event.get("error"), (
        f"the refusal must name a non-empty, useful error -- event={event!r}"
    )
    assert _head_commit_count(repo) == _BASELINE_COMMIT_COUNT, (
        "no new commit may land when the guard should have refused the "
        f"input -- repo has {_head_commit_count(repo)} commits, expected "
        f"the baseline {_BASELINE_COMMIT_COUNT} (template + predecessor)"
    )


@pytest.mark.negative_at
def test_commit_slice_guard_rejects_a_non_hex_gate_scope_line_anywhere_in_body(
    tmp_path: Path, capsys
) -> None:
    """Stronger, position-independent instance of the same case-2 defect:
    a non-hex `Gate-Scope:` line buried mid-body, with prose both before
    and after it, must ALSO be refused -- "any position" means any
    position, not merely "as the final trailer".

    RED for the right reason: same as above -- the STRICT hex-only grammar
    never matches `pending` regardless of where the line sits.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _NON_HEX_MID_BODY_MESSAGE
    )

    assert exit_code == 2, (
        "a --message with a non-hex 'Gate-Scope: pending' line buried "
        f"mid-body must be refused -- got exit_code={exit_code!r}, "
        f"event={event!r}. WHAT: the guard let a non-hex, non-trailing "
        "Gate-Scope: line through. WHY: extract_gate_scope's strict-hex, "
        "trailer-block-scoped grammar matches neither the payload nor the "
        "position. HOW: the guard must detect ANY line starting with "
        "'Gate-Scope:' anywhere in the message, regardless of payload "
        "shape or position."
    )
    assert event.get("event") == "MalformedInput", event
    assert event.get("error"), (
        f"the refusal must name a non-empty, useful error -- event={event!r}"
    )
    assert _head_commit_count(repo) == _BASELINE_COMMIT_COUNT, (
        "no new commit may land when the guard should have refused the "
        f"input -- repo has {_head_commit_count(repo)} commits, expected "
        f"the baseline {_BASELINE_COMMIT_COUNT} (template + predecessor)"
    )


# --- case 3: sibling-branch pin -- well-formed trailing trailer still ---
# --- refused (already correct today; must not regress) ---

_WELL_FORMED_TRAILING_MESSAGE = (
    "fix(gate-scope): attempt to smuggle a well-formed final trailer\n"
    "\n"
    f"Gate-Scope: {'b' * 64}\n"
)


def test_commit_slice_guard_still_rejects_a_well_formed_trailing_gate_scope_trailer(
    tmp_path: Path, capsys
) -> None:
    """Sibling-branch pin (non-regression): the guard's original,
    already-correct case -- a well-formed 64-hex `Gate-Scope:` trailer
    sitting exactly as the message's final trailer -- must keep being
    refused. Already GREEN today; pins the direction any guard-widening
    fix must not break.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _WELL_FORMED_TRAILING_MESSAGE
    )

    assert exit_code == 2, (
        f"a well-formed trailing Gate-Scope: trailer must still be "
        f"refused -- got exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "MalformedInput", event
    assert event.get("error"), (
        f"the refusal must name a non-empty, useful error -- event={event!r}"
    )
    assert _head_commit_count(repo) == _BASELINE_COMMIT_COUNT, (
        f"no new commit may land -- repo has {_head_commit_count(repo)} "
        f"commits, expected the baseline {_BASELINE_COMMIT_COUNT} "
        "(template + predecessor)"
    )


# --- case 4: sibling-branch pins -- clean input must keep working ---
# --- (the guard-widening fix must not become over-aggressive) ---

_CLEAN_MESSAGE = (
    "fix(gate-scope): a perfectly ordinary commit with no trailer\n"
    "\n"
    "nothing resembling a mechanical trailer appears anywhere in this\n"
    "body.\n"
)

# Pinned interpretation (dispatch flagged this as ambiguous): a message
# that MENTIONS "Gate-Scope" mid-sentence -- never as the first token of a
# line -- must NOT be mistaken for a caller-supplied trailer. A commit
# message has every right to talk ABOUT the mechanism.
_MID_SENTENCE_MENTION_MESSAGE = (
    "fix(gate-scope): document the mechanical trailer behaviour\n"
    "\n"
    "the trailer named Gate-Scope: is appended mechanically after the\n"
    "commit lands, so callers must never supply it themselves.\n"
)


def test_commit_slice_guard_still_accepts_a_message_with_no_gate_scope_line(
    tmp_path: Path, capsys
) -> None:
    """Sibling-branch pin (non-regression): an ordinary `--message` with no
    `Gate-Scope:` line at all must keep producing a valid commit -- the
    guard-widening fix must not become so aggressive it starts rejecting
    clean input. Already GREEN today.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _CLEAN_MESSAGE
    )

    assert exit_code == 0, (
        f"a clean --message with no Gate-Scope: line must still produce a "
        f"commit -- got exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event
    assert _head_commit_count(repo) == _BASELINE_COMMIT_COUNT + 1, (
        "the commit must have landed on top of the baseline -- repo has "
        f"{_head_commit_count(repo)} commits, expected "
        f"{_BASELINE_COMMIT_COUNT + 1}"
    )


def test_commit_slice_guard_still_accepts_a_mid_sentence_mention_of_gate_scope(
    tmp_path: Path, capsys
) -> None:
    """Sibling-branch pin (non-regression, pinned interpretation): a
    message that merely MENTIONS "Gate-Scope" mid-sentence -- never
    starting a line with it -- must keep producing a valid commit. Only a
    line that literally STARTS with `Gate-Scope:` counts as a
    caller-supplied trailer attempt. Already GREEN today.
    """
    exit_code, event, repo = _run_commit_slice_with_message(
        tmp_path, capsys, _MID_SENTENCE_MENTION_MESSAGE
    )

    assert exit_code == 0, (
        f"a message that merely MENTIONS Gate-Scope mid-sentence (never "
        f"starting a line with it) must still produce a commit -- got "
        f"exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event
    assert _head_commit_count(repo) == _BASELINE_COMMIT_COUNT + 1, (
        "the commit must have landed on top of the baseline -- repo has "
        f"{_head_commit_count(repo)} commits, expected "
        f"{_BASELINE_COMMIT_COUNT + 1}"
    )
