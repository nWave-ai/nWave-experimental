#!/usr/bin/env python3
"""Build dist/ from nWave source directories.

Assembles a distributable layout from scattered source directories:
  nWave/agents/       → dist/agents/nw/
  nWave/templates/    → dist/templates/
  nWave/skills/nw-*/  → dist/skills/nw-*/    (flat layout, includes command-skills)
  nWave/scripts/des/  → dist/scripts/des/
  src/des/            → dist/lib/python/des/  (imports rewritten: src.des → des)
  scripts/*.py        → dist/scripts/

Note: Commands are now installed as skills (nw-{name}/SKILL.md) since v2.8.0.
The legacy commands/nw/ directory is no longer built.

Usage:
    python scripts/build_dist.py
    python scripts/build_dist.py --project-root /path/to/project
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


# Ensure project root is in sys.path when invoked as standalone script
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.shared.agent_catalog import (  # noqa: E402
    build_ownership_map,
    detect_command_skills,
    is_public_agent,
    load_public_agents,
)
from scripts.shared.skill_distribution import (  # noqa: E402
    copy_skills_to_target,
    enumerate_skills,
    filter_public_skills,
)


# Static directories that must exist after build.
# Skills use dynamic validation (nw-* directories under skills/).
REQUIRED_DIRS = [
    "agents/nw",
    "templates",
    "skills",
    "scripts/des",
    "lib/python/des",
]

# DES import rewriting patterns (from des_plugin.py)
_FROM_PATTERN = re.compile(r"\bfrom\s+src\.des\b")
_IMPORT_PATTERN = re.compile(r"\bimport\s+src\.des\b")
_GENERAL_PATTERN = re.compile(r"\bsrc\.des\.")

# Utility scripts to include in dist/scripts/
# Entries may include subdirectory prefixes (e.g. "hooks/foo.py") — the file is
# copied from scripts/<entry> into dist/scripts/<basename>.
UTILITY_SCRIPTS = [
    "install_nwave_target_hooks.py",
    "validate_step_file.py",
]


def _get_version(project_root: Path) -> str:
    """Read version from pyproject.toml (single source of truth)."""
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return "0.0.0"
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")
    except ModuleNotFoundError:
        content = pyproject_path.read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return m.group(1) if m else "0.0.0"


class DistBuilder:
    """Assembles dist/ from source directories."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.dist_dir = self.project_root / "dist"
        self.nwave_dir = self.project_root / "nWave"
        self.version = _get_version(self.project_root)
        self.public_agents: set[str] = set()  # loaded in run() after source validation

    def _log(self, message: str, level: str = "INFO"):
        print(f"[{level}] {message}")

    def clean(self) -> None:
        """Remove dist/ (preserving dist/releases/ for CI artifacts)."""
        if not self.dist_dir.exists():
            return

        # Preserve releases/ if it exists
        releases_dir = self.dist_dir / "releases"
        releases_backup = None
        if releases_dir.exists():
            releases_backup = self.dist_dir.parent / ".dist_releases_backup"
            if releases_backup.exists():
                shutil.rmtree(releases_backup)
            shutil.move(str(releases_dir), str(releases_backup))

        # Remove everything in dist/
        shutil.rmtree(self.dist_dir)

        # Restore releases/
        if releases_backup and releases_backup.exists():
            self.dist_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(releases_backup), str(releases_dir))

        self._log("Cleaned dist/")

    def build_agents(self) -> int:
        """nWave/agents/nw-*.md → dist/agents/nw/ (public agents only)."""
        src = self.nwave_dir / "agents"
        dst = self.dist_dir / "agents" / "nw"
        dst.mkdir(parents=True, exist_ok=True)

        count = 0
        skipped = 0
        for md_file in src.glob("nw-*.md"):
            if is_public_agent(md_file.name, self.public_agents):
                shutil.copy2(md_file, dst / md_file.name)
                count += 1
            else:
                skipped += 1

        msg = f"Agents: {count} files"
        if skipped:
            msg += f" ({skipped} private, excluded)"
        self._log(msg)
        return count

    def build_templates(self) -> int:
        """nWave/templates/ → dist/templates/"""
        src = self.nwave_dir / "templates"
        dst = self.dist_dir / "templates"
        dst.mkdir(parents=True, exist_ok=True)

        count = 0
        for item in src.iterdir():
            if item.is_file():
                shutil.copy2(item, dst / item.name)
                count += 1

        self._log(f"Templates: {count} files")
        return count

    def build_skills(self) -> int:
        """nWave/skills/nw-*/ → dist/skills/nw-*/ (flat, public + commands)."""
        src = self.nwave_dir / "skills"
        dst = self.dist_dir / "skills"
        dst.mkdir(parents=True, exist_ok=True)

        # Build ownership map for flat namespace filtering (ADR-003)
        agents_dir = self.nwave_dir / "agents"
        ownership_map = build_ownership_map(agents_dir) if agents_dir.exists() else {}
        command_skills = detect_command_skills(src)

        entries = enumerate_skills(src)
        public_entries = filter_public_skills(
            entries, self.public_agents, ownership_map, command_skills
        )
        count = copy_skills_to_target(public_entries, dst)

        skipped = len(entries) - len(public_entries)
        msg = f"Skills: {count} directories ({len(command_skills)} commands)"
        if skipped:
            msg += f" ({skipped} private, excluded)"
        self._log(msg)
        return count

    def build_des_scripts(self) -> int:
        """nWave/scripts/des/ → dist/scripts/des/"""
        src = self.nwave_dir / "scripts" / "des"
        if not src.exists():
            self._log("DES scripts: source not found, skipping", "WARN")
            return 0

        dst = self.dist_dir / "scripts" / "des"
        dst.mkdir(parents=True, exist_ok=True)

        count = 0
        for item in src.iterdir():
            if item.is_file():
                shutil.copy2(item, dst / item.name)
                count += 1

        self._log(f"DES scripts: {count} files")
        return count

    def build_des_module(self) -> int:
        """src/des/ → dist/lib/python/des/ (rewrite imports, clear __pycache__)."""
        src = self.project_root / "src" / "des"
        if not src.exists():
            self._log("DES module: src/des/ not found, skipping", "WARN")
            return 0

        dst = self.dist_dir / "lib" / "python" / "des"
        shutil.copytree(src, dst, dirs_exist_ok=True)

        # Rewrite imports: src.des → des
        files_modified = 0
        for py_file in dst.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            original = content
            content = _FROM_PATTERN.sub("from des", content)
            content = _IMPORT_PATTERN.sub("import des", content)
            content = _GENERAL_PATTERN.sub("des.", content)
            if content != original:
                py_file.write_text(content, encoding="utf-8")
                files_modified += 1

        # Clear __pycache__
        for cache_dir in dst.rglob("__pycache__"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)

        self._log(f"DES module: rewrote imports in {files_modified} files")
        return files_modified

    def build_utilities(self) -> int:
        """scripts/*.py → dist/scripts/ (selected utility scripts only).

        Entries in UTILITY_SCRIPTS may include a subdirectory prefix
        (e.g. "hooks/check_probe_method.py") — the file is copied flat
        into dist/scripts/<basename>.
        """
        src = self.project_root / "scripts"
        dst = self.dist_dir / "scripts"
        dst.mkdir(parents=True, exist_ok=True)

        count = 0
        for script_name in UTILITY_SCRIPTS:
            script_file = src / script_name
            dest_name = Path(script_name).name  # flatten subdirectory
            if script_file.exists():
                shutil.copy2(script_file, dst / dest_name)
                count += 1

        self._log(f"Utility scripts: {count} files")
        return count

    def write_manifest(self, counts: dict) -> None:
        """Write dist/MANIFEST.json with version and file counts."""
        manifest = {
            "version": self.version,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "contents": {
                "agents": len(list((self.dist_dir / "agents" / "nw").glob("nw-*.md"))),
                "templates": len(list((self.dist_dir / "templates").iterdir())),
                "skills": counts.get("skills", 0),
                "des_module": counts.get("des_module", 0),
            },
        }

        manifest_path = self.dist_dir / "MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._log(f"Manifest: {manifest_path}")

    def validate(self) -> bool:
        """Validate all required artifacts are present."""
        missing = []
        for dir_path in REQUIRED_DIRS:
            if not (self.dist_dir / dir_path).is_dir():
                missing.append(dir_path)

        # Dynamic validation: at least one nw-* skill directory must exist
        skills_dir = self.dist_dir / "skills"
        if skills_dir.is_dir():
            nw_skill_dirs = [
                d
                for d in skills_dir.iterdir()
                if d.is_dir() and d.name.startswith("nw-")
            ]
            if not nw_skill_dirs:
                missing.append("skills/nw-* (no skill directories found)")
        else:
            missing.append("skills")

        if not (self.dist_dir / "MANIFEST.json").exists():
            missing.append("MANIFEST.json")

        if missing:
            self._log(f"Validation failed — missing: {missing}", "ERROR")
            return False

        self._log("Validation passed")
        return True

    def run(self) -> bool:
        """Orchestrate: clean → build_* → manifest → validate."""
        self._log(f"Building dist/ for version {self.version}")
        self._log(f"Source: {self.nwave_dir}")
        self._log(f"Output: {self.dist_dir}")

        # Validate source exists
        if not self.nwave_dir.exists():
            self._log(f"nWave/ not found at {self.nwave_dir}", "ERROR")
            return False

        # Load public agents (after source validation)
        self.public_agents = load_public_agents(self.nwave_dir)

        # Always clean first
        self.clean()

        # Build all components
        self.dist_dir.mkdir(parents=True, exist_ok=True)

        counts = {}
        counts["agents"] = self.build_agents()
        counts["templates"] = self.build_templates()
        counts["skills"] = self.build_skills()
        self.build_des_scripts()
        counts["des_module"] = self.build_des_module()
        self.build_utilities()

        # Write manifest
        self.write_manifest(counts)

        # Validate
        if not self.validate():
            return False

        self._log("Build complete")
        return True


def main():
    parser = argparse.ArgumentParser(description="Build dist/ from nWave source")
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root directory (default: auto-detect)",
    )
    args = parser.parse_args()

    builder = DistBuilder(project_root=args.project_root)
    success = builder.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
