"""Smoke test for scripts/build_offline_bundle.py.

Verifies tarball layout: install-offline.sh, dist/, and wheels/ directories
present in the produced archive. The pip download subprocess is mocked to
avoid network access in CI.
"""

import hashlib
import re
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "build_offline_bundle.py"


@pytest.fixture()
def fake_pip_download(monkeypatch):
    """Stub subprocess.run so pip download never touches the network.

    Creates a minimal wheel file in the dest dir so the script can proceed
    to tarball construction. Import happens lazily so RED phase shows
    ModuleNotFoundError clearly.
    """

    def _fake_run(cmd, **kwargs):
        # Detect the pip download call and plant a stub wheel in --dest
        if "pip" in cmd and "download" in cmd:
            dest = None
            for i, arg in enumerate(cmd):
                if arg == "--dest" and i + 1 < len(cmd):
                    dest = Path(cmd[i + 1])
                    break
            if dest is not None:
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "nwave_ai-0.0.0-py3-none-any.whl").write_bytes(b"stub")
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr(subprocess, "run", _fake_run)


def test_offline_bundle_tarball_layout(tmp_path, fake_pip_download):
    """
    Given: build_offline_bundle is invoked with --output-dir pointing to tmp_path
    When: the script runs end-to-end (pip download mocked)
    Then: a tarball exists containing install-offline.sh, dist/, and wheels/ entries
    """
    import scripts.build_offline_bundle as mod

    bundle_path = mod.build_offline_bundle(output_dir=tmp_path)

    assert bundle_path is not None, "build_offline_bundle must return the tarball path"
    assert bundle_path.exists(), f"Tarball not found at {bundle_path}"
    assert bundle_path.suffix == ".gz", "Tarball must be .tar.gz"

    with tarfile.open(bundle_path, "r:gz") as tf:
        names = tf.getnames()

    has_install_script = any(
        n == "install-offline.sh" or n.endswith("/install-offline.sh") for n in names
    )
    has_dist_dir = any(n == "dist" or n.startswith("dist/") for n in names)
    has_wheels_dir = any(n == "wheels" or n.startswith("wheels/") for n in names)

    assert has_install_script, (
        f"install-offline.sh missing from tarball. Contents: {names}"
    )
    assert has_dist_dir, f"dist/ directory missing from tarball. Contents: {names}"
    assert has_wheels_dir, f"wheels/ directory missing from tarball. Contents: {names}"


class TestSha256CompanionFile:
    """
    Given: build_offline_bundle is invoked
    When: the script completes
    Then: a .sha256 companion file is produced alongside the tarball
          containing a valid sha256sum-compatible line
    """

    def test_sha256_companion_file_exists(self, tmp_path, fake_pip_download):
        """SHA256 companion file is written next to the tarball."""
        import scripts.build_offline_bundle as mod

        bundle_path = mod.build_offline_bundle(output_dir=tmp_path)
        sha256_path = Path(str(bundle_path) + ".sha256")

        assert sha256_path.exists(), (
            f".sha256 companion file not found at {sha256_path}"
        )

    def test_sha256_companion_file_contains_valid_checksum(
        self, tmp_path, fake_pip_download
    ):
        """SHA256 companion file contains a 64-hex-char digest matching the tarball."""
        import scripts.build_offline_bundle as mod

        bundle_path = mod.build_offline_bundle(output_dir=tmp_path)
        sha256_path = Path(str(bundle_path) + ".sha256")

        content = sha256_path.read_text(encoding="utf-8").strip()

        # sha256sum format: "<64-hex-chars>  <filename>" (two spaces)
        pattern = r"^([0-9a-f]{64})  .+$"
        match = re.match(pattern, content)
        assert match, (
            f"SHA256 file content does not match sha256sum format. Got: {content!r}"
        )

        digest_in_file = match.group(1)
        actual_digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        assert digest_in_file == actual_digest, (
            f"SHA256 mismatch: file says {digest_in_file!r}, "
            f"actual tarball digest is {actual_digest!r}"
        )
