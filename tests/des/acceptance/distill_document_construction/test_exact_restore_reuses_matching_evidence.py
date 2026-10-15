"""Exact restoration of a complete DESIGN reuses matching oracle/craft evidence.

Human decision: reuse when ALL identities match (same complete constructor
DESIGN, same selected revision, same target bytes). Scope: oracle and craft
turn records as shown by `des state`; verify records are not asserted here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
    HANDOVER,
    _acceptance_keys,
    _blue_design,
    _call,
    _labels_of,
    _Subject,
    _value_manifest,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import block


BLUE = "tests/acceptance/test_selected_blue.py"
BLUE_ORACLE = f"{BLUE}::test_selects_blue"
CORRECTED_PURPOSE = "Expose the same public value under a corrected product purpose."


def _restored_design(subject: _Subject, decision: str | None = None) -> None:
    """The complete constructor DESIGN; `decision` makes intermediate B."""
    _blue_design(subject)
    if decision is None:
        return
    import sys

    manifest = _value_manifest(shared=subject.shared, decision=decision)
    manifest["oracle"] = BLUE_ORACLE
    manifest["acceptance_supports"] = ["tests/support/blue_driver.py"]
    manifest["verification"] = [[sys.executable, "-m", "pytest", BLUE]]
    code, out, err = _call(
        subject.root, "design", json.dumps(manifest), value=1, replace_current=True
    )
    assert code == 0, out + err


def _restore_with_changed_purpose(subject: _Subject) -> None:
    """Change only the purpose definition, retaining A's operative slots."""
    import sys

    manifest = _value_manifest(
        shared=subject.shared,
        purpose=CORRECTED_PURPOSE,
    )
    manifest["oracle"] = BLUE_ORACLE
    manifest["acceptance_supports"] = ["tests/support/blue_driver.py"]
    manifest["verification"] = [[sys.executable, "-m", "pytest", BLUE]]
    code, out, err = _call(
        subject.root, "design", json.dumps(manifest), value=1, replace_current=True
    )
    assert code == 0, out + err


def _records(subject: _Subject) -> list[str]:
    """The actual persisted oracle/craft evidence refs, not a provider log."""
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(subject.root),
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/nwave/turns",
        ],
        text=True,
    ).splitlines()


@pytest.mark.parametrize(
    "restore",
    ("full-same-code", "full-target-code-changed", "full-semantic-content-changed"),
)
def test_exact_design_restore_reuses_evidence_only_when_every_identity_matches(
    tmp_path: Path, restore: str
) -> None:
    subject = _Subject(tmp_path, None, shared=False).designed()
    _blue_design(subject)  # complete constructor DESIGN A
    original_value = json.loads((subject.root / HANDOVER).read_text())["values"][0]
    subject.select("blue")
    assert subject.oracle("blue")[0] == 0 and subject.craft("blue")[0] == 0
    recorded = {"oracle": "recorded", "craft": "recorded"}
    assert _labels_of(subject.state()) == recorded
    kept, records = _acceptance_keys(subject.root), _records(subject)

    _restored_design(subject, "Intermediate B decision: validate at the boundary.")
    between = _labels_of(subject.state())
    assert between != recorded and "recorded" not in between.values(), (
        "WHAT: DESIGN B showed A's oracle/craft as current. WHY: B is a "
        "different complete design. HOW: judge currentness by design identity."
    )
    assert _records(subject) == records, (
        "intermediate B altered historical evidence refs"
    )
    assert _acceptance_keys(subject.root) == kept

    if restore == "full-target-code-changed":
        widget = subject.root / "src" / "widget.py"
        widget.write_text(widget.read_text() + "MOVED = 1\n")
        subprocess.run(
            ["git", "-C", str(subject.root), "add", "src/widget.py"], check=True
        )
        subprocess.run(
            ["git", "-C", str(subject.root), "commit", "-qm", "target code moved"],
            check=True,
        )
    if restore == "full-semantic-content-changed":
        _restore_with_changed_purpose(subject)
    else:
        _blue_design(subject)  # exact restoration of complete DESIGN A
    assert _acceptance_keys(subject.root) == kept, "restoration rewrote B/A selection"
    value = json.loads((subject.root / HANDOVER).read_text())["values"][0]
    if restore != "full-semantic-content-changed":
        assert value["authority"] == original_value["authority"], (
            "WHAT: exact DESIGN restoration changed the normalized authority. "
            "WHY: restoring A must retain its complete catalog and operative slots. "
            "HOW: reproduce A's complete constructor input, not only its oracle."
        )
        assert (
            value["design_semantic_sha256"] == original_value["design_semantic_sha256"]
        ), (
            "WHAT: exact DESIGN restoration changed its semantic identity. "
            "WHY: unchanged DESIGN must reuse its identity even when target code moves. "
            "HOW: derive the identity from the complete normalized DESIGN input."
        )

    # The oracle record binds acceptance bytes and their selected authority.
    # The craft record additionally binds the mutable target bytes whose
    # oracle was observed GREEN. Moving only target code therefore makes the
    # craft record historical, without changing the oracle record's identity.
    labels = _labels_of(subject.state())
    if restore == "full-same-code":
        assert labels == recorded, (
            "WHAT: exact restoration of DESIGN A (same selected revision, same "
            f"target bytes) left oracle={labels['oracle']} craft={labels['craft']}. "
            "WHY: the human chose reuse when ALL identities match; A's records "
            "are valid again. HOW: judge oracle/craft currentness by the matching "
            "design, revision and tree identities, never by history order."
        )
        assert _records(subject) == records
        code, out, err, _new = subject.oracle("blue")
        assert code == 0, out + err
        return

    if restore == "full-target-code-changed":
        assert labels["oracle"] == "recorded", (
            "WHAT: after only the mutable target code moved, the oracle "
            f"author record read oracle={labels['oracle']}. WHY: the oracle "
            "turn is a fact about the acceptance bytes and the selected "
            "revision identity alone -- production target bytes are the "
            "crafter's to move and carry no oracle-authorship claim. HOW: "
            "judge oracle currentness by acceptance-path bytes and the "
            "selected revision, never by mutable target bytes."
        )
        assert labels["craft"] != "recorded", (
            "WHAT: after the mutable target code moved, the craft record "
            f"still read craft={labels['craft']}. WHY: a craft record is a "
            "fact about the mutable targets AND the acceptance bytes "
            "together; moved target bytes make it historical, never proof "
            "the crafted code is current. HOW: judge craft currentness over "
            "mutable targets plus acceptance bytes, and re-run `des craft` "
            "when they move."
        )
        assert _records(subject) == records, "old evidence refs were not kept"
        next_step = subject.state()
        assert "des craft --repo-root" in next_step, (
            f"WHAT: the canonical next step read {next_step!r}. WHY: the "
            "oracle record is still current and only the craft record is "
            "historical, so the only step owed is re-crafting, never "
            "re-authoring the oracle or restarting DESIGN. HOW: name `des "
            "craft` as NEXT whenever oracle=recorded and craft is not."
        )
        return

    assert "recorded" not in labels.values(), (
        f"WHAT: {restore} restore showed oracle={labels['oracle']} "
        f"craft={labels['craft']}. WHY: an identity differs or is unknown, so "
        "old evidence may not be current. HOW: reuse only on full identity match."
    )
    assert _records(subject) == records, "old evidence refs were not kept"
    original_authority = original_value["authority"]
    purpose_id = original_authority["purpose"]["ref"]
    original_purpose = [
        fact for fact in original_authority["facts"] if fact["id"] == purpose_id
    ]
    assert len(original_purpose) == 1, (
        "WHAT: the original purpose reference has no unique catalog definition. "
        "WHY: this stimulus must change exactly one admitted purpose definition. "
        "HOW: construct A through the normalized DESIGN producer with one definition."
    )
    assert original_purpose[0]["text"] != CORRECTED_PURPOSE, (
        "WHAT: the corrected purpose matches A's original purpose. "
        "WHY: an unchanged definition cannot challenge semantic-identity reuse. "
        "HOW: submit a genuinely different purpose while preserving operative slots."
    )
    expected_authority = {
        **original_authority,
        "facts": [
            {**fact, "text": CORRECTED_PURPOSE} if fact["id"] == purpose_id else fact
            for fact in original_authority["facts"]
        ],
    }
    assert value["authority"] == expected_authority, (
        "WHAT: the restored normalized authority differs beyond the purpose text. "
        "WHY: every other catalog definition, catalog order, stable id, FactRef "
        "and typed operative slot must remain exactly A's. "
        "HOW: change only the purpose definition through the DESIGN constructor."
    )
    assert (
        value["design_semantic_sha256"] != original_value["design_semantic_sha256"]
    ), (
        "WHAT: changing the catalog purpose retained A's full semantic identity. "
        "WHY: unchanged operative slots do not make the complete DESIGN identical. "
        "HOW: bind semantic identity to the complete normalized input, including facts."
    )
    before = _records(subject)
    code, out, err, _ = subject.oracle("blue")
    assert code != 0 and "SelectedRevisionRealignmentNeeded" in out + err
    assert "--replace-current" in out + err
    assert _records(subject) == before, "a misaligned selection changed evidence refs"


def test_externally_weakened_oracle_is_never_relabeled_current_by_verify_refresh(
    tmp_path: Path,
) -> None:
    """`des verify`'s formatter refresh must not launder an unreviewed edit.

    A complete oracle/craft turn is recorded, then the oracle file is weakened
    by hand -- outside `des oracle`/`des craft` -- so its bytes no longer match
    what the recorded turn produced. `des verify` still builds a candidate and
    re-points every EXISTING record at bytes the runner itself moved
    (`_refresh_turn_records`, for its own declared formatter). That refresh
    must never be the sole reason an externally, unreviewed-changed oracle or
    craft record reads as current again: without a native witness that the
    change was produced by a real oracle/craft turn, `des state` must show it
    historical on success, or `des verify` must return a named Refusal whose
    reason identifies the changed oracle and whose HOW returns to `des oracle`.
    A crash or unavailable verification substrate is not that safe alternative.
    """
    subject = _Subject(tmp_path, None, shared=False).designed()
    _blue_design(subject)
    assert subject.oracle("blue")[0] == 0 and subject.craft("blue")[0] == 0, (
        "WHAT: the legal blue oracle/craft control did not complete. "
        "WHY: this scenario must challenge already recorded evidence, not setup. "
        "HOW: complete the declared blue oracle and craft through the public steps."
    )
    assert _labels_of(subject.state()) == {"oracle": "recorded", "craft": "recorded"}, (
        "WHAT: the unmodified blue oracle/craft evidence is not current. "
        "WHY: only the subsequent external oracle edit may make it historical. "
        "HOW: record matching oracle/craft evidence before changing oracle bytes."
    )

    oracle_path = subject.root / BLUE
    original = oracle_path.read_text()
    assert "assert" in original, (
        f"WHAT: the recorded oracle {BLUE} contains no assertion: {original!r}. "
        "WHY: weakening must replace an actual recorded behavioral observation. "
        "HOW: author the blue behavioral oracle through the public oracle step."
    )
    oracle_path.write_text(
        "def test_selects_blue():\n    assert True  # weakened outside des oracle\n"
    )

    subject.complete_second_value()
    code, out, err = run_cli_in_process(
        ["verify", "--repo-root", str(subject.root)],
        cwd=subject.root,
        env=subject.native,
        catch_all=True,
    )
    if code != 0:
        refusal = block(out, err)
        assert code == 1 and refusal.get("DELIVERY-OUTCOME") == "Refusal", (
            f"WHAT: verifying the externally changed oracle exited {code} with "
            f"{out + err!r}, expected a named Refusal. "
            "WHY: a crash or indeterminate substrate is not evidence that verify "
            "safely rejected unreviewed oracle bytes. "
            "HOW: emit the public Refusal outcome for the moved oracle witness."
        )
        assert refusal.get("WHAT") and BLUE in refusal.get("WHY", ""), (
            f"WHAT: the verify refusal does not identify {BLUE} as its cause: "
            f"{refusal!r}. WHY: an unrelated prerequisite failure cannot discharge "
            "the external-oracle-edit safety law. "
            "HOW: name the changed acceptance path and its stale native witness."
        )
        assert "des oracle" in refusal.get("HOW", ""), (
            f"WHAT: the moved-oracle refusal has no oracle reauthoring remedy: "
            f"{refusal!r}. WHY: unreviewed acceptance bytes need a new native "
            "oracle witness, not an infrastructure workaround. "
            "HOW: direct the caller to restore the witnessed bytes or invoke "
            "`des oracle` to author and review the changed oracle."
        )
        return

    labels = _labels_of(subject.state())
    assert "recorded" not in labels.values(), (
        f"WHAT: after the oracle file was weakened by hand, `des verify`'s "
        f"formatter refresh alone left oracle={labels['oracle']} "
        f"craft={labels['craft']} current. WHY: `_refresh_turn_records` may "
        "only re-point bytes the RUNNER itself moved to satisfy its declared "
        "format contract, never bytes an operator edited outside `des "
        "oracle`/`des craft`; an unreviewed change has no native witness. HOW: "
        "gate the refresh on a witness that the runner, not an external edit, "
        "produced the new bytes, and otherwise leave the record historical."
    )
