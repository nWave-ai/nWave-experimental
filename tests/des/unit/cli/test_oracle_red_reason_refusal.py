"""Executable coverage for the BASE oracle-execution probe (K4 Run 13).

Real, bounded subprocess execution against tiny synthetic oracle files in
`tmp_path` -- never this repo's own tree, so there is no recursive-pytest
risk. The probe is NEVER switchable off (GDP-7) and language-agnostic
(roadmap: "language agnostic is an outcome constraint, not authorization
to build or retain a universal language-adapter framework"): a declared-
symbol token match is RED (accepted); a language-neutral build/compile
marker is `UNACCEPTABLE_BUILD` (refused, output quoted); anything else is
`INDETERMINATE` (an informational note, never a refusal).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from des.cli._oracle_red_reason_refusal import oracle_red_reason_check


def _contract(oracle_relative: str, route: str = "RED_TO_GREEN") -> dict:
    return {
        "delivery-route": route,
        "acceptance-tests": {"locator": oracle_relative},
        "targets": {
            "pkg/mod.py": {
                "justification": "The new NotBuiltYet symbol lives beside mod.",
                "overlap": "",
            }
        },
        "verification-scope": {
            "commands": [
                {
                    "executable": {"kind": "repository", "path": sys.executable},
                    "arguments": ["-m", "pytest", "-q", oracle_relative],
                }
            ]
        },
    }


def test_probe_always_fires_even_from_inside_this_repos_own_pytest_run(
    tmp_path: Path,
) -> None:
    """GDP-7: no environment can switch this probe off. Run under this
    repo's own ambient pytest process (no monkeypatch involved at all) --
    a real, isolated `tmp_path` subprocess, so no recursion risk either way."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it(:\n    pass\n", encoding="utf-8")  # SyntaxError

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    assert notes == []


def test_oracle_failing_for_the_right_reason_yields_no_finding_and_no_note(
    tmp_path: Path,
) -> None:
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
        encoding="utf-8",
    )

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert findings == []
    assert notes == []


def test_oracle_with_a_syntax_error_is_refused_with_quoted_output(
    tmp_path: Path,
) -> None:
    """A SyntaxError matches the language-neutral build-marker table --
    refused, the real output quoted, no declared-symbol correlation
    needed."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it(:\n    pass\n", encoding="utf-8")

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    what, why, how = findings[0]
    assert "quoted output" in what
    assert why
    assert how
    assert notes == []


def test_oracle_failing_with_no_symbol_and_no_build_marker_is_indeterminate(
    tmp_path: Path,
) -> None:
    """A fixture/setup gap this classifier has no vocabulary for -- an
    honest INDETERMINATE note, never a refusal."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "def test_it():\n    raise RuntimeError('unrelated dependency missing')\n",
        encoding="utf-8",
    )

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert findings == []
    assert len(notes) == 1
    assert "INFO:" in notes[0]
    assert "INDETERMINATE" in notes[0]


def test_already_green_oracle_for_red_to_green_is_refused(tmp_path: Path) -> None:
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it():\n    assert 1 == 1\n", encoding="utf-8")

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    what, _why, _how = findings[0]
    assert "already passes at BASE" in what
    assert notes == []


def test_already_green_refusal_how_names_commit_before_green_to_green(
    tmp_path: Path,
) -> None:
    """SF friction report 2026-08-20, item 4: the OLD `how=` suggested
    "switch delivery-route to GREEN_TO_GREEN if the behavior genuinely
    already exists" -- but ADR-SSOT-002 §4b requires GREEN_TO_GREEN to
    name an EXISTING (committed) oracle DESIGN already knows about;
    "switch route" alone is a dead-end recovery on a dirty, uncommitted
    tree (trunk-crash recovery lands exactly here: prior-lane WIP
    already makes the oracle green, but nothing is committed yet). The
    `how` must name the actual missing prerequisite -- commit first --
    not just restate the route choice as if it needed no precondition."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it():\n    assert 1 == 1\n", encoding="utf-8")

    findings, _notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    _what, _why, how = findings[0]
    assert "commit" in how.lower(), (
        f"the how= field must name committing the tree as the real "
        f"prerequisite before GREEN_TO_GREEN can name an existing "
        f"oracle, not just 'switch the route': {how!r}"
    )


def test_already_green_oracle_for_green_to_green_is_accepted(tmp_path: Path) -> None:
    """GREEN_TO_GREEN expects the oracle already green at base -- no defect."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it():\n    assert 1 == 1\n", encoding="utf-8")

    findings, notes = oracle_red_reason_check(
        tmp_path, _contract("test_oracle.py", route="GREEN_TO_GREEN")
    )

    assert findings == []
    assert notes == []


def test_command_that_cannot_even_start_is_an_informational_note_never_green(
    tmp_path: Path,
) -> None:
    """A missing executable / unresolvable interpreter raises `OSError`
    before any return code exists -- GDP-6: this must never be silent
    (an empty findings/notes pair would otherwise read as nothing to
    report, indistinguishable from a genuine GREEN)."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
        encoding="utf-8",
    )
    contract = _contract("test_oracle.py")
    contract["verification-scope"]["commands"] = [
        {
            "executable": {
                "kind": "repository",
                "path": "does-not-exist-nowhere-nohow",
            },
            "arguments": ["-m", "pytest", "-q", "test_oracle.py"],
        }
    ]

    findings, notes = oracle_red_reason_check(tmp_path, contract)

    assert findings == []
    assert len(notes) == 1
    assert "COULD-NOT-RUN" in notes[0]
    assert "could not even START" in notes[0]


def test_already_green_unrelated_command_is_not_flagged(tmp_path: Path) -> None:
    """An oracle-UNLINKED command that legitimately already passes (this
    repo's own shared dispatch-test fixture also declares `git diff
    --check`) must never be flagged -- the exact regression class CI
    caught once already."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
        encoding="utf-8",
    )
    contract = _contract("test_oracle.py")
    contract["verification-scope"]["commands"].append(
        {"executable": {"kind": "toolchain", "name": "true"}, "arguments": []}
    )

    findings, _notes = oracle_red_reason_check(tmp_path, contract)

    assert findings == []


# --- SF friction 2026-08-21 (verification-authority DELEGATION): a
# delegation contract carries `verification-scope.literal-script-block`
# and NO argv commands -- iterating only `.commands` used to traverse it
# silently to zero findings/notes (GDP-6). The probe never argv-executes
# an authority SCRIPT; its delegation-branch contract is: re-resolve the
# locator against the owning document, verify the digest, and be LOUD
# either way.

_AUTHORITY_DOC = "docs/adrs/adr-verify.md"
_AUTHORITY_LOCATOR = f"{_AUTHORITY_DOC}#the-exact-order"
_AUTHORITY_LINES = [
    'FORMAL_TMP="$(mktemp -d)"',
    "go test ./... -count=1",
]


def _write_authority_doc(repo_root: Path, lines: list[str]) -> str:
    doc = repo_root / _AUTHORITY_DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "# ADR\n\n## The exact order\n\n```text\n" + "\n".join(lines) + "\n```\n",
        encoding="utf-8",
    )
    return "sha256:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _delegation_contract(digest: str) -> dict:
    return {
        "delivery-route": "RED_TO_GREEN",
        "acceptance-tests": {"locator": "go/x_test.go::TestX"},
        "targets": {"go/x.go": {"justification": "adds X", "overlap": ""}},
        "verification-scope": {
            "literal-script-block": {
                "locator": _AUTHORITY_LOCATOR,
                "content-digest": digest,
                "lines": list(_AUTHORITY_LINES),
            }
        },
    }


def test_delegation_contract_is_loud_never_a_silent_zero_pass(
    tmp_path: Path,
) -> None:
    digest = _write_authority_doc(tmp_path, _AUTHORITY_LINES)

    findings, notes = oracle_red_reason_check(tmp_path, _delegation_contract(digest))

    assert findings == []
    assert len(notes) == 1
    assert _AUTHORITY_LOCATOR in notes[0]
    assert "digest re-verified" in notes[0]
    assert "BASELINE" in notes[0]


def test_delegation_digest_mismatch_is_a_refusal_finding(tmp_path: Path) -> None:
    # The owning document drifted after compile: the contract's carried
    # digest no longer matches -- refused, never executed on faith.
    digest = _write_authority_doc(tmp_path, _AUTHORITY_LINES)
    _write_authority_doc(tmp_path, [*_AUTHORITY_LINES, "rm -rf tampered"])

    findings, notes = oracle_red_reason_check(tmp_path, _delegation_contract(digest))

    assert notes == []
    assert len(findings) == 1
    what, _why, how = findings[0]
    assert "no longer matches" in what
    assert _AUTHORITY_LOCATOR in what
    assert "des compile-contract" in how


def test_delegation_tampered_carried_lines_refused_despite_matching_digest(
    tmp_path: Path,
) -> None:
    # Sister falsifier (SF live finding 2026-08-21): correct locator,
    # correct declared digest, ONLY the carried lines swapped for a
    # harmless-looking order -- comparing the re-resolved digest to the
    # DECLARED digest alone let exactly this contract through, and the
    # crafter would have faithfully executed the tampered lines.
    digest = _write_authority_doc(tmp_path, _AUTHORITY_LINES)
    contract = _delegation_contract(digest)
    contract["verification-scope"]["literal-script-block"]["lines"] = ["exit 0"]

    findings, notes = oracle_red_reason_check(tmp_path, contract)

    assert notes == []
    assert len(findings) == 1
    what, why, how = findings[0]
    assert "do not match the re-resolved authority block" in what
    assert _AUTHORITY_LOCATOR in what
    # The judgment is derived from the RE-RESOLVED content of the intact
    # authority document (its real line count), never from the carried
    # copy -- the eliminative binding: execution reads the resolved block.
    assert f"({len(_AUTHORITY_LINES)} lines)" in what
    assert "(1 lines)" in what
    assert "display-only" in why
    assert "EXCLUSIVELY" in why
    assert "des compile-contract" in how


def test_delegation_faithful_note_counts_the_resolved_lines(tmp_path: Path) -> None:
    # Same tamper, opposite emphasis: with carried == resolved the branch
    # stays a note, and the line count it reports is the RESOLVED block's
    # own -- the one surface dispatch derives from script content reads
    # the re-resolved authority, never the carried projection.
    digest = _write_authority_doc(tmp_path, _AUTHORITY_LINES)

    _findings, notes = oracle_red_reason_check(tmp_path, _delegation_contract(digest))

    assert len(notes) == 1
    assert f"({len(_AUTHORITY_LINES)} lines" in notes[0]


def test_delegation_unresolvable_at_dispatch_is_a_refusal_finding(
    tmp_path: Path,
) -> None:
    # The owning document is gone entirely: a delegation contract with no
    # re-resolvable authority leaves the crafter no executable order.
    digest = "sha256:" + "0" * 64

    findings, notes = oracle_red_reason_check(tmp_path, _delegation_contract(digest))

    assert notes == []
    assert len(findings) == 1
    what, _why, how = findings[0]
    assert "cannot be re-resolved" in what
    assert "des compile-contract" in how
