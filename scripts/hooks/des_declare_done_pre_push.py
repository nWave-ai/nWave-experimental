"""Harness-neutral declare-done backstop: a git pre-push done-gate (DDD-2).

f-nonbypassable-attestation slice-01. The terminal "declare a feature done"
action in nWave-dev's dogfood is a ``git push`` of the feature branch. Before the
flow-v2 incident this was attested ONLY on the Claude-Code ``F_FINAL_REVIEW``
SubagentStop return -- a surface the incident's hand-dispatch never reached, so a
feature could be pushed "done" with a 0/7 feature-end ledger and nothing
objected.

This pre-push hook is the missing harness-neutral surface: it auto-fires the
SAME portable done-gate core (``des verify-integrity`` /
``verify_deliver_integrity.main``) on the terminal push action, INDEPENDENT of
any Claude-Code SubagentStop. It adds NO new decision logic -- it is a thin DDD-7
shim that REUSES the done-gate verbatim and PROPAGATES its veto (a non-zero exit
aborts the push).

Target-machine independence (AD-21/24): the gate logic is Python + filesystem.
git is the surface that TRIGGERS the backstop (a git pre-push hook), never a hard
dependency of the gate's verdict. When no feature is in flight (no
``docs/feature/*`` with a ledger) the backstop is a deterministic no-op (exit 0,
nothing to attest) -- it never blocks a push it has no feature to gate.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Bootstrap `des` onto sys.path for the dev-checkout case. A git pre-push hook
# runs with cwd = the pushed repo root, but this hook is installed OUTSIDE that
# repo (~/.claude/scripts/), so its own location does not locate `des`. In a
# source checkout `des` lives under `<repo>/src/`; prepend it so the import below
# resolves. Additive: when `des` is an installed package (target machine) it is
# already importable and this no-ops. Mirrors the 0854192ff subprocess-PYTHONPATH
# fix (the remaining pre-push site tracked by fe36796bc).
_des_src = Path.cwd() / "src"
if (_des_src / "des").is_dir() and str(_des_src) not in sys.path:
    sys.path.insert(0, str(_des_src))

from des.adapters.driven.logging.at_completion_ledger import (  # noqa: E402
    active_feature_id,
)
from des.cli import verify_deliver_integrity  # noqa: E402  (after sys.path bootstrap)


def main(argv: list[str] | None = None) -> int:
    """Auto-fire the portable done-gate on the terminal push; propagate its veto."""
    repo_root = Path.cwd()
    feature_id = active_feature_id(repo_root)
    if feature_id is None:
        return 0
    return verify_deliver_integrity.main(
        ["--repo", str(repo_root), "--feature-id", feature_id]
    )


if __name__ == "__main__":
    sys.exit(main())
