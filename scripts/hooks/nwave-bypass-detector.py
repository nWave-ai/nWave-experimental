#!/usr/bin/env python3
"""nWave Bypass Detector -- post-commit hook.

Records every commit, and records LOUDLY when one skipped verification.

ORDER IS THE CONTRACT HERE, and it is why this file is shaped the way it is.
The detection signal -- did pre-commit run? -- and the human-facing BYPASS line
need nothing but git and the filesystem. The structured audit event needs the DES
package. Those are two different fragilities, and the earlier version fused them:
the DES import came FIRST, inside one broad `try`, so when
`des.adapters.driven.logging.audit_logger` was deleted on 2026-02-06 the
ModuleNotFoundError was swallowed by `except Exception: return 0` and the hook
stopped doing ALL of its jobs at once -- silently, for five months.

Worse than the missing event: the marker was never consumed either, because that
code sat downstream of the failing import. So a later partial repair -- fixing
only the import -- would have read a stale marker and reported the next
`--no-verify` commit as verified. A false negative is worse than the outage.

So: git-and-filesystem work first and unconditionally, the optional structured
event last and separately guarded. If the DES package breaks again, this hook
still detects the bypass and still writes the line a human reads.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _git_dir() -> Path:
    return Path(
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or ".git"
    )


def _consume_marker(git_dir: Path) -> bool:
    """True when pre-commit did NOT run (the bypass signal).

    The marker is written only by the pre-commit stage, which `--no-verify`
    skips; post-commit is not skipped, so this hook always runs and can observe
    the absence. Consuming it here -- BEFORE anything that can raise -- is what
    keeps the next commit's detection honest.
    """
    marker = git_dir / ".nwave-precommit-ran"
    ran = marker.exists()
    if ran:
        try:
            marker.unlink()
        except OSError:
            pass
    return not ran


def _head_commit() -> tuple[str, str, str]:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H|%s|%an"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ("unknown", "unknown", "unknown")
    parts = result.stdout.strip().split("|", 2)
    while len(parts) < 3:
        parts.append("unknown")
    return (parts[0], parts[1], parts[2])


def _write_bypass_line(git_dir: Path, commit_hash: str) -> None:
    """The line a human reads. Needs no DES import, so it is never lost with one."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = (
        f"{stamp} | {commit_hash[:8]} | BYPASS | --no-verify used | ⚠️ AUDIT REQUIRED\n"
    )
    try:
        log = git_dir / "hooks" / "pre-commit.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def _log_audit_event(
    commit_hash: str, subject: str, author: str, no_verify: bool
) -> None:
    """The structured event. Optional by design, and guarded ALONE.

    Its failure must never take the detection with it -- that coupling is the
    defect this file exists to not repeat.
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from des.adapters.driven.config.des_config import DESConfig
        from des.adapters.driven.logging.audit_events import AuditEvent
        from des.adapters.driven.logging.jsonl_audit_log_writer import (
            JsonlAuditLogWriter,
        )

        if not DESConfig().audit_logging_enabled:
            return
        JsonlAuditLogWriter().log_event(
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event="GIT_COMMIT",
                commit_hash=commit_hash,
                outcome="BYPASS" if no_verify else "VERIFIED",
                extra_context={
                    "commit": commit_hash[:8],
                    "subject": subject,
                    "author": author,
                    "no_verify": no_verify,
                },
            )
        )
    except Exception:
        pass


def main() -> int:
    git_dir = _git_dir()
    no_verify = _consume_marker(git_dir)
    commit_hash, subject, author = _head_commit()

    if no_verify:
        _write_bypass_line(git_dir, commit_hash)

    _log_audit_event(commit_hash, subject, author, no_verify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
