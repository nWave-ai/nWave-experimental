"""FeatureMigrator — application service for lossless .feature → embedded migration.

Design decisions:
  DD-A4: zero side effects — migration touches ONLY files inside target directory.
  DD-A7b: idempotency — re-run on already-migrated directory (detected by
          .feature.pre-migration presence) is a no-op with exit 0.
  DD-A7c: LoggingPort deferred — side-effect tracing via stderr/structured log.
  H11 spike: round-trip byte-identical (1-byte tolerance for trailing newline).

Round-trip invariant:
  1. Read .feature content (original).
  2. Embed as ```gherkin ... ``` block in feature-delta.md.
  3. Extract from feature-delta.md via GherkinExtractor.
  4. Compare extracted vs original: abs(len(extracted) - len(original)) <= 1.
  5. If comparison fails: raise MigrationAbortError (no file modifications).
  6. If comparison passes: rename .feature → .feature.pre-migration.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path


class MigrationAbortError(Exception):
    """Raised when the round-trip check fails.

    No file has been modified when this is raised.
    """


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of a FeatureMigrator.migrate() call."""

    embedded_count: int
    already_migrated: bool = False
    backup_paths: tuple[Path, ...] = field(default_factory=tuple)


class FeatureMigrator:
    """Migrate legacy .feature files into embedded gherkin blocks.

    Entry point (driving port): migrate(feature_dir: Path) -> MigrationResult.

    Raises MigrationAbortError if the round-trip check fails for any file.
    When MigrationAbortError is raised, no files have been modified.
    """

    def __init__(self, *, force_roundtrip_fail: bool = False) -> None:
        self._force_roundtrip_fail = force_roundtrip_fail

    # ------------------------------------------------------------------
    # Driving port
    # ------------------------------------------------------------------

    def migrate(self, feature_dir: Path) -> MigrationResult:
        """Embed .feature files into feature-delta.md with round-trip check.

        Args:
            feature_dir: directory containing .feature files and feature-delta.md.

        Returns:
            MigrationResult with embedded_count and backup_paths.

        Raises:
            MigrationAbortError: if round-trip check exceeds 1-byte tolerance.
                                  No files are modified when this is raised.
            FileNotFoundError: if feature_dir does not exist.
            ValueError: if feature_dir is not a directory.
        """
        feature_dir = Path(feature_dir)
        if not feature_dir.is_dir():
            raise ValueError(f"Not a directory: {feature_dir}")

        # DD-A7b: idempotency — detect .feature.pre-migration presence.
        pre_migration_files = list(feature_dir.glob("*.feature.pre-migration"))
        if pre_migration_files:
            return MigrationResult(embedded_count=0, already_migrated=True)

        feature_files = sorted(feature_dir.glob("*.feature"))
        if not feature_files:
            return MigrationResult(embedded_count=0)

        delta_path = feature_dir / "feature-delta.md"
        existing_delta = self._read_delta(delta_path)

        # Phase 1: Build the updated delta content (dry-run, in-memory).
        updated_delta = self._embed_all(existing_delta, feature_files)

        # Phase 2: Round-trip check — extract and compare (DD-A5 / H11 spike).
        self._assert_roundtrip(feature_files, updated_delta, delta_path)

        # Phase 3: Commit — all checks passed, write files.
        delta_path.write_text(updated_delta, encoding="utf-8")
        backup_paths: list[Path] = []
        for feature_file in feature_files:
            backup = feature_file.with_suffix(".feature.pre-migration")
            feature_file.rename(backup)
            backup_paths.append(backup)

        return MigrationResult(
            embedded_count=len(feature_files),
            backup_paths=tuple(backup_paths),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_delta(self, delta_path: Path) -> str:
        """Read existing feature-delta.md or return an empty scaffold."""
        if delta_path.exists():
            return delta_path.read_text(encoding="utf-8")
        stem = delta_path.parent.name
        return f"# {stem}\n\n## Wave: DISCUSS\n\n"

    def _embed_all(self, delta_text: str, feature_files: list[Path]) -> str:
        """Embed all .feature files as gherkin blocks into delta_text."""
        text = delta_text
        for feature_file in feature_files:
            content = feature_file.read_text(encoding="utf-8")
            text = self._embed_block(text, content)
        return text

    def _embed_block(self, delta_text: str, feature_content: str) -> str:
        """Append a fenced gherkin block to the last wave section.

        The block is appended after the last non-whitespace line of delta_text,
        separated by a blank line, then closed with ``` on its own line.
        """
        stripped = feature_content.rstrip("\n")
        block = f"\n\n```gherkin\n{stripped}\n```\n"
        return delta_text.rstrip("\n") + block

    def _assert_roundtrip(
        self,
        feature_files: list[Path],
        updated_delta: str,
        delta_path: Path,
    ) -> None:
        """Verify the round-trip invariant for all embedded files.

        Parses updated_delta with MarkdownSectionParser to extract the raw
        gherkin block strings, then compares them against the original .feature
        file contents. Raises MigrationAbortError if the byte difference
        exceeds 1 byte for any file.

        The extraction is done in-memory against updated_delta (not yet written
        to disk), so no files are touched if this fails.
        """
        if self._force_roundtrip_fail:
            raise MigrationAbortError(
                "round-trip check forced to fail (test mode). "
                "diff: forced loss > 1 byte."
            )

        from nwave_ai.feature_delta.domain.parser import MarkdownSectionParser

        model = MarkdownSectionParser().parse(updated_delta)
        extracted_blocks: list[str] = []
        for section in model.sections:
            extracted_blocks.extend(section.gherkin_blocks)

        if not extracted_blocks:
            raise MigrationAbortError(
                f"round-trip extraction yielded no gherkin blocks in {delta_path}"
            )

        original_contents = [f.read_text(encoding="utf-8") for f in feature_files]

        for i, (feature_file, original) in enumerate(
            zip(feature_files, original_contents, strict=False)
        ):
            if i >= len(extracted_blocks):
                raise MigrationAbortError(
                    f"round-trip check failed: expected {len(feature_files)} "
                    f"blocks, got {len(extracted_blocks)}"
                )
            block = extracted_blocks[i]
            original_stripped = original.rstrip("\n")
            block_stripped = block.rstrip("\n")
            diff_bytes = abs(len(original_stripped) - len(block_stripped))
            if diff_bytes > 1:
                diff_lines = list(
                    difflib.unified_diff(
                        original_stripped.splitlines(keepends=True),
                        block_stripped.splitlines(keepends=True),
                        fromfile=str(feature_file),
                        tofile="<round-tripped>",
                    )
                )
                diff_text = "".join(diff_lines)
                raise MigrationAbortError(
                    f"round-trip check failed for {feature_file.name}: "
                    f"diff exceeds 1-byte tolerance ({diff_bytes} bytes).\n"
                    f"diff:\n{diff_text}"
                )
