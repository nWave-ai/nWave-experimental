"""RealFileSystemReader / RealFileSystemWriter — real I/O adapters."""

from __future__ import annotations

from pathlib import Path


class RealFileSystemReader:
    def read_text(self, path: Path | str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def probe(self) -> None:
        """Startup health check — verify filesystem is accessible."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as tmp:
            Path(tmp.name).write_text("probe", encoding="utf-8")


class RealFileSystemWriter:
    def write_text(self, path: Path | str, content: str) -> None:
        Path(path).write_text(content, encoding="utf-8")

    def probe(self) -> None:
        """Startup health check — DD-A5 fsync round-trip via shared helper."""
        from nwave_ai.feature_delta.adapters._fsync_probe import fsync_probe

        fsync_probe(probe_content=b"nwave-fs-probe", suffix=".txt")
