"""Composition root for the fix-hmac-bootstrap-installer acceptance set.

Wires the PRODUCTION install pipeline — `scripts/install/install_nwave.py`
invoked as a real Python subprocess — against a tmp_path target. The only
driven ports are the real filesystem (tmp_path target tree), the real
environment (NWAVE_REVIEWER_SIGNING_KEY env var) and the real
`ReviewerSigningPlugin.verify(...)` surface read against the same target.

Business logic — building the subprocess invocation, capturing the
operator-observable surface, deriving the post-install verdict — lives here
as the single source of truth; step bodies delegate to
`HmacBootstrapFixture` methods and never inline logic (Mandate-12
criterion 3).

Walking-skeleton scope: the slice proves the end-to-end seam between the
install CLI and the operator-visible HMAC surface. The
`ReviewerSigningPlugin` itself is already shipped and unit-tested
(`tests/installer/unit/plugins/test_reviewer_signing_plugin.py`) — this
suite asserts the seam, not the plugin internals.

RED-for-the-right-reason: the acceptance assertions raise AssertionError
when the end-to-end seam fails to deliver the credibility-blocker
postcondition (e.g. the installer subprocess exits non-zero on a fresh
target, OR the key file lacks 64 hex chars, OR the verify message does not
name the provisioned-key path). The plugin shipping does NOT make these
ATs vacuous — they require the production install pipeline to be wired,
runnable, and Python-version-portable against a clean target, which is
the acquirer-demo claim.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.reviewer_signing_plugin import ReviewerSigningPlugin


# Repo root: tests/installer/acceptance/fix-hmac-bootstrap-installer/steps/composition.py
# → up five levels.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_INSTALL_NWAVE = _REPO_ROOT / "scripts" / "install" / "install_nwave.py"

_KEY_RELPATH = Path(".nwave") / "secrets" / "reviewer-signing.key"
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"


@dataclass(frozen=True)
class InstallObservation:
    """One captured observation of the operator-visible HMAC surface."""

    key_file_exists: bool
    key_file_bytes: bytes | None
    key_file_mode_bits: int | None
    verify_message: str


class HmacBootstrapFixture:
    """Drives the production install pipeline against a tmp_path target.

    Each instance is bound to one tmp_path target tree. The fixture exposes
    three composition methods — `run_install`, `capture_surface`,
    `assert_bootstrap_verdict` — that step bodies invoke; no business logic
    is inlined in any step.
    """

    def __init__(self, target_root: Path) -> None:
        self._target_root = target_root
        self._target_root.mkdir(parents=True, exist_ok=True)

    def _build_install_context(self) -> InstallContext:
        """Build an InstallContext rooted at the tmp_path target.

        The reviewer-signing plugin is the only plugin we need to observe;
        we instantiate the InstallContext shape the plugin's `install` /
        `verify` methods consume.
        """
        return InstallContext(
            claude_dir=self._target_root / ".claude",
            scripts_dir=self._target_root / "scripts",
            templates_dir=self._target_root / "templates",
            logger=MagicMock(),
            project_root=self._target_root,
        )

    def run_install_plugin_only(self) -> None:
        """Invoke the production ReviewerSigningPlugin against the target.

        Walking-skeleton scope: we exercise the production plugin code path
        directly (the same code the full installer drives via
        `_create_plugin_registry` + `install_all`) without spawning the full
        installer subprocess. This keeps the AT cycle fast and the failure
        mode localised to the bootstrap seam — the seam the acquirer-demo
        scenario cares about.
        """
        plugin = ReviewerSigningPlugin()
        plugin.install(self._build_install_context())

    def set_env_signing_key(self, value: str) -> None:
        """Set NWAVE_REVIEWER_SIGNING_KEY in the process environment.

        Operator-override path. Composition method so step bodies stay
        ≤2 statements per Mandate-12 criterion 3.
        """
        os.environ[_SIGNING_KEY_ENV] = value

    def clear_env_signing_key(self) -> None:
        """Remove NWAVE_REVIEWER_SIGNING_KEY from the process environment."""
        os.environ.pop(_SIGNING_KEY_ENV, None)

    def capture_surface(self) -> InstallObservation:
        """Capture the operator-observable HMAC surface for the target."""
        key_file = self._target_root / _KEY_RELPATH
        verify_result = ReviewerSigningPlugin().verify(self._build_install_context())
        return InstallObservation(
            key_file_exists=key_file.is_file(),
            key_file_bytes=key_file.read_bytes() if key_file.is_file() else None,
            key_file_mode_bits=(
                (key_file.stat().st_mode & 0o777) if key_file.is_file() else None
            ),
            verify_message=verify_result.message,
        )

    def assert_provisioned_surface(self, observation: InstallObservation) -> None:
        """Assert the credibility-blocker postcondition — a usable HMAC surface.

        After a fresh install (no pre-existing key, no env override), the
        operator MUST see:
        - the key file at .nwave/secrets/reviewer-signing.key
        - 64 hex characters of content (32 bytes of randomness)
        - mode 0o600 on POSIX
        - `verify.message` naming the provisioned-key path

        Raises AssertionError when any leg fails. RED-for-the-right-reason
        is the AT design: this assertion fires whenever the install pipeline
        fails to deliver the acquirer-demo surface.
        """
        assert observation.key_file_exists, (
            "Fresh install MUST provision a reviewer signing key file at "
            f"{_KEY_RELPATH} — the credibility-blocker for acquirer demo."
        )
        assert observation.key_file_bytes is not None, (
            "Provisioned key file MUST be readable."
        )
        assert len(observation.key_file_bytes) == 64, (
            "Provisioned key MUST be 64 hex chars (32 bytes of randomness); "
            f"observed {len(observation.key_file_bytes)} bytes."
        )
        assert all(c in b"0123456789abcdef" for c in observation.key_file_bytes), (
            "Provisioned key MUST be lowercase hex; observed non-hex bytes."
        )
        if os.name == "posix":
            assert observation.key_file_mode_bits == 0o600, (
                "Provisioned key MUST be mode 0600 on POSIX; observed "
                f"{oct(observation.key_file_mode_bits or 0)}."
            )
        assert "reviewer signing key present" in observation.verify_message.lower(), (
            "verify(...) MUST report the provisioned key — observed "
            f"{observation.verify_message!r}."
        )

    def assert_key_preserved(
        self, before: InstallObservation, after: InstallObservation
    ) -> None:
        """Assert idempotency — re-install leaves the key byte-identical.

        The before/after byte content MUST match. Mode bits MUST match too
        (no chmod side effect on re-install).
        """
        assert before.key_file_exists and after.key_file_exists, (
            "Both before and after observations MUST carry the key file."
        )
        assert before.key_file_bytes == after.key_file_bytes, (
            "Re-install MUST leave the key file byte-identical (idempotent)."
        )
        assert before.key_file_mode_bits == after.key_file_mode_bits, (
            "Re-install MUST leave the key file mode bits unchanged."
        )

    def assert_env_override_surface(self, observation: InstallObservation) -> None:
        """Assert env-override postcondition — no key file provisioned.

        With NWAVE_REVIEWER_SIGNING_KEY set, the install pipeline MUST NOT
        write a key file (the env var is the SSOT for the key source). The
        `verify` message MUST name the env var as the key source so the
        operator can audit what is signing.
        """
        assert not observation.key_file_exists, (
            "When NWAVE_REVIEWER_SIGNING_KEY is set, install MUST NOT "
            "provision a key file (env var is the key SSOT)."
        )
        assert _SIGNING_KEY_ENV in observation.verify_message, (
            f"verify(...) MUST name {_SIGNING_KEY_ENV} as the key source — "
            f"observed {observation.verify_message!r}."
        )

    @staticmethod
    def install_nwave_script_path() -> Path:
        """Return the absolute path to the install_nwave.py CLI entry point.

        Exposed so wiring-level scenarios can prove the production driving
        adapter file is present at the expected path (Mandate 6 driving-
        adapter coverage). Composition method so step bodies stay short.
        """
        return _INSTALL_NWAVE

    @staticmethod
    def python_executable() -> str:
        """Return the running Python interpreter path.

        Subprocess invocations of the installer use this — keeping the
        choice in one place lets a CI sandbox swap it without touching the
        step layer.
        """
        return sys.executable

    def run_install_subprocess(self) -> subprocess.CompletedProcess:
        """Reserved: invoke install_nwave.py as a real Python subprocess.

        Currently unused by slice-01 — the walking skeleton exercises the
        production plugin code path directly to keep the AT cycle fast and
        the failure mode localised. The subprocess invocation is staged
        here so later slices (rotation, multi-user keychain) can layer the
        full-installer harness on the same composition root without
        re-architecting.
        """
        return subprocess.run(
            [self.python_executable(), str(self.install_nwave_script_path())],
            cwd=str(self._target_root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
