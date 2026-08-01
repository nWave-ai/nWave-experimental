"""Two shipped rejections whose HOW cannot be executed as written (D87, items 3-4).

CONTRACT_SHAPE: observable-outcome
Outcome anchor: a refused gate hands back a repair that WORKS when followed, and
grounds a symbol on the property (it is defined there) rather than the
designation (the characters appear somewhere in the file).

Measured 2026-07-30 in this worktree, both reproduced before this file was written:

1. ``scripts/cli/validate_component_manifest.py::_ground_sut`` decides a ``sut:``
   citation by SUBSTRING (``symbol not in candidate.read_text()``). A manifest
   citing ``src/des/application/deliver_loop_projection.py::_build_slice_rows``
   exits 0 -- "grounded" -- even though that file only MENTIONS the name inside a
   comment on line 91 and defines nothing of the sort. The gate's own docstring
   promises "every ``sut:`` symbol grep-findable in its cited file"; grep-findable
   is the designation, defined-there is the property (GDP-8).

2. ``src/des/cli/feature_delta_doctor.py::_sustainability_gaps`` prints a HOW that
   reads as an either/or: "Add the canonical heading with the table ... **or** a
   'Test-Reuse-Analysis: methodology-exempt' marker". The parser
   (``_classify_sustainability_exemption``) only ever looks for that marker among
   ``_sustainability_body_lines`` -- i.e. UNDER the canonical heading. A reader who
   takes the "or" as an alternative to the heading writes the marker alone and is
   refused again, with a detail that says "no section found" and never mentions
   that the marker needed a heading over it. Two independent readers took this in
   opposite directions on 2026-07-30 (GDP-3).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from des.cli.feature_delta_doctor import _sustainability_gaps
from des.cli.validate_feature_delta import (
    SUSTAINABILITY_HEADING,
    validate_sustainability_content,
)


REPO_ROOT = Path(__file__).resolve().parents[3]

#: A file that MENTIONS this name in a comment and defines nothing by it.
MENTION_ONLY_FILE = "src/des/application/deliver_loop_projection.py"
MENTION_ONLY_SYMBOL = "_build_slice_rows"

#: A file that really does define the name it is cited for -- the positive pin, so
#: a fix cannot pass this suite by rejecting everything.
DEFINED_FILE = "src/des/application/how_executability.py"
DEFINED_SYMBOL = "collect_invocations"


def _manifest(tmp_path: Path, sut: str) -> Path:
    path = tmp_path / "component-manifest.yaml"
    path.write_text(
        textwrap.dedent(
            f"""\
            schema-version: "1.0"
            feature-id: ground-sut-probe
            unbounded-input-domains:
              - id: probe-one
                sut: "{sut}"
                domain: "any string"
                why-unbounded: "probe"
                canonical-category: C2
                declared-at: design
            """
        ),
        encoding="utf-8",
    )
    return path


def _run_manifest_gate(manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.cli.validate_component_manifest",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def test_a_symbol_that_only_appears_in_a_comment_is_not_reported_grounded(
    tmp_path: Path,
) -> None:
    """RED before the fix: the substring read calls a comment a definition."""
    mentions = (REPO_ROOT / MENTION_ONLY_FILE).read_text(encoding="utf-8")
    assert MENTION_ONLY_SYMBOL in mentions, (
        "the fixture premise is gone: the probe file no longer mentions the symbol, "
        "so this test would pass for the wrong reason"
    )

    completed = _run_manifest_gate(
        _manifest(tmp_path, f"{MENTION_ONLY_FILE}::{MENTION_ONLY_SYMBOL}")
    )

    assert completed.returncode != 0, (
        f"the manifest gate reported a comment-only mention as grounded "
        f"(exit {completed.returncode}). It decided on the designation (the "
        f"characters are in the file) instead of the property (the symbol is "
        f"defined there).\nstdout={completed.stdout}\nstderr={completed.stderr}"
    )


def test_a_symbol_that_is_really_defined_is_still_reported_grounded(
    tmp_path: Path,
) -> None:
    """The positive pin: the fix must not reject every citation."""
    completed = _run_manifest_gate(
        _manifest(tmp_path, f"{DEFINED_FILE}::{DEFINED_SYMBOL}")
    )

    assert completed.returncode == 0, (
        f"a genuinely defined symbol was refused (exit {completed.returncode}); "
        f"the fix over-rejects.\nstdout={completed.stdout}\nstderr={completed.stderr}"
    )


def test_a_stale_symbol_refusal_explains_what_why_and_how(tmp_path: Path) -> None:
    """RED before the fix: the staleness diagnostic is a bare WHAT.

    ``manifest is stale: symbol 'X' not found in Y`` names the WHAT and nothing
    else -- no WHY the manifest gate cares, and no HOW to repair it (GDP-3).
    """
    completed = _run_manifest_gate(
        _manifest(tmp_path, f"{MENTION_ONLY_FILE}::definitely_not_defined_anywhere")
    )
    message = completed.stdout + completed.stderr

    assert completed.returncode != 0, "the fixture did not produce a refusal"
    assert "WHY" in message, f"the staleness refusal states no WHY:\n{message}"
    assert "HOW" in message, f"the staleness refusal states no HOW:\n{message}"


def test_the_missing_manifest_how_names_a_command_that_exists(tmp_path: Path) -> None:
    """RED before the fix: the HOW points at a producing tool nobody shipped.

    The message says "generate it with the design wave's producing tool" without
    naming it. There IS no such producer -- the architect hand-authors the file --
    so the HOW is a designation with no referent (GDP-8 authoring corollary) and
    cannot be executed as written (GDP-4). The honest repair either names a real
    command or says plainly that the file is hand-authored and against which
    schema.
    """
    completed = _run_manifest_gate(tmp_path / "does-not-exist.yaml")
    message = completed.stdout + completed.stderr

    assert completed.returncode != 0, "a missing manifest did not refuse"
    assert "the design wave's producing tool" not in message, (
        "the HOW still gestures at an unnamed 'producing tool'. Name a command "
        f"that exists, or say the file is hand-authored:\n{message}"
    )
    names_something_real = (
        "scripts.cli.validate_component_manifest" in message
        or "component-manifest.schema.json" in message
    )
    assert names_something_real, (
        "the HOW names no executable command and no schema the author could work "
        f"against:\n{message}"
    )


# ---------------------------------------------------------------------------
# 2. the sustainability HOW offers a choice its parser does not accept
# ---------------------------------------------------------------------------

MARKER = "Test-Reuse-Analysis: methodology-exempt"


def test_the_marker_alone_is_refused_by_the_parser() -> None:
    """The parser property this HOW must not misdescribe. GREEN today.

    Pinned so a future 'fix' cannot make the HOW true by widening the parser
    without saying so: if this ever goes RED, the contract moved and the HOW
    assertion below must be revisited deliberately.
    """
    result = validate_sustainability_content(f"# delta\n\n{MARKER}\n")

    assert result.verdict == "missing-sustainability-section", (
        f"the marker alone now parses as {result.verdict!r}; the parser contract "
        "changed and the HOW wording below must be re-decided"
    )


def test_the_marker_under_the_heading_is_accepted() -> None:
    """The shape the HOW should be describing. GREEN today."""
    result = validate_sustainability_content(
        f"# delta\n\n{SUSTAINABILITY_HEADING}\n\n{MARKER}\n"
    )

    assert result.verdict == "methodology-exempt", (
        f"the marker under the canonical heading was not accepted: {result.verdict}"
    )


@pytest.mark.parametrize("content", ["# delta\n\nnothing here\n"])
def test_the_sustainability_how_does_not_offer_the_marker_as_an_alternative_to_the_heading(
    content: str,
) -> None:
    """RED before the fix: the HOW reads as heading-OR-marker.

    The parser reaches the marker only INSIDE the section, so the heading is
    required on BOTH branches. A HOW that says "or a marker" hands the reader a
    repair that gets refused a second time.
    """
    gaps = _sustainability_gaps(content)

    assert len(gaps) == 1, f"expected exactly one sustainability gap, got {gaps}"
    how = gaps[0]["how"]

    assert MARKER in how, (
        "the HOW no longer mentions the exemption marker at all; that removes the "
        "lie by removing the information, which is not the repair"
    )
    marker_at = how.index(MARKER)
    prefix = how[:marker_at].lower()
    assert "under" in prefix or "inside" in prefix or "beneath" in prefix, (
        "the HOW still offers the marker without saying it must sit UNDER the "
        f"canonical heading. A reader who writes the marker alone is refused "
        f"again:\n{how}"
    )
