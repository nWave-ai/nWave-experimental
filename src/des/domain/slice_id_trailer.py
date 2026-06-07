"""Pure parsing of ``Slice-Id:`` / ``Step-Id:`` commit-message trailers.

The single SSOT for extracting the ``slice-NN`` identities a commit message
carries. This is pure-function domain logic -- a regex over a string with no
filesystem, subprocess, or CLI dependency -- so it lives in the domain layer.

The CLI driving port (``des.cli.verify_slice_commit_completeness``) and the
hook adapters (``carpaccio_intercept``, ``earned_verdict_commit_gate_hook``)
all import these helpers from here. Previously they lived in the CLI module and
were imported DOWNWARD by the adapters, inverting the hexagonal layering
(AD-05). Domain logic must never live in the drivers layer.
"""

from __future__ import annotations

import re


_SLICE_ID_TRAILER_RE = re.compile(
    # Capture canonical `slice-NN` or letter-suffix `slice-NNa` as group 1.
    # Optionally consume (but not capture) phase suffix `-A_GREEN_ATS` etc --
    # commit trailers carry the phase as a marker; the slice identity is the
    # bare slice-NN[-letter]. Closes friction #10 cascade-blocker (Slice-Id:
    # slice-02-A_GREEN_ATS rejection blocking M71 backfill).
    r"^(?:Slice-Id|Step-Id):\s*(slice-\d+(?:[a-z])?)(?:-[A-Z][A-Z_]*)?\s*$"
)


def extract_slice_ids(commit_message: str) -> list[str]:
    """Return every `slice-NN` carried by a `Slice-Id:`/`Step-Id:` trailer.

    A batched commit lists each slice it covers as a separate trailer line.
    Order of first appearance is preserved; duplicates are collapsed so a
    repeated trailer does not double-verify the same slice.
    """
    ordered: list[str] = []
    for line in commit_message.splitlines():
        match = _SLICE_ID_TRAILER_RE.match(line.strip())
        if match:
            slice_id = match.group(1)
            if slice_id not in ordered:
                ordered.append(slice_id)
    return ordered


def extract_slice_id(commit_message: str) -> str | None:
    """Return the FIRST `slice-NN` carried by a `Slice-Id:`/`Step-Id:` trailer.

    Retained for backward compatibility; prefer ``extract_slice_ids`` which
    returns every listed slice (the F-07 multi-trailer shape).
    """
    slice_ids = extract_slice_ids(commit_message)
    return slice_ids[0] if slice_ids else None
