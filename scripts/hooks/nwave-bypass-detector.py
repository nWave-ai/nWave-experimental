#!/usr/bin/env python3
"""nWave Bypass Detector - Post-commit hook."""

import sys
from pathlib import Path


def main():
    """Log commit for audit purposes using DES audit logger."""
    try:
        # Add src to path to import DES modules
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        # Import DES config and audit logger
        from src.des.adapters.driven.config.des_config import DESConfig
        from src.des.adapters.driven.logging.audit_logger import log_audit_event

        # Check if audit logging is enabled
        config = DESConfig()
        if not config.audit_logging_enabled:
            return 0

        # Get commit info
        import subprocess
        from datetime import datetime, timezone

        # Resolve $GIT_DIR to read the pre-commit "ran" marker. The marker is
        # written ONLY by the pre-commit stage (nwave_precommit_marker); a
        # `git commit --no-verify` skips pre-commit, so an ABSENT marker is the
        # reliable signal of a verification bypass. post-commit is NOT skipped by
        # --no-verify, so this detector always runs and can observe the absence.
        # (The prior PRE_COMMIT_ALLOW_NO_CONFIG env check never fired and silently
        # logged every --no-verify commit as a normal one.)
        git_dir = (
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            or ".git"
        )
        marker = Path(git_dir) / ".nwave-precommit-ran"
        no_verify = not marker.exists()
        if marker.exists():
            try:
                marker.unlink()  # consume so the next commit re-detects freshly
            except OSError:
                pass

        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%an"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            parts = result.stdout.strip().split("|", 2)
            if len(parts) >= 3:
                commit_hash, subject, author = parts
            else:
                commit_hash = parts[0] if parts else "unknown"
                subject = parts[1] if len(parts) > 1 else "unknown"
                author = "unknown"

            # Log to DES audit log
            log_audit_event(
                event_type="GIT_COMMIT",
                commit=commit_hash[:8],
                commit_full=commit_hash,
                subject=subject,
                author=author,
                no_verify=no_verify,
            )

            # Restore the human-facing bypass audit log so a --no-verify commit is
            # loudly recorded for review (the Feb-era format Ale relies on).
            if no_verify:
                stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                log_line = (
                    f"{stamp} | {commit_hash[:8]} | BYPASS | --no-verify used "
                    f"| ⚠️ AUDIT REQUIRED\n"
                )
                try:
                    with (Path(git_dir) / "hooks" / "pre-commit.log").open(
                        "a", encoding="utf-8"
                    ) as handle:
                        handle.write(log_line)
                except OSError:
                    pass

        return 0

    except Exception:
        # Never block on audit failures
        return 0


if __name__ == "__main__":
    sys.exit(main())
