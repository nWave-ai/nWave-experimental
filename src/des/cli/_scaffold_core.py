"""Shared SCAFFOLD-FAMILY primitives for the DES CLI surface (D49, mikado
2026-07-29 -- Ale-ratified unification: "queste sono tutte violazioni di
SSOT ... va unificato in modo da estendere e gestirlo UN SOLO POSTO").

Three ``des`` subcommands are all "the producing tool for an artifact another
gate consumes" (GDP-4/5): ``charter-scaffold``, ``examine-fixture``,
``flavor-scaffold``. Each was written separately and copy-pasted the same two
decisions (a fourth, ``feature-end-preconditions-scaffold``, has since been
deleted):

1. **What to do when the target already exists** -- ``charter-scaffold``
   skips silently (idempotent no-op, ``accepted`` verdict);
   ``flavor-scaffold`` refuses unless ``--force``;
   ``examine-fixture`` unconditionally destroys and rebuilds (its target is a
   disposable fixture repo, not a document a human fills in). These are not
   four different bugs -- they are ONE decision (skip / refuse / rebuild)
   made four times, independently. ``decide_on_exists`` is now the single
   place that decision is made; each caller declares its policy instead of
   hand-rolling the branch.

2. **How a verdict token becomes a JSON stdout line + an exit code.**
   ``charter_scaffold._degrade`` printed a payload dict containing a
   ``verdict`` key and returned ``0`` when it equalled ``VERDICT_ACCEPTED``,
   ``1`` otherwise -- a decision each scaffold re-derived byte-identically. ``emit_scaffold_verdict`` is now the one
   place that mapping lives.

WHAT THIS DOES **NOT** UNIFY. ``flavor-scaffold``'s success/refuse output is
plain YAML text + distinct numeric exit codes (1/2/3) piped straight into a
file by callers -- that is a DECLARED, different failure channel, not a
duplicate of the JSON-verdict channel, and changing its shape would break
every consumer of ``--stdout``. It reuses ``decide_on_exists`` for the
exists-decision (the axis it genuinely shares) but keeps its own emission
shape. ``examine-fixture``'s SUCCESS payload (``{repo, feature_id,
shipped_slice, ...}``) is bespoke -- a fixture-driving contract, not a
verdict envelope -- and stays exactly as it was; only its previously-ABSENT
FAILURE path now routes through ``emit_scaffold_verdict`` (a strict
improvement: a git/ledger failure used to raise an uncaught exception --
`CalledProcessError`/`OSError` -- straight to a raw traceback; it now
degrades LOUD with the same JSON verdict vocabulary the other two scaffolds
already use). ``ScaffoldDegradeError`` is the shared signal for that path.

Three-to-nine honest variants beat one shape that lies about a fourth
(``_emit_json.py``'s own words) -- this module collapses exactly the two
decisions proven duplicated above, and no further.
"""

from __future__ import annotations

import json
from typing import Literal


#: The three declared behaviours a scaffold generator can have when its
#: target already exists on disk. A caller with ``force=True`` overrides
#: ``"refuse"`` to a write regardless of policy (``flavor-scaffold``'s
#: ``--force`` escape hatch) -- no other policy is affected by ``force``.
ExistsPolicy = Literal["skip", "refuse", "rebuild"]

#: The verdict token `charter_scaffold`
#: (and, for its new failure path, `examine_fixture`) already share via
#: `des.cli.validate_feature_delta.VERDICT_ACCEPTED`. Re-declared here as the
#: plain string literal (not imported) to keep this module free of a
#: dependency on the feature-delta parser -- the two modules that import both
#: already guarantee the two constants can never drift (see
#: `test_scaffold_core_accepted_matches_validate_feature_delta`).
_ACCEPTED_VERDICT = "accepted"


def decide_on_exists(
    *, target_exists: bool, policy: ExistsPolicy, force: bool = False
) -> Literal["write", "skip", "refuse", "rebuild"]:
    """The ONE place a `des.cli` scaffold generator decides what happens when
    its target already exists. Pure.

    - ``target_exists=False`` -> always ``"write"`` (the policy only governs
      the exists-branch; a fresh target is always written, regardless of
      declared policy).
    - ``target_exists=True, force=True`` -> always ``"write"`` (the
      `flavor-scaffold` ``--force`` escape hatch: overrides ANY policy).
    - ``target_exists=True, force=False`` -> the declared ``policy`` verbatim
      (``"skip"`` for an idempotent no-op, ``"refuse"`` for a hard reject,
      ``"rebuild"`` for a destroy-and-recreate).
    """
    if not target_exists or force:
        return "write"
    return policy


class ScaffoldDegradeError(Exception):
    """Raised by a scaffold generator's build step when an underlying
    operation it cannot control (a git subprocess, a ledger write) fails.
    Caught by the subcommand's own `main` and turned into the shared JSON
    degrade-LOUD verdict envelope via `emit_scaffold_verdict` -- never an
    uncaught traceback (GDP-6: no silent-wrong, degrade LOUD)."""

    def __init__(self, verdict: str, detail: str) -> None:
        super().__init__(detail)
        self.verdict = verdict
        self.detail = detail


def emit_scaffold_verdict(
    payload: dict[str, object], *, accepted: str = _ACCEPTED_VERDICT
) -> int:
    """Print `payload` (which MUST carry a `"verdict"` key) as one line of
    JSON to stdout, and return the shared scaffold exit-code convention: `0`
    when `payload["verdict"] == accepted`, `1` otherwise.

    The ONE place a `des.cli` scaffold generator maps its verdict token to an
    exit code -- `charter_scaffold._degrade` and
    each scaffold's private `_emit` independently re-derived this
    exact mapping before this module existed (D49, mikado 2026-07-29).
    """
    print(json.dumps(payload))
    return 0 if payload.get("verdict") == accepted else 1
