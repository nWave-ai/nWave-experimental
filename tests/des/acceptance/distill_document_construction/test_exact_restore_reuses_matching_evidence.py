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
from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
    HANDOVER,
    _acceptance_keys,
    _blue_design,
    _call,
    _labels_of,
    _provider_design,
    _Subject,
    _value_manifest,
)


BLUE = "tests/acceptance/test_selected_blue.py"
BLUE_ORACLE = f"{BLUE}::test_selects_blue"


def _restored_design(subject: _Subject, decision: str | None = None) -> None:
    """The complete constructor DESIGN; `decision` makes intermediate B."""
    _blue_design(subject)
    if decision is None:
        return
    import sys

    manifest = _value_manifest()
    manifest["decisions"] = [decision]
    manifest["oracle"] = BLUE_ORACLE
    manifest["acceptance_supports"] = ["tests/support/blue_driver.py"]
    manifest["verification"] = [[sys.executable, "-m", "pytest", BLUE]]
    code, out, err = _call(
        subject.root, "design", json.dumps(manifest), value=1, replace_current=True
    )
    assert code == 0, out + err


def _blue_partial_facts() -> dict[str, object]:
    """Provider facts naming A's own oracle/argv: typed, but no full identity."""
    import sys

    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "typed facts",
            "design_facts": {
                "targets": [
                    {
                        "path": "src/widget.py",
                        "decision": "EXTEND",
                        "reason": "Widget already owns color.",
                    }
                ],
                "paradigm": "object_oriented",
                "decisions": ["Value one keeps color validation at construction."],
                "oracle": BLUE_ORACLE,
                "acceptance_supports": ["tests/support/blue_driver.py"],
                "verification": [[sys.executable, "-m", "pytest", BLUE]],
                "oracle_verification_index": 0,
            },
        }
    }


@pytest.mark.parametrize(
    "restore",
    ("full-same-code", "full-target-code-changed", "partial-provider-facts"),
)
def test_exact_design_restore_reuses_evidence_only_when_every_identity_matches(
    tmp_path: Path, restore: str
) -> None:
    subject = _Subject(tmp_path, None, shared=False).designed()
    _blue_design(subject)  # complete constructor DESIGN A
    subject.select("blue")
    assert subject.oracle("blue")[0] == 0 and subject.craft("blue")[0] == 0
    recorded = {"oracle": "recorded", "craft": "recorded"}
    assert _labels_of(subject.state()) == recorded
    kept, records = _acceptance_keys(subject.root), subject.rows()

    _restored_design(subject, "Intermediate B decision: validate at the boundary.")
    between = _labels_of(subject.state())
    assert between != recorded and "recorded" not in between.values(), (
        "WHAT: DESIGN B showed A's oracle/craft as current. WHY: B is a "
        "different complete design. HOW: judge currentness by design identity."
    )
    assert subject.rows() == records, "the intermediate B lost or bought records"
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
    if restore == "partial-provider-facts":
        code, out, err = _provider_design(subject, _blue_partial_facts())
        assert code == 0, out + err
    else:
        _blue_design(subject)  # exact restoration of complete DESIGN A
    assert _acceptance_keys(subject.root) == kept, "restoration rewrote B/A selection"
    spent = len(subject.rows())

    # `oracle=` and `craft=` are two DISTINCT native-git turn-record artifacts,
    # never the same fact under two names. The oracle record witnesses only
    # that an APPROVED oracle-authoring turn happened over the selected
    # acceptance bytes and the selected-revision identity; it carries no claim
    # about production target bytes, and no claim about a native pytest
    # execution result (RED/GREEN native evidence is a separate artifact,
    # produced by `des verify`, never read through `oracle=`/`craft=`). The
    # craft record witnesses that a crafting turn happened over the mutable
    # production targets TOGETHER WITH those same acceptance bytes. Moving
    # only mutable target code therefore moves the craft record's tree but
    # never the oracle record's: the two arms below diverge on exactly this.
    labels = _labels_of(subject.state())
    if restore == "full-same-code":
        assert labels == recorded, (
            "WHAT: exact restoration of DESIGN A (same selected revision, same "
            f"target bytes) left oracle={labels['oracle']} craft={labels['craft']}. "
            "WHY: the human chose reuse when ALL identities match; A's records "
            "are valid again. HOW: judge oracle/craft currentness by the matching "
            "design, revision and tree identities, never by history order."
        )
        assert subject.rows()[: len(records)] == records
        code, out, err, _new = subject.oracle("blue")
        assert "SelectedRevisionRealignmentNeeded" not in out + err
        assert spent == len(records), "restoration bought provider turns"
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
        assert subject.rows()[: len(records)] == records, "old records were not kept"
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
    assert subject.rows()[: len(records)] == records, "old records were not kept"
    value = json.loads((subject.root / HANDOVER).read_text())["values"][0]
    assert "design_semantic_sha256" not in value
    before = len(subject.rows())
    code, out, err, _ = subject.oracle("blue")
    assert code != 0 and "SelectedRevisionRealignmentNeeded" in out + err
    assert "--replace-current" in out + err
    assert len(subject.rows()) == before, "a misaligned selection bought a turn"


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
    historical, or `des verify` must refuse outright.
    """
    subject = _Subject(tmp_path, None, shared=False).designed()
    _blue_design(subject)
    assert subject.oracle("blue")[0] == 0 and subject.craft("blue")[0] == 0
    assert _labels_of(subject.state()) == {"oracle": "recorded", "craft": "recorded"}

    oracle_path = subject.root / BLUE
    original = oracle_path.read_text()
    assert "assert" in original
    oracle_path.write_text(
        "def test_selects_blue():\n    assert True  # weakened outside des oracle\n"
    )

    subject.verify()

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
