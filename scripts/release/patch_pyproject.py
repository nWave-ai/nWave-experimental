"""Patch pyproject.toml for public nWave repo distribution.

Renames package, sets version, removes dev-only sections,
rewrites build targets.

CLI:
    python patch_pyproject.py --input PATH --output PATH \\
        --target-name NAME --target-version VERSION [--dry-run]

Exit codes:
    0 = success
    1 = input file not found / parse error / missing field
    2 = (reserved)
    3 = no changes needed
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli


# Ensure project root is importable for the privacy-strip dependency when this
# script is invoked standalone from a wheel-build sandbox.
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# UTILITY_SCRIPTS (scripts/build_dist.py) is the single source of truth for
# which top-level scripts must ship to users; the wheel force-include map is
# derived from it below so the two lists cannot drift apart again (see
# tests/release/test_wheel_utility_scripts_invariant.py).
from scripts.build_dist import UTILITY_SCRIPTS  # noqa: E402

# DESPlugin.DES_HOOKS is the single source of truth for which
# `scripts/hooks/*.py` files the installed `des` package (Claude Code and
# host-neutral targets alike) propagates to `~/.claude/scripts/` or
# `~/.nwave/nWave/hooks/`; the wheel force-include map is derived from it
# below so a wheel build cannot silently omit one of them (RCA:
# fix-cross-host-sessionstart-packaging-path -- only
# `orchestrator_affordance_refresh.py` was ever hand-listed here, so the
# wheel shipped 1/8 DES_HOOKS scripts; once the install-time source-dir
# resolution was fixed to actually find the nested wheel directory,
# `validate_prerequisites` started (correctly) failing the install outright
# on the other 7 missing scripts). `scripts/hooks/` also carries this repo's
# OWN dev-only pre-commit tooling (autofix_python.py, check_*.py, ...) that
# must NOT ship to users, so the whole directory is never force-included --
# only the explicit DES_HOOKS allow-list, mirroring UTILITY_SCRIPTS above.
from scripts.install.plugins.des_plugin import DESPlugin  # noqa: E402


def _utility_scripts_force_include_block() -> str:
    """Force-include line per ``UTILITY_SCRIPTS`` entry (single source of truth).

    Several ``des`` subcommands SPAWN these scripts as their actuator, so a
    wheel that ships the command without the script offers a drain that
    cannot run on any installed machine -- the failure surfaces only at drain
    time, far from here. Deriving these lines from ``UTILITY_SCRIPTS``
    instead of hand-listing them keeps the dev-tarball and wheel whitelists
    from drifting apart again;
    ``tests/release/test_wheel_utility_scripts_invariant`` guards this as a
    second, redundant check, not the only one.
    """
    return "".join(f'"scripts/{name}" = "scripts/{name}"\n' for name in UTILITY_SCRIPTS)


def _hook_scripts_force_include_block() -> str:
    """Force-include line per ``DESPlugin.DES_HOOKS`` entry (single source of truth).

    Ships each hook script NESTED under ``nWave/nWave/hooks/`` -- the same
    physical shape ``_resolve_hook_scripts_source_dir`` (des_plugin.py)
    probes FIRST on a pipx/PyPI install, since ``framework_source`` already
    resolves to ``site-packages/nWave/`` there.
    """
    return "".join(
        f'"scripts/hooks/{name}" = "nWave/nWave/hooks/{name}"\n'
        for name in DESPlugin.DES_HOOKS
    )


class PatchError(Exception):
    """Raised when patching fails (file not found, parse error, missing field)."""


# Dev-only TOML sections to strip from public distribution.
_DEV_SECTIONS = frozenset({"[tool.nwave]", "[tool.semantic_release]"})
_TEMPLATE_BUILD_ALIAS = ".nwave-wheel-assets/templates"
_DATA_BUILD_ALIAS = ".nwave-wheel-assets/data"
_CATALOG_BUILD_ALIAS = ".nwave-wheel-assets/framework-catalog.yaml"


def _read_and_validate(input_path: str) -> tuple[str, dict]:
    """Read raw TOML text and parse it for validation.

    Returns (raw_text, parsed_dict).
    Raises PatchError on file-not-found, parse error, or missing fields.
    """
    if not os.path.isfile(input_path):
        msg = f"Input file not found: {input_path}"
        raise PatchError(msg)

    raw = Path(input_path).read_text(encoding="utf-8")

    try:
        parsed = tomli.loads(raw)
    except tomli.TOMLDecodeError as exc:
        msg = f"TOML parse error in {input_path}: {exc}"
        raise PatchError(msg) from exc

    project = parsed.get("project", {})
    if "name" not in project:
        msg = "pyproject.toml missing required field: [project] name"
        raise PatchError(msg)

    return raw, parsed


def _patch_name(text: str, old_name: str, new_name: str) -> tuple[str, str | None]:
    """Replace the project name value (exact match inside [project] name line)."""
    pattern = re.compile(
        r'^(name\s*=\s*")' + re.escape(old_name) + r'(")', re.MULTILINE
    )
    new_text, count = pattern.subn(rf"\g<1>{new_name}\2", text)
    if count == 0:
        return text, None
    return new_text, f"name: {old_name} -> {new_name}"


def _patch_version(
    text: str, old_version: str, new_version: str
) -> tuple[str, str | None]:
    """Replace the project version value."""
    pattern = re.compile(
        r'^(version\s*=\s*")' + re.escape(old_version) + r'(")',
        re.MULTILINE,
    )
    new_text, count = pattern.subn(rf"\g<1>{new_version}\2", text)
    if count == 0:
        return text, None
    return new_text, f"version: {old_version} -> {new_version}"


def _patch_wheel_packages(text: str, new_name: str) -> tuple[str, str | None]:
    """Rewrite [tool.hatch.build.targets.wheel] packages and add force-include."""
    pkg_name = new_name.replace("-", "_")

    # Remove existing wheel section (base) and force-include subsection if present
    force_include = re.compile(
        r"^\[tool\.hatch\.build\.targets\.wheel\.force-include\]\s*\n(?:(?!\[).+\n?)*",
        re.MULTILINE,
    )
    text_clean = force_include.sub("", text)

    wheel_section = re.compile(
        r"^\[tool\.hatch\.build\.targets\.wheel\]\s*\n(?:(?!\[).+\n?)*",
        re.MULTILINE,
    )
    # Selective includes: only directories needed in the public package.
    # Avoids broken symlinks, dev-only directories, and closed-source runtime.
    #
    # Privacy note (fix-installer-private-skill-leak slice-01, 2026-05-20):
    # The `nWave/agents` + `nWave/skills` force-include below reads the tree on
    # disk verbatim. `python -m build --wheel` copies it into the .whl as-is, so
    # the tree MUST be privacy-stripped BEFORE the build. `patch_pyproject()`
    # invokes `strip_private_agents.strip()` on the tree containing this
    # pyproject.toml (see `_strip_private_artifacts`) — that is the in-place
    # half of the two-part fix; the force-include pointing at the now-stripped
    # `nWave/agents`+`nWave/skills` is the other half. build_dist.py also
    # produces a filtered dist/, but the wheel force-include bypasses dist/ and
    # reads source — so the strip has to happen on the source tree itself.
    #
    # Historical note (fix-wheel-leaks-des-config-p0, 2026-04-23):
    # Previously this block force-included broad "scripts" = "scripts" and
    # "src/des" = "src/des", which shipped 136 files of dev-only tooling
    # (release/, hooks/, framework/, validation/) and 149 files of closed-source
    # DES runtime to the public 3.11.0 wheel.  The fix:
    #   - narrows scripts to scripts/install + scripts/shared (the only subtrees
    #     imported by nwave_ai/cli.py AND scripts/install/*.py at runtime,
    #     verified by grep);
    #   - replaces raw src/des with the pre-built lib/python/des tree (which
    #     scripts/build_dist.py produces with imports rewritten src.des -> des)
    #     and places it under nWave/ so installer lookup matches.
    # The CI pypi-publish job (release-prod.yml) must run `scripts/build_dist.py`
    # and stage `dist/lib` -> `./lib` before `python -m build --wheel` for the
    # nWave/lib/python/des force-include to resolve.
    #
    # One built runtime has two consumers, so build_dist produces two distinct
    # physical source roots (Hatch normalizes equivalent source keys):
    #   lib/python/des          -> site-packages/des/ (public `des` entry point)
    #   lib/nwave-runtime/des  -> site-packages/nWave/lib/python/des/
    #                               (installer-owned bundled runtime)
    # The installer's des_plugin.py:222 looks up
    # `context.framework_source / "lib/python/des"`.  When installed via pipx,
    # install_nwave.py sets framework_source = site-packages/nWave/, so files
    # must land at site-packages/nWave/lib/python/des/ — which only happens if
    # the force-include destination is prefixed with "nWave/".  The public
    # ``des = des.cli.__main__:main`` entry point also needs the prebuilt
    # package at site-packages/des/.  Hatch normalizes force-include source
    # paths, so these must be genuinely distinct staged source directories;
    # a trailing-slash spelling of one source is silently deduplicated.
    #
    # RUNTIME-ASSET note (fix-wheel-ships-nwave-runtime-assets, 2026-07-08):
    # `DESPlugin._install_nwave_runtime_assets` reads a DIFFERENT, deeper root
    # under a pipx install: when `using_prebuilt`, it resolves
    # `context.framework_source / "nWave" / <asset>` i.e.
    # site-packages/nWave/nWave/<asset> — one level below the flat entries
    # above, because `framework_source` already equals site-packages/nWave/.
    # So `flavors`/`data`/`schemas`/`framework-catalog.yaml` need a SECOND,
    # nested destination in addition to (or instead of) their flat one.
    # `templates` is consumed at BOTH the flat destination (TemplatesPlugin
    # reads `context.templates_dir` = framework_source/"templates") and the
    # nested one (the runtime-asset resolver). Hatch normalises source keys, so
    # syntactic aliases such as a trailing slash collide. The nested mapping
    # therefore reads a physically distinct, build-private staged copy.
    # `framework-catalog.yaml` is likewise shipped to both destinations; one
    # mapping therefore uses its own physically distinct staged copy too.
    utility_scripts_block = _utility_scripts_force_include_block()
    hook_scripts_block = _hook_scripts_force_include_block()
    replacement = (
        "[tool.hatch.build.targets.wheel]\n"
        f'packages = ["{pkg_name}"]\n'
        "\n"
        "[tool.hatch.build.targets.wheel.force-include]\n"
        '"nWave/agents" = "nWave/agents"\n'
        '"nWave/scripts" = "nWave/scripts"\n'
        '"nWave/skills" = "nWave/skills"\n'
        '"nWave/tasks/nw" = "nWave/tasks/nw"\n'
        '"nWave/templates" = "nWave/templates"\n'
        f'"{_TEMPLATE_BUILD_ALIAS}" = "nWave/nWave/templates"\n'
        '"nWave/flavors" = "nWave/nWave/flavors"\n'
        '"nWave/data" = "nWave/data"\n'
        f'"{_DATA_BUILD_ALIAS}" = "nWave/nWave/data"\n'
        '"nWave/schemas" = "nWave/nWave/schemas"\n'
        '"nWave/dispatch" = "nWave/nWave/dispatch"\n'
        '"nWave/waves" = "nWave/nWave/waves"\n'
        f'"{_CATALOG_BUILD_ALIAS}" = "nWave/nWave/framework-catalog.yaml"\n'
        '"nWave/framework-catalog.yaml" = "nWave/framework-catalog.yaml"\n'
        f"{hook_scripts_block}"
        '"nWave/VERSION" = "nWave/VERSION"\n'
        '"nWave/README.md" = "nWave/README.md"\n'
        '"scripts/install" = "scripts/install"\n'
        '"scripts/shared" = "scripts/shared"\n'
        f"{utility_scripts_block}"
        '"lib/python/des" = "des"\n'
        '"lib/nwave-runtime/des" = "nWave/lib/python/des"\n'
    )
    new_text, count = wheel_section.subn(replacement, text_clean)
    if count == 0:
        return text, None
    return (
        new_text,
        f'wheel config: rewritten with packages=["{pkg_name}"] + force-include',
    )


def _add_offline_handoff_hook(text: str) -> tuple[str, str | None]:
    """Register the public-wheel hook that writes its adjacent offline closure."""
    section = "[tool.hatch.build.hooks.custom]"
    hook = (
        "\n[tool.hatch.build.hooks.custom]\n"
        'path = "scripts/release/offline_wheelhouse_hook.py"\n'
    )
    if section in text:
        return text, None

    wheel_section = re.compile(
        r"(^\[tool\.hatch\.build\.targets\.wheel\.force-include\]\s*\n(?:(?!\[).+\n?)*)",
        re.MULTILINE,
    )
    new_text, count = wheel_section.subn(rf"\1{hook}", text, count=1)
    if count == 0:
        return text, None
    return new_text, "registered offline public-candidate handoff build hook"


def _add_offline_handoff_build_requirement(text: str) -> tuple[str, str | None]:
    """Ensure the isolated public-wheel backend can run ``pip download``."""
    pattern = re.compile(
        r"(^\[build-system\]\nrequires\s*=\s*\[)([^\]]*)(\])",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None or re.search(r'"pip(?:[<>=!~].*)?"', match.group(2)):
        return text, None

    existing = match.group(2).rstrip()
    separator = ", " if existing else ""
    replacement = f'{match.group(1)}{existing}{separator}"pip>=24"{match.group(3)}'
    return (
        text[: match.start()] + replacement + text[match.end() :],
        "added pip>=24 to the public wheel build backend requirements",
    )


def _add_cli_entry_point(text: str, new_name: str) -> tuple[str, str | None]:
    """Add [project.scripts] CLI entry point (merging into existing section if present).

    Behaviour per issue #41 RCA Branch A (skip->merge):
      - If [project.scripts] is absent, create the section after [project.urls]
        or before the first [tool.] section (preserves prior behaviour).
      - If [project.scripts] exists, MERGE the new entry into it (do not skip).
        Foreign entries are preserved alongside.
      - If the exact entry already exists, leave the file unchanged (idempotent).
    """
    pkg_name = new_name.replace("-", "_")
    entry_line = f'{new_name} = "{pkg_name}.cli:main"\n'

    if "[project.scripts]" in text:
        # Idempotency: bail out if the entry is already present.
        if entry_line.strip() in text:
            return text, None

        # Merge: insert the new entry on the line immediately after the
        # [project.scripts] header, preserving any foreign entries that follow.
        pattern = re.compile(r"(\[project\.scripts\]\n)")
        new_text, count = pattern.subn(rf"\1{entry_line}", text, count=1)
        if count == 0:
            return text, None
        return (
            new_text,
            f'merged [project.scripts] entry: {new_name} = "{pkg_name}.cli:main"',
        )

    scripts_block = f"\n[project.scripts]\n{entry_line}"

    # Insert after [project.urls] block (before next section)
    pattern = re.compile(r"(\[project\.urls\].*?\n)(\n\[)", re.DOTALL)
    new_text, count = pattern.subn(rf"\1{scripts_block}\2", text)
    if count == 0:
        # Fallback: append before first [tool.] section
        pattern2 = re.compile(r"(\n)(\[tool\.)")
        new_text, count = pattern2.subn(rf"\1{scripts_block}\2", text, count=1)
        if count == 0:
            return text, None
    return (
        new_text,
        f'added [project.scripts] entry point: {new_name} = "{pkg_name}.cli:main"',
    )


def _remove_section(text: str, header: str) -> tuple[str, str | None]:
    """Remove an entire TOML section (header + all lines until next section or EOF)."""
    # Match the section header and all lines up to (but not including) the next section header
    escaped = re.escape(header)
    pattern = re.compile(
        r"^" + escaped + r"\s*\n(?:(?!\[).+\n?)*",
        re.MULTILINE,
    )
    new_text, count = pattern.subn("", text)
    if count == 0:
        return text, None
    # Clean up any resulting double blank lines
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    return new_text, f"removed section: {header}"


def _strip_private_artifacts(input_path: str) -> str | None:
    """Privacy-strip the source tree the wheel force-include reads.

    The wheel ``force-include`` map points at ``nWave/agents`` +
    ``nWave/skills`` on disk. ``python -m build --wheel`` copies that tree
    verbatim, so any ``public: false`` agent or privately-owned skill present
    on disk leaks into the public ``.whl``. This strips the tree in place
    BEFORE the build runs.

    The strip preserves the ``PUBLIC_SHARED_SKILLS`` allow-list (load-bearing
    public skills with no owning public agent) — that logic lives in
    ``is_public_skill`` and is applied by ``strip()``.

    *input_path* is the pyproject.toml being patched; the tree root is its
    parent directory (the wheel-build sandbox). Returns a one-line change
    description, or ``None`` when there is no ``nWave/`` tree to strip.
    """
    tree_root = Path(input_path).resolve().parent
    if not (tree_root / "nWave" / "agents").is_dir():
        return None

    from scripts.release.strip_private_agents import strip

    removed = strip(tree_root)
    agents = len(removed["agents"])
    skills = len(removed["skills"])
    return (
        f"privacy strip: removed {agents} private agent(s) and "
        f"{skills} private skill dir(s) before wheel build"
    )


def _stage_directory_build_alias(
    input_path: str,
    source_relative: str,
    alias_relative: str,
    asset_name: str,
) -> str | None:
    """Mirror a public directory to a private source used by Hatch.

    Replacing the prior alias on every real patch keeps the staged tree an
    exact, idempotent copy even when files have been removed upstream.
    """
    tree_root = Path(input_path).resolve().parent
    source = tree_root / Path(source_relative)
    alias = tree_root / Path(alias_relative)
    if alias.is_symlink() or alias.is_file():
        alias.unlink()
    elif alias.is_dir():
        shutil.rmtree(alias)

    if not source.is_dir():
        return None

    alias.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, alias)
    return f"staged wheel {asset_name}: {source} -> {alias}"


def _stage_catalog_build_alias(input_path: str) -> str | None:
    """Copy the public catalog to the private source used by Hatch."""
    tree_root = Path(input_path).resolve().parent
    source = tree_root / "nWave" / "framework-catalog.yaml"
    alias = tree_root / Path(_CATALOG_BUILD_ALIAS)
    if alias.is_symlink() or alias.is_file():
        alias.unlink()
    elif alias.is_dir():
        shutil.rmtree(alias)

    if not source.is_file():
        return None

    alias.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, alias)
    return f"staged wheel catalog: {source} -> {alias}"


def patch_pyproject(
    input_path: str,
    output_path: str,
    target_name: str,
    target_version: str,
    dry_run: bool = False,
) -> dict:
    """Patch a pyproject.toml for public distribution.

    Returns a dict with keys: patched, changes, output_path.
    """
    raw, parsed = _read_and_validate(input_path)

    old_name = parsed["project"]["name"]
    old_version = parsed["project"].get("version", "0.0.0")

    text = raw
    changes: list[str] = []

    # 1. Name swap
    text, change = _patch_name(text, old_name, target_name)
    if change:
        changes.append(change)

    # 2. Version set
    text, change = _patch_version(text, old_version, target_version)
    if change:
        changes.append(change)

    # 3. Rewrite wheel packages + force-include
    text, change = _patch_wheel_packages(text, target_name)
    if change:
        changes.append(change)

    # The public candidate handoff must be self-contained for normal pipx
    # resolution, without adding pip or pinned transitive dependencies to the
    # public wheel's Requires-Dist metadata.
    text, change = _add_offline_handoff_hook(text)
    if change:
        changes.append(change)

    text, change = _add_offline_handoff_build_requirement(text)
    if change:
        changes.append(change)

    # 4. Add CLI entry point
    text, change = _add_cli_entry_point(text, target_name)
    if change:
        changes.append(change)

    # 5. Remove dev-only sections
    for section in sorted(_DEV_SECTIONS):
        text, change = _remove_section(text, section)
        if change:
            changes.append(change)

    # Final cleanup: collapse triple+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. Privacy-strip the source tree the wheel force-include reads.
    #    Mutates the filesystem, so skip under --dry-run.
    if not dry_run:
        strip_change = _strip_private_artifacts(input_path)
        if strip_change:
            changes.append(strip_change)
        template_change = _stage_directory_build_alias(
            input_path,
            "nWave/templates",
            _TEMPLATE_BUILD_ALIAS,
            "templates",
        )
        if template_change:
            changes.append(template_change)
        data_change = _stage_directory_build_alias(
            input_path,
            "nWave/data",
            _DATA_BUILD_ALIAS,
            "data",
        )
        if data_change:
            changes.append(data_change)
        catalog_change = _stage_catalog_build_alias(input_path)
        if catalog_change:
            changes.append(catalog_change)

    patched = len(changes) > 0

    if not dry_run:
        Path(output_path).write_text(text, encoding="utf-8")

    return {
        "patched": patched,
        "changes": changes,
        "output_path": output_path,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Patch pyproject.toml for public distribution"
    )
    parser.add_argument(
        "--input", required=True, dest="input_path", help="Source pyproject.toml"
    )
    parser.add_argument(
        "--output", required=True, dest="output_path", help="Output path"
    )
    parser.add_argument("--target-name", required=True, help="Target package name")
    parser.add_argument("--target-version", required=True, help="Target version")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show diff without writing"
    )

    args = parser.parse_args()

    try:
        result = patch_pyproject(
            input_path=args.input_path,
            output_path=args.output_path,
            target_name=args.target_name,
            target_version=args.target_version,
            dry_run=args.dry_run,
        )
        print(json.dumps(result))
        sys.exit(0)
    except PatchError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
