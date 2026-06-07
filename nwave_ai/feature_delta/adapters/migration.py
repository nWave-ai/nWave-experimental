"""MigrationApplier — adapter that wires FeatureMigrator to the CLI.

Responsibilities:
  - Resolve the feature_dir path (absolute or relative to cwd).
  - Invoke FeatureMigrator.migrate().
  - Format exit code and stderr messages for the CLI surface.
  - probe(): startup health check (filesystem writable).
"""

from __future__ import annotations

import sys
from pathlib import Path


class MigrationApplier:
    """CLI adapter for the FeatureMigrator application service.

    Entry point: apply(feature_dir_str, cwd) -> int (exit code).
    """

    def apply(self, feature_dir_str: str, cwd: Path | None = None) -> int:
        """Run migration on feature_dir_str; return exit code.

        Args:
            feature_dir_str: path to the feature directory (absolute or
                             relative to cwd).
            cwd: working directory to resolve relative paths against.
                 Defaults to Path.cwd().

        Returns:
            0  — migration succeeded or directory already migrated.
            1  — round-trip check failed or other error.
        """
        from nwave_ai.feature_delta.application.migrator import (
            FeatureMigrator,
            MigrationAbortError,
        )

        base = cwd if cwd is not None else Path.cwd()
        feature_dir = Path(feature_dir_str)
        if not feature_dir.is_absolute():
            feature_dir = base / feature_dir

        if not feature_dir.exists():
            print(
                f"ERROR: directory not found: {feature_dir_str}",
                file=sys.stderr,
            )
            return 1

        if not feature_dir.is_dir():
            print(
                f"ERROR: not a directory: {feature_dir_str}",
                file=sys.stderr,
            )
            return 1

        try:
            result = FeatureMigrator().migrate(feature_dir)
        except MigrationAbortError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"ERROR: filesystem error: {exc}", file=sys.stderr)
            return 1

        if result.already_migrated:
            print(
                f"already migrated: {feature_dir_str} "
                "(found .feature.pre-migration backup — skipping)",
                file=sys.stderr,
            )
            return 0

        print(
            f"migrated {result.embedded_count} file(s) in {feature_dir_str}",
            file=sys.stdout,
        )
        return 0

    def probe(self) -> None:
        """Startup health check — DD-A5 fsync round-trip via shared helper."""
        from nwave_ai.feature_delta.adapters._fsync_probe import fsync_probe

        fsync_probe(probe_content=b"nwave-migration-probe", suffix=".probe")
