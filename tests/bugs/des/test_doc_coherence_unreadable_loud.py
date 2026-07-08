"""Regression (GDP-6 silent-undercount): `des verify-doc-coherence` must
degrade LOUD on an unreadable doc -- never silently skip it and PASS.

Charter: ``docs/product/expectations/fix-doc-coherence-unreadable-loud/
an-unreadable-doc-degrades-loud-never-silently-passes.md``.

Found in ``src/des/cli/verify_doc_coherence.py`` ``_scan_doc`` (~:374):

    try:
        text = doc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

On an unreadable doc (permission-denied, broken symlink, ...) this catches
the ``OSError`` and ``return``s SILENTLY -- the doc is never scanned, no
event is emitted naming it, and ``main()`` can still return exit 0
(``DocCoherenceVerified``) as if that doc were coherent. That is a
silent-undercount: an unreadable doc silently escapes the coherence check.

The fix direction (charter, NOT implemented here): mirror the existing
``_indeterminate(what, why, how)`` helper (already used for the no-docs-found
case, exit 2) and the per-doc ``DocCoherenceDocSkipped`` event pattern
(``_scan_doc`` ~:378) -- emit a visible event naming the unreadable doc file
AND make the gate exit non-zero (INDETERMINATE) rather than a clean PASS
while a doc went unread.

CRITICAL CONSTRAINT (preserved, do NOT change): the valid path is
unchanged -- a repo whose docs are ALL readable and coherent is scanned
normally and returns its usual verdict (exit 0, no spurious unreadable
event).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_doc_coherence.main()`` CLI driver, captured via
``capsys`` -- mirrors the sibling regression ATs
``tests/bugs/des/test_ledger_evidence_since_validated.py`` and
``tests/bugs/des/test_slice_at_completeness_incomplete_names_how.py``.

OSError trigger: the doc-enumeration filter (``_find_doc_files``) keeps only
``p.is_file()`` results -- a directory-as-``.md`` or a broken symlink is
filtered OUT there and never reaches ``_scan_doc`` (confirmed empirically:
``Path.is_file()`` follows symlinks and returns ``False`` on both a
directory-named-``.md`` and a broken symlink, so neither plants a bad path
through the real enumeration). A real file ``chmod``'d to ``0o000`` DOES
pass ``is_file()`` (permission bits don't affect that check) while
``read_text()`` raises ``PermissionError`` -- an ``OSError`` subclass --
confirmed empirically on this machine (non-root: chmod 0o000 blocks the
read). This is the trigger used below.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from des.cli.verify_doc_coherence import main as verify_doc_coherence_main


_UNREADABLE_SIGNAL_KEYWORDS = (
    "unreadable",
    "cannot be read",
    "could not be read",
    "permission",
    "oserror",
    "os error",
    "indeterminate",
)


def _run_gate(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Drive the REAL ``des verify-doc-coherence`` CLI (``main()``)
    in-process. Returns ``(exit_code, combined_stdout_stderr)``.
    """
    exit_code = verify_doc_coherence_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err


def _parse_json_lines(combined: str) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                payloads.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return payloads


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_unreadable_doc_degrades_loud_not_silently_passed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repo whose doc tree has ONE unreadable doc (permission-denied) and
    otherwise-coherent docs must NOT silently pass: the gate must (1) name
    the unreadable doc in a visible event/line, AND (2) not return a clean
    exit 0 while that doc went unread.

    RED today: ``_scan_doc`` catches the ``OSError`` from ``read_text`` and
    ``return``s silently -- the unreadable doc is never scanned, no event
    names it, and ``main()`` proceeds to the normal ``DocCoherenceVerified``
    exit-0 path because the one OTHER doc (readable, coherent) has zero
    violations. Both halves of the conjunction below are false today, so
    this fails with a semantic ``AssertionError`` on the silent-skip -- not
    a crash -- RED for the right reason.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Coherent Doc\n\nEverything documented here is true of the tree.\n"
    )
    unreadable = docs_dir / "unreadable.md"
    unreadable.write_text("# Unreadable\n\nThis content must never be scanned.\n")
    os.chmod(unreadable, 0o000)

    try:
        exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

        doc_rel = str(unreadable.relative_to(tmp_path))
        combined_lower = combined.lower()
        names_the_doc = doc_rel.lower() in combined_lower
        signals_unreadable = any(
            keyword in combined_lower for keyword in _UNREADABLE_SIGNAL_KEYWORDS
        )
        surfaced_visibly = names_the_doc and signals_unreadable

        assert exit_code != 0 and surfaced_visibly, (
            "an unreadable doc must degrade LOUD: the gate must not return "
            "a clean PASS (exit 0) while a doc went unread, AND must emit "
            f"a visible event naming the unreadable doc ({doc_rel!r}) -- "
            f"got exit_code={exit_code}, names_the_doc={names_the_doc}, "
            f"signals_unreadable={signals_unreadable}, output={combined!r}"
        )
    finally:
        # Restore readability so tmp_path teardown can remove the file.
        os.chmod(unreadable, stat.S_IRUSR | stat.S_IWUSR)


# ===========================================================================
# NEGATIVE AT -- control, green now AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_all_readable_docs_scan_normally_no_spurious_unreadable_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repo whose docs are ALL readable and coherent is unaffected by the
    fix: the gate returns its normal PASS (exit 0, ``DocCoherenceVerified``)
    with no spurious unreadable/indeterminate event. Must stay green both
    BEFORE and AFTER the fix.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Coherent Doc\n\nEverything documented here is true of the tree.\n"
    )
    (docs_dir / "other.md").write_text(
        "# Another Coherent Doc\n\nNothing here overstates the code.\n"
    )

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 0, (
        "an all-readable, coherent doc tree must still PASS (exit 0) -- got "
        f"exit_code={exit_code}; output={combined!r}"
    )
    combined_lower = combined.lower()
    for keyword in _UNREADABLE_SIGNAL_KEYWORDS:
        assert keyword not in combined_lower, (
            f"no doc was unreadable -- a spurious {keyword!r} signal must "
            f"not appear; output={combined!r}"
        )
    payloads = _parse_json_lines(combined)
    verified = next(
        (p for p in payloads if p.get("event") == "DocCoherenceVerified"), None
    )
    assert verified is not None, (
        f"expected a DocCoherenceVerified event; got {combined!r}"
    )
