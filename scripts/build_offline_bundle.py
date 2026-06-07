#!/usr/bin/env python3
"""Build a self-contained offline install bundle for air-gapped environments.

Produces: dist/releases/nwave-offline-bundle-{version}.tar.gz
          dist/releases/nwave-offline-bundle-{version}.tar.gz.sha256

Bundle contents:
  dist/          — nWave assets (via build_dist.DistBuilder)
  wheels/        — nwave-ai wheel + all Python deps (via pip download)
  install-offline.sh  — one-line install script (pip --no-index + nwave-ai install)

Usage:
    python scripts/build_offline_bundle.py
    python scripts/build_offline_bundle.py --output-dir /tmp/my-bundle
    python scripts/build_offline_bundle.py --python /path/to/python

Platform note: --python selects which interpreter *invokes* pip download.
It does NOT change the target platform. Wheels fetched by pip download are
always built for the builder machine's OS and CPU architecture. To target a
different platform, build on a machine whose OS/architecture/Python minor
version match the target.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


# Ensure project root is on sys.path so build_dist imports work.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.build_dist import DistBuilder, _get_version  # noqa: E402


_INSTALL_SCRIPT_CONTENT = """\
#!/bin/sh
# Bootstrap script for nWave offline installation.
#
# NOTE: This is an intentional exception to the nWave zero-shell-scripts policy.
# Offline installers must be executable on the target machine without Python
# available on PATH. A Python entry point cannot bootstrap itself. This script
# is the traditional installer bootstrap pattern; it is kept minimal and
# read-only (no network calls, no privilege escalation).
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
pip install --no-index --find-links "$SCRIPT_DIR/wheels" nwave-ai
nwave-ai install
nwave-ai doctor
"""


def _write_install_script(staging_dir: Path) -> Path:
    """Write install-offline.sh into staging_dir and make it executable."""
    script_path = staging_dir / "install-offline.sh"
    script_path.write_text(_INSTALL_SCRIPT_CONTENT, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def _validate_python(python: str) -> str:
    """Validate that python names a usable executable.

    Args:
        python: path or name of the Python interpreter to use.

    Returns:
        Resolved executable path (same value if already absolute and valid).

    Raises:
        SystemExit: with a clear message if the executable cannot be found.
    """
    resolved = shutil.which(python)
    if resolved is None:
        # shutil.which returns None when the name is not on PATH and not an
        # accessible file. Provide a human-readable error before subprocess
        # swallows the problem.
        print(
            f"[ERROR] Python interpreter not found or not executable: {python!r}\n"
            "       Pass an absolute path or a name resolvable on PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    return resolved


def _download_wheels(staging_dir: Path, python: str) -> Path:
    """Run pip download to fetch nwave-ai and its dependencies.

    Args:
        staging_dir: parent staging directory; wheels/ will be created inside.
        python: path to the Python executable to use for pip.
            NOTE: this controls which interpreter *runs* pip download, not
            which platform the downloaded wheels target. Wheels always match
            the builder machine's OS and ABI.

    Returns:
        Path to the wheels/ directory.
    """
    wheels_dir = staging_dir / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        python,
        "-m",
        "pip",
        "download",
        "--dest",
        str(wheels_dir),
        "nwave-ai",
    ]
    subprocess.run(cmd, check=True)
    return wheels_dir


def _create_tarball(staging_dir: Path, bundle_path: Path) -> Path:
    """Pack staging_dir contents into bundle_path (.tar.gz) atomically.

    Writes to a .tmp sibling first, then renames to the final path so that
    a partial write (e.g., disk full) never leaves a misleading artifact at
    the target location.
    """
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = bundle_path.with_suffix(".tmp")

    try:
        with tarfile.open(tmp_path, "w:gz") as tf:
            for item in sorted(staging_dir.rglob("*")):
                arcname = item.relative_to(staging_dir)
                tf.add(item, arcname=str(arcname))
        tmp_path.rename(bundle_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return bundle_path


def _write_sha256(bundle_path: Path) -> Path:
    """Compute SHA-256 of bundle_path and write a sha256sum-compatible file.

    The companion file follows the standard sha256sum(1) format::

        <64-hex-chars>  <filename>

    so that users can verify with ``sha256sum -c <companion>``.

    Args:
        bundle_path: path to the produced tarball.

    Returns:
        Path to the .sha256 companion file.
    """
    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    sha256_path = Path(str(bundle_path) + ".sha256")
    # Two spaces between digest and filename matches sha256sum(1) text-mode output.
    sha256_path.write_text(
        f"{digest}  {bundle_path.name}\n",
        encoding="utf-8",
    )
    return sha256_path


def build_offline_bundle(
    project_root: Path | None = None,
    output_dir: Path | None = None,
    python: str | None = None,
) -> Path:
    """Orchestrate the offline bundle build.

    Args:
        project_root: nWave-dev project root (auto-detected if None).
        output_dir: directory where the tarball is written. Defaults to
            dist/releases/ inside project_root.
        python: Python executable for pip download (defaults to sys.executable).
            NOTE: this controls which interpreter *runs* pip download, not
            which platform the downloaded wheels target. See module docstring.

    Returns:
        Path to the produced .tar.gz tarball (a .sha256 companion is also
        written to the same directory).
    """
    project_root = project_root or _project_root
    python_exe = _validate_python(python or sys.executable)

    version = _get_version(project_root)

    with tempfile.TemporaryDirectory(prefix="nwave-offline-bundle-") as _tmp:
        staging = Path(_tmp)

        # 1. Build dist/ assets into staging/dist/
        dist_staging = staging / "dist"
        # NOTE: DistBuilder.dist_dir is set as a direct attribute because
        # DistBuilder does not currently accept dist_dir via its constructor.
        # If DistBuilder adds constructor-level validation in the future,
        # prefer passing it there. Until then, keep this coupling minimal and
        # documented here.
        builder = DistBuilder(project_root=project_root)
        builder.dist_dir = dist_staging
        builder.run()

        # 2. Download wheels into staging/wheels/
        _download_wheels(staging, python=python_exe)

        # 3. Write install-offline.sh at staging root
        _write_install_script(staging)

        # 4. Create tarball (atomic via .tmp rename)
        if output_dir is None:
            output_dir = project_root / "dist" / "releases"

        bundle_name = f"nwave-offline-bundle-{version}.tar.gz"
        bundle_path = Path(output_dir) / bundle_name
        _create_tarball(staging, bundle_path)

    # 5. Write SHA-256 companion (after context manager so tarball is final)
    _write_sha256(bundle_path)

    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a self-contained offline install bundle."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to write the tarball (default: dist/releases/)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root (default: auto-detect from script location)",
    )
    parser.add_argument(
        "--python",
        help=(
            "Python interpreter to invoke pip download. "
            "Does NOT change target platform; wheels follow the builder's "
            "platform ABI. Default: current interpreter."
        ),
    )
    args = parser.parse_args()

    bundle = build_offline_bundle(
        project_root=args.project_root,
        output_dir=args.output_dir,
        python=args.python,
    )
    sha256_path = Path(str(bundle) + ".sha256")
    digest_line = sha256_path.read_text(encoding="utf-8").split()[0]
    print(f"[INFO] Bundle created: {bundle}")
    print(f"[INFO] SHA256: {digest_line}")
    print(f"[INFO] Companion: {sha256_path}")


if __name__ == "__main__":
    main()
