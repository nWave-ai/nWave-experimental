"""
Behavioral probe tests — fault injection per adapter (DD-A5).

Every driven adapter in nwave_ai/feature_delta/adapters/ is exercised with
an injected substrate fault so that probe() raises (or the test asserts
the correct health signal at the composition root).

Test budget: 5 adapter fault behaviors * 2 = 10 max unit tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 1. SystemClock — time never goes backwards
# ---------------------------------------------------------------------------


class TestSystemClockProbe:
    def test_probe_succeeds_when_clock_advances(self) -> None:
        """probe() completes without raising on a normally-advancing clock."""
        from nwave_ai.feature_delta.adapters.clock import SystemClock

        clock = SystemClock()
        clock.probe()  # must not raise

    def test_probe_raises_when_clock_goes_backwards(self) -> None:
        """probe() raises ProbeFailure when mocked clock regresses."""
        from nwave_ai.feature_delta.adapters.clock import SystemClock

        clock = SystemClock()
        # Inject a regressing clock: now() returns 100.0 first, then 50.0
        call_count = 0

        def _regressing_now() -> float:
            nonlocal call_count
            call_count += 1
            return 100.0 if call_count == 1 else 50.0

        clock.now = _regressing_now  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="clock"):
            clock.probe()


# ---------------------------------------------------------------------------
# 2. JsonSchemaFileLoader — corrupted JSON causes probe failure
# ---------------------------------------------------------------------------


class TestJsonSchemaFileLoaderProbe:
    def test_probe_exits_70_on_corrupted_json(self, tmp_path: Path) -> None:
        """probe() calls sys.exit(70) when schema file is not valid JSON."""
        from nwave_ai.feature_delta.adapters.schema import JsonSchemaFileLoader

        broken = tmp_path / "bad-schema.json"
        broken.write_text("{not json", encoding="utf-8")

        loader = JsonSchemaFileLoader(schema_path=broken)
        with pytest.raises(SystemExit) as exc_info:
            loader.probe()
        assert exc_info.value.code == 70

    def test_probe_exits_70_on_missing_schema_file(self, tmp_path: Path) -> None:
        """probe() calls sys.exit(70) when schema file does not exist."""
        from nwave_ai.feature_delta.adapters.schema import JsonSchemaFileLoader

        missing = tmp_path / "nonexistent.json"
        loader = JsonSchemaFileLoader(schema_path=missing)
        with pytest.raises(SystemExit) as exc_info:
            loader.probe()
        assert exc_info.value.code == 70


# ---------------------------------------------------------------------------
# 3. PlaintextVerbLoader — missing verb file causes probe failure
# ---------------------------------------------------------------------------


class TestPlaintextVerbLoaderProbe:
    def test_probe_exits_70_when_verb_file_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """probe() refuses LOUDLY (exit 70) when en.txt is absent or empty (D-6a).

        This used to be a bare ``assert``, whose ``AssertionError`` escaped
        ``cli.py`` (which catches only ``ReDoSError``) and reached the maintainer
        as a RAW TRACEBACK — the shipped product's actual behaviour, and output
        they cannot act on. It now refuses exactly like every other adapter:
        the structured ``health.startup.refused`` event naming this adapter and
        the cure, then exit 70 (GDP-3 / GDP-6). Same contract as
        ``TestJsonSchemaFileLoaderProbe`` above.
        """
        from nwave_ai.feature_delta.adapters import verbs as verbs_module
        from nwave_ai.feature_delta.adapters.verbs import PlaintextVerbLoader

        # Point _VERB_DIR to a tmp directory with no en.txt
        empty_dir = tmp_path / "protocol-verbs"
        empty_dir.mkdir()
        monkeypatch.setattr(verbs_module, "_VERB_DIR", empty_dir)

        loader = PlaintextVerbLoader(cwd_root=tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            loader.probe()

        assert exc_info.value.code == 70
        refusal = capsys.readouterr().err
        assert "health.startup.refused" in refusal
        assert "PlaintextVerbLoader" in refusal
        assert "reinstall" in refusal.lower(), (
            "the refusal must tell the maintainer HOW to fix it, not just that "
            f"a file is missing: {refusal!r}"
        )


# ---------------------------------------------------------------------------
# 4. RealFileSystemWriter — write-then-read inconsistency causes probe failure
# ---------------------------------------------------------------------------


class TestRealFileSystemWriterProbe:
    def test_probe_raises_when_readback_differs(self) -> None:
        """probe() raises RuntimeError when fsync+readback returns different bytes."""
        from nwave_ai.feature_delta.adapters.filesystem import RealFileSystemWriter

        writer = RealFileSystemWriter()

        def _wrong_readback(self: Path) -> bytes:
            return b"corrupted"

        with patch.object(Path, "read_bytes", _wrong_readback):
            with pytest.raises(RuntimeError, match="Filesystem probe failed"):
                writer.probe()


# ---------------------------------------------------------------------------
# 5. MigrationApplier — inherits filesystem write probe (same contract)
# ---------------------------------------------------------------------------


class TestMigrationApplierProbe:
    def test_probe_raises_when_filesystem_inconsistent(self) -> None:
        """probe() raises RuntimeError on filesystem write/read inconsistency."""
        from nwave_ai.feature_delta.adapters.migration import MigrationApplier

        applier = MigrationApplier()

        def _wrong_readback(self: Path) -> bytes:
            return b"wrong"

        with patch.object(Path, "read_bytes", _wrong_readback):
            with pytest.raises(RuntimeError, match="Filesystem probe failed"):
                applier.probe()


# ---------------------------------------------------------------------------
# 6. RealFileSystemReader — read probe fails when tmpfile unreadable
# ---------------------------------------------------------------------------


class TestRealFileSystemReaderProbe:
    def test_probe_raises_when_write_fails(self) -> None:
        """probe() propagates OSError when the temp directory is unwritable."""
        from nwave_ai.feature_delta.adapters.filesystem import RealFileSystemReader

        reader = RealFileSystemReader()

        # Patch write_text to raise OSError — simulates unwritable filesystem
        with patch.object(Path, "write_text", side_effect=OSError("read-only fs")):
            with pytest.raises(OSError, match="read-only fs"):
                reader.probe()


# ---------------------------------------------------------------------------
# 7. PlaintextKeywordLoader — missing keyword file causes probe failure
# ---------------------------------------------------------------------------


class TestPlaintextKeywordLoaderProbe:
    def test_probe_exits_70_when_keyword_file_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """probe() refuses LOUDLY (exit 70) when en.txt is absent or empty (D-6a).

        Was a bare ``assert``; now the same structured refusal every other
        adapter emits — a damaged install is a damaged install, whichever asset
        is the casualty, and the maintainer is told which adapter refused and
        how to cure it.
        """
        from nwave_ai.feature_delta.adapters import gherkin as gherkin_module
        from nwave_ai.feature_delta.adapters.gherkin import PlaintextKeywordLoader

        # Point _KEYWORD_DIR to a tmp directory with no en.txt
        empty_dir = tmp_path / "gherkin-keywords"
        empty_dir.mkdir()
        monkeypatch.setattr(gherkin_module, "_KEYWORD_DIR", empty_dir)

        loader = PlaintextKeywordLoader()
        with pytest.raises(SystemExit) as exc_info:
            loader.probe()

        assert exc_info.value.code == 70
        refusal = capsys.readouterr().err
        assert "health.startup.refused" in refusal
        assert "PlaintextKeywordLoader" in refusal
        assert "reinstall" in refusal.lower(), (
            "the refusal must tell the maintainer HOW to fix it, not just that "
            f"a file is missing: {refusal!r}"
        )
