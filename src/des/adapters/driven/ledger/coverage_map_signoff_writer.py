"""coverage_map_signoff_writer -- deterministic ledger writer (slice-04 GREEN).

F-DISTILL-HUMAN-SIGNOFF slice-04. The deterministic engine function that
appends a ``CoverageMapSignedOff`` record to the per-feature HMAC-chained
AT-completion ledger AND projects the ``Coverage-Map-Signed-Off-By: <name>
<date>`` trailer from the ``## Signoff`` block.

Called ONLY from hook-invoked deterministic code (Ale 2026-05-24: nwave-dev
has NO sequencer / NO engine -- only hooks; the ledger writer is invoked by
hook-fired commands). The G5 two-layer architecture-test in slice-04 AT3
enforces a closed-world allowlist (``_ENGINE_CALLER_ALLOWLIST``) so an
LLM-agent dispatch path cannot reach this writer.

The trailer projection (§6.1) and the ledger record share ONE identity:
the §5.3 canonical-content digest carried by the ``## Signoff`` block.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger


if TYPE_CHECKING:
    from pathlib import Path


# G5 closed-world allowlist: the only modules permitted to call
# ``write_coverage_map_signed_off()``. Adding a caller requires a deliberate
# edit here (an architectural decision recorded in the diff). An LLM agent
# importing the function from anywhere else fails the slice-04 AT3 (b) check.
_ENGINE_CALLER_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Hooks fire the DISTILL-exit + DELIVER-exit touchpoints (slice-06 wires
        # them); both call sites are engine code.
        "src.des.adapters.drivers.hooks.distill_exit_hook",
        "src.des.adapters.drivers.hooks.deliver_exit_hook",
        # The verify CLI's emit-trailer subcommand records the signoff alongside
        # the trailer projection -- the trailer + ledger record are bound by
        # the same digest (slice-04 AT1).
        "scripts.cli.verify_coverage_map",
    }
)


# The conventional-commit trailer key the §6.1 projection emits.
_TRAILER_KEY: str = "Coverage-Map-Signed-Off-By"


# The fixed event-name appended to the per-feature AT-completion ledger.
_LEDGER_EVENT: str = "CoverageMapSignedOff"


# Pattern matching the ``- reviewed-content-digest: <hex>`` line.
_DIGEST_LINE_PATTERN = re.compile(
    r"^-\s*reviewed-content-digest:\s*([0-9a-f]+)\s*$", re.MULTILINE
)


def emit_trailer_from_signoff_block(coverage_map_path: Path) -> str:
    """Re-derive the ``Coverage-Map-Signed-Off-By: <name> <date>`` trailer line.

    Pure mechanical projection of the ``## Signoff`` block's ``name`` + ``date``
    fields onto the conventional-commit trailer (§6.1). The trailer is NEVER
    hand-authored -- a hand-edited trailer that diverges from this projection
    is refused with ``TrailerMismatch`` exit 1 at verify time.

    Returns the full trailer LINE (``Coverage-Map-Signed-Off-By: <name> <date>``)
    without a trailing newline. The verify CLI's ``emit-trailer`` subcommand
    prints this line on stdout.
    """
    body = coverage_map_path.read_text(encoding="utf-8")
    signer_name, signer_date = _extract_signoff_name_and_date(body)
    return f"{_TRAILER_KEY}: {signer_name} {signer_date}"


def write_coverage_map_signed_off(
    feature_id: str,
    project_root: Path,
    coverage_map_path: Path,
) -> dict[str, object]:
    """Append a ``CoverageMapSignedOff`` record to the AT-completion ledger.

    Reads the §5.3 canonical-content digest from the ``## Signoff`` block's
    ``reviewed-content-digest:`` line and appends a record carrying it to
    ``{project_root}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` under the
    M7 HMAC-chained write contract (``seq`` + ``record_hash`` for free).

    Returns the appended record. Hook-invoked only -- the G5 closed-world
    allowlist (``_ENGINE_CALLER_ALLOWLIST``) enforces this at the AST level.
    """
    body = coverage_map_path.read_text(encoding="utf-8")
    digest = _extract_reviewed_content_digest(body)
    signer_name, signer_date = _extract_signoff_name_and_date(body)
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=project_root)
    return ledger.append_coverage_map_signed_off(
        reviewed_content_digest=digest,
        signer_name=signer_name,
        signer_date=signer_date,
    )


def _extract_signoff_name_and_date(body: str) -> tuple[str, str]:
    """Parse ``- name:`` and ``- date:`` lines from the ``## Signoff`` block."""
    signer_name: str | None = None
    signer_date: str | None = None
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- name:"):
            signer_name = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- date:"):
            signer_date = stripped.split(":", 1)[1].strip()
    if signer_name is None or signer_date is None:
        raise ValueError(
            "## Signoff block is missing `- name:` or `- date:` -- "
            "the trailer + ledger record cannot be projected without both"
        )
    return signer_name, signer_date


def _extract_reviewed_content_digest(body: str) -> str:
    """Parse the ``- reviewed-content-digest: <hex>`` line."""
    match = _DIGEST_LINE_PATTERN.search(body)
    if match is None:
        raise ValueError(
            "## Signoff block is missing `- reviewed-content-digest:` -- "
            "the ledger record cannot be appended without the digest"
        )
    return match.group(1)
