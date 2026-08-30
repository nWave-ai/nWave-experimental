"""Regression tests for the immutable public-candidate handoff."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.release.prepare_public_candidate import (
    CandidatePreparationError,
    build_manifest,
)


def _candidate(tmp_path: Path, candidate_line: str) -> Path:
    wheel = tmp_path / "nwave_ai-4.0.0-py3-none-any.whl"
    wheel.write_bytes(b"reviewed candidate bytes")
    wheelhouse = tmp_path / "offline-wheelhouse"
    wheelhouse.mkdir()
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (wheelhouse / "requirements.lock").write_text(
        "packaging==26.0 --hash=sha256:"
        + "0" * 64
        + "\n"
        + candidate_line.format(wheel=wheel, name=wheel.name, digest=digest)
        + "\n",
        encoding="utf-8",
    )
    return wheel


def test_manifest_accepts_the_canonical_relocatable_candidate_reference(
    tmp_path: Path,
) -> None:
    wheel = _candidate(tmp_path, "../{name} --hash=sha256:{digest}")

    manifest = build_manifest(wheel)

    assert (
        manifest["artifact"]["sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    )


def test_manifest_ignores_blank_lock_lines(tmp_path: Path) -> None:
    wheel = _candidate(tmp_path, "\n../{name} --hash=sha256:{digest}\n")

    assert build_manifest(wheel)["artifact"]


@pytest.mark.parametrize(
    "candidate_line",
    [
        "nwave-ai==4.0.0 --hash=sha256:{digest}",
        "../{name} --hash=sha256:" + "f" * 64,
        "https://example.invalid/{name} --hash=sha256:{digest}",
        "{wheel} --hash=sha256:{digest}",
    ],
)
def test_manifest_rejects_an_unbound_or_nonportable_candidate_reference(
    tmp_path: Path, candidate_line: str
) -> None:
    wheel = _candidate(tmp_path, candidate_line)

    with pytest.raises(CandidatePreparationError):
        build_manifest(wheel)


def test_manifest_rejects_duplicate_candidate_references(tmp_path: Path) -> None:
    line = "../{name} --hash=sha256:{digest}"
    wheel = _candidate(tmp_path, line + "\n" + line)

    with pytest.raises(CandidatePreparationError, match="2 times"):
        build_manifest(wheel)
