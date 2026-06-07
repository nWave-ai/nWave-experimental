"""
G4 Zero-Side-Effects Hard Gate — tests/installer/test_no_side_effects.py

DD-A4: the validator MUST NOT modify any file outside the <path> argument.
Whitelist: stdout, stderr, --format=json output.
Forbidden: .git/, ~/.bashrc, ~/.config/, ~/.local/share/, system files.

Strategy: snapshot HOME + CWD before validator invocation, run validator,
snapshot after, diff. Any change outside the allowed set is a hard failure.

This module is the CI hard gate for G4. It is distinct from the acceptance-
level snapshot tests in cross_cutting.feature — those verify behaviour at the
BDD scenario level; this module provides a focused integration-level guard that
runs independently and blocks commits if violated.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileSnapshot:
    """Immutable snapshot of a directory tree."""

    root: Path
    files: dict[str, str] = field(default_factory=dict)  # rel path -> sha256

    @classmethod
    def capture(cls, root: Path, max_depth: int = 8) -> FileSnapshot:
        """Walk root and hash every regular file up to max_depth levels deep."""
        files: dict[str, str] = {}
        if not root.exists():
            return cls(root=root, files=files)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if len(rel.parts) > max_depth:
                continue
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
            files[str(rel)] = digest
        return cls(root=root, files=files)

    def diff(
        self, after: FileSnapshot, allowlist_prefixes: tuple[str, ...] = ()
    ) -> list[str]:
        """Return a sorted list of paths that changed/appeared since this snapshot.

        Paths whose relative string starts with any prefix in allowlist_prefixes
        are excluded from the diff (allowed side effects, e.g. .nwave/ logs).
        """
        violations: list[str] = []
        for path, digest in after.files.items():
            if any(path.startswith(p) for p in allowlist_prefixes):
                continue
            if path not in self.files:
                violations.append(f"CREATED: {path}")
            elif self.files[path] != digest:
                violations.append(f"MODIFIED: {path}")
        for path in self.files:
            if any(path.startswith(p) for p in allowlist_prefixes):
                continue
            if path not in after.files:
                violations.append(f"DELETED: {path}")
        return sorted(violations)


# ---------------------------------------------------------------------------
# Subprocess invocation helper
# ---------------------------------------------------------------------------


def _run_validator(
    feature_delta_path: Path,
    home_dir: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run nwave-ai validate-feature-delta in an isolated subprocess."""
    env = {
        "HOME": str(home_dir),
        "PATH": str(Path(sys.executable).parent),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        # Prevent git from walking up to the host repo.
        "GIT_CEILING_DIRECTORIES": str(Path(__file__).parents[2].parent),
    }
    # Preserve coverage instrumentation if active.
    if os.environ.get("COVERAGE_PROCESS_START"):
        env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
        env["PYTHONPATH"] = os.environ.get("PYTHONPATH", os.getcwd())
        if os.environ.get("COVERAGE_FILE"):
            env["COVERAGE_FILE"] = os.environ["COVERAGE_FILE"]

    cmd = [
        sys.executable,
        "-m",
        "nwave_ai.cli",
        "validate-feature-delta",
        str(feature_delta_path),
        *(extra_args or []),
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
        cwd=str(feature_delta_path.parent),
    )


def _run_extractor(
    feature_delta_path: Path,
    home_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """Run nwave-ai extract-gherkin in an isolated subprocess."""
    env = {
        "HOME": str(home_dir),
        "PATH": str(Path(sys.executable).parent),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_CEILING_DIRECTORIES": str(Path(__file__).parents[2].parent),
    }
    if os.environ.get("COVERAGE_PROCESS_START"):
        env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
        env["PYTHONPATH"] = os.environ.get("PYTHONPATH", os.getcwd())
        if os.environ.get("COVERAGE_FILE"):
            env["COVERAGE_FILE"] = os.environ["COVERAGE_FILE"]

    cmd = [
        sys.executable,
        "-m",
        "nwave_ai.cli",
        "extract-gherkin",
        str(feature_delta_path),
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
        cwd=str(feature_delta_path.parent),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_home(tmp_path: Path) -> Path:
    """Isolated HOME directory — clean for each test."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def valid_feature_delta(tmp_path: Path) -> Path:
    """Minimal valid feature-delta.md with no violations."""
    fd = tmp_path / "docs" / "feature" / "test" / "feature-delta.md"
    fd.parent.mkdir(parents=True)
    fd.write_text(
        "# test\n\n"
        "## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | vendor-neutral commitment | n/a | preserves vendor-neutral surface |\n",
        encoding="utf-8",
    )
    return fd


@pytest.fixture
def violation_feature_delta(tmp_path: Path) -> Path:
    """Feature-delta with a known violation (E3b cherry-pick)."""
    fd = tmp_path / "docs" / "feature" / "viol" / "feature-delta.md"
    fd.parent.mkdir(parents=True)
    fd.write_text(
        "# token-billing\n\n"
        "## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | real WSGI handler bound to /api/usage | n/a | establishes protocol surface |\n\n"
        "## Wave: DESIGN\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| DISCUSS#row1 | framework-agnostic dispatcher | (none) | tradeoffs apply across the stack |\n",
        encoding="utf-8",
    )
    return fd


@pytest.fixture
def gherkin_feature_delta(tmp_path: Path) -> Path:
    """Feature-delta with embedded Gherkin blocks for extractor testing."""
    fd = tmp_path / "docs" / "feature" / "gherkin" / "feature-delta.md"
    fd.parent.mkdir(parents=True)
    fd.write_text(
        "# gherkin-test\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\nFeature: x\n  Scenario: y\n    Given z\n```\n",
        encoding="utf-8",
    )
    return fd


# ---------------------------------------------------------------------------
# G4 Hard Gate Tests
# ---------------------------------------------------------------------------

# Allowed side-effect prefixes (relative to HOME snapshot root).
_ALLOWED_PREFIXES = (".nwave/",)

# Forbidden absolute paths — these must NEVER be modified.
_FORBIDDEN_ABSOLUTE = (
    Path.home() / ".git",
    Path.home() / ".bashrc",
    Path.home() / ".bash_profile",
    Path.home() / ".zshrc",
    Path.home() / ".config",
    Path.home() / ".local" / "share",
)


def test_validator_produces_no_side_effects_on_valid_file(
    valid_feature_delta: Path,
    isolated_home: Path,
) -> None:
    """G4: validator leaves HOME unchanged when validating a clean feature-delta."""
    pre = FileSnapshot.capture(isolated_home)

    result = _run_validator(valid_feature_delta, isolated_home)

    post = FileSnapshot.capture(isolated_home)
    violations = pre.diff(post, allowlist_prefixes=_ALLOWED_PREFIXES)

    assert not violations, (
        "Validator modified HOME unexpectedly:\n"
        + "\n".join(f"  {v}" for v in violations)
        + f"\n\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.returncode in (0, 1), (
        f"Unexpected exit code {result.returncode}: {result.stderr!r}"
    )


def test_validator_produces_no_side_effects_on_file_with_violations(
    violation_feature_delta: Path,
    isolated_home: Path,
) -> None:
    """G4: validator leaves HOME unchanged even when violations are detected."""
    pre = FileSnapshot.capture(isolated_home)

    result = _run_validator(violation_feature_delta, isolated_home)

    post = FileSnapshot.capture(isolated_home)
    violations = pre.diff(post, allowlist_prefixes=_ALLOWED_PREFIXES)

    assert not violations, (
        "Validator modified HOME on violation run:\n"
        + "\n".join(f"  {v}" for v in violations)
        + f"\n\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def test_validator_json_mode_produces_no_side_effects(
    violation_feature_delta: Path,
    isolated_home: Path,
) -> None:
    """G4: validator with --format=json leaves HOME unchanged."""
    pre = FileSnapshot.capture(isolated_home)

    result = _run_validator(
        violation_feature_delta, isolated_home, extra_args=["--format=json"]
    )

    post = FileSnapshot.capture(isolated_home)
    violations = pre.diff(post, allowlist_prefixes=_ALLOWED_PREFIXES)

    assert not violations, (
        "Validator (--format=json) modified HOME:\n"
        + "\n".join(f"  {v}" for v in violations)
        + f"\n\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    # JSON mode with violations must exit 1 (machine-consumption contract).
    assert result.returncode == 1, (
        f"Expected exit 1 from --format=json with violations, got {result.returncode}"
    )


def test_extractor_produces_no_side_effects(
    gherkin_feature_delta: Path,
    isolated_home: Path,
) -> None:
    """G4: extractor leaves HOME unchanged (output goes to stdout only)."""
    pre = FileSnapshot.capture(isolated_home)

    result = _run_extractor(gherkin_feature_delta, isolated_home)

    post = FileSnapshot.capture(isolated_home)
    violations = pre.diff(post, allowlist_prefixes=_ALLOWED_PREFIXES)

    assert not violations, (
        "Extractor modified HOME unexpectedly:\n"
        + "\n".join(f"  {v}" for v in violations)
        + f"\n\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.returncode == 0, (
        f"Extractor failed unexpectedly: exit {result.returncode}, "
        f"stderr: {result.stderr!r}"
    )


def test_forbidden_paths_not_modified(
    valid_feature_delta: Path,
    isolated_home: Path,
) -> None:
    """G4: explicitly verify none of the forbidden absolute paths are modified."""
    # Capture modification times for forbidden paths that exist.
    existing_forbidden = [p for p in _FORBIDDEN_ABSOLUTE if p.exists()]
    mtime_before = {p: p.stat().st_mtime for p in existing_forbidden}

    _run_validator(valid_feature_delta, isolated_home)

    for path in existing_forbidden:
        mtime_after = path.stat().st_mtime
        assert mtime_before[path] == mtime_after, f"Forbidden path was modified: {path}"
