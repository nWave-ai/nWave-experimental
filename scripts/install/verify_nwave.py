#!/usr/bin/env python3
"""Standalone verification script for nWave Framework installation.

This script provides an independent way to verify nWave installation status
without running the full installer. It checks:
- Agent file counts in ~/.claude/agents/nw/
- Command file counts in ~/.claude/commands/nw/
- Manifest existence at ~/.claude/nwave-manifest.txt
- Essential command files (review.md, devops.md, etc.)
- Skills file counts in ~/.claude/skills/nw/
- DES module presence in ~/.claude/lib/python/des/
- Codex DES hook, agents (181 skills, 36 agents) [--platform codex]
- Cursor DES hook [--platform cursor]
- Devin skills (181 skills) [--platform devin]

The script supports multiple output modes:
- Terminal: Human-readable colored output (default)
- JSON: Machine-parseable output for Claude Code (--json flag)
- Verbose: Detailed information including counts (--verbose flag)

Exit codes:
- 0: Verification successful, all checks passed
- 1: Verification failed, missing files or manifest

Usage:
    # Default terminal output (Claude Code only)
    python verify_nwave.py

    # Verify all supported platforms
    python verify_nwave.py --platform all

    # Verify a specific platform
    python verify_nwave.py --platform codex
    python verify_nwave.py --platform cursor
    python verify_nwave.py --platform devin

    # JSON output for automated tools
    python verify_nwave.py --json

    # Verbose terminal output
    python verify_nwave.py --verbose

    # Combined flags
    python verify_nwave.py --json --verbose
"""

import argparse
import json
import sys
from pathlib import Path


try:
    from scripts.install.context_detector import is_claude_code_context
    from scripts.install.install_nwave import print_logo
    from scripts.install.install_utils import PathUtils
    from scripts.install.installation_verifier import (
        InstallationVerifier,
        VerificationResult,
    )
    from scripts.install.plugins.base import InstallContext, PluginResult
    from scripts.install.plugins.codex_des_plugin import CodexDESPlugin
    from scripts.install.plugins.codex_skills_plugin import CodexSkillsPlugin
    from scripts.install.plugins.codex_agents_plugin import CodexAgentsPlugin
    from scripts.install.plugins.cursor_des_plugin import CursorDESPlugin
    from scripts.install.plugins.devin_skills_plugin import DevinSkillsPlugin
    from scripts.install.rich_console import RichLogger
except ImportError:
    from context_detector import is_claude_code_context
    from install_nwave import print_logo
    from install_utils import PathUtils
    from installation_verifier import (
        InstallationVerifier,
        VerificationResult,
    )
    from plugins.base import InstallContext, PluginResult
    from plugins.codex_des_plugin import CodexDESPlugin
    from plugins.codex_skills_plugin import CodexSkillsPlugin
    from plugins.codex_agents_plugin import CodexAgentsPlugin
    from plugins.cursor_des_plugin import CursorDESPlugin
    from plugins.devin_skills_plugin import DevinSkillsPlugin
    from rich_console import RichLogger


_NATIVE_PLATFORMS = ("codex", "cursor", "devin")


def _project_root() -> Path:
    """Return the nWave-experimental repo root (parent of scripts/install/)."""
    return Path(__file__).resolve().parent.parent.parent


def _make_verify_context(claude_dir: Path, platform: str, logger: object) -> InstallContext:
    """Build a minimal InstallContext sufficient for plugin verify() calls."""
    repo_root = _project_root()
    # Mirror NWaveInstaller: prefer nWave/ (dev checkout), fall back to dist/
    framework_source = repo_root / "nWave"
    if not framework_source.exists():
        framework_source = repo_root / "dist"
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=repo_root / "scripts",
        templates_dir=claude_dir / "templates",
        logger=logger,
        project_root=repo_root,
        framework_source=framework_source,
        target_platforms={platform},
    )


def verify_native_platform(
    platform: str,
    claude_dir: Path,
    logger: object,
) -> list[PluginResult]:
    """Run verify() for each plugin relevant to a native platform.

    Returns a list of PluginResult — one per plugin checked.
    """
    ctx = _make_verify_context(claude_dir, platform, logger)
    results: list[PluginResult] = []
    if platform == "codex":
        results.append(CodexSkillsPlugin().verify(ctx))
        results.append(CodexAgentsPlugin().verify(ctx))
        results.append(CodexDESPlugin().verify(ctx))
    elif platform == "cursor":
        results.append(CursorDESPlugin().verify(ctx))
    elif platform == "devin":
        results.append(DevinSkillsPlugin().verify(ctx))
    return results


def format_native_results(
    platform: str, results: list[PluginResult], verbose: bool = False
) -> str:
    """Format native-platform plugin verify results for terminal output."""
    lines = [f"\n  Platform: {platform}"]
    all_ok = all(r.success for r in results)
    for r in results:
        icon = "✅" if r.success else "❌"
        lines.append(f"    {icon} {r.plugin_name}: {r.message}")
        if not r.success and r.errors:
            for e in r.errors:
                lines.append(f"        ⚠️  {e}")
    if all_ok:
        lines.append(f"  ✅ {platform} verification passed")
    else:
        lines.append(f"  ❌ {platform} verification failed")
    return "\n".join(lines)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: List of argument strings. If None, uses sys.argv.

    Returns:
        Parsed arguments namespace with json and verbose flags.
    """
    parser = argparse.ArgumentParser(
        description="Verify nWave Framework installation status.",
        epilog="Exit code 0 indicates success, non-zero indicates verification failure.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format for machine parsing",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include detailed verification information",
    )
    parser.add_argument(
        "--platform",
        choices=["claude-code", "codex", "cursor", "devin", "all"],
        default="claude-code",
        help=(
            "Platform to verify (default: claude-code). "
            "Use 'all' to verify every supported platform."
        ),
    )
    return parser.parse_args(args)


def run_verification(claude_config_dir: Path | None = None) -> VerificationResult:
    """Run installation verification.

    This function delegates to InstallationVerifier to perform the actual
    verification checks.

    Args:
        claude_config_dir: Optional path to Claude config directory.
                          Defaults to ~/.claude via InstallationVerifier.

    Returns:
        VerificationResult containing all verification details.
    """
    verifier = InstallationVerifier(claude_config_dir=claude_config_dir)
    return verifier.run_verification()


def format_terminal_output(
    result: VerificationResult,
    verbose: bool = False,
) -> str:
    """Format verification result for terminal output.

    Args:
        result: VerificationResult from verification run.
        verbose: If True, include detailed counts and file information.

    Returns:
        Formatted string for terminal display.
    """
    lines = []

    if result.success:
        lines.append("  ✅ nWave installation verification passed")
    else:
        lines.append("  ❌ nWave installation verification failed")

    if verbose or not result.success:
        lines.append("")
        lines.append(f"    📦 Agent files: {result.agent_file_count}")
        lines.append(f"    📦 Command files: {result.command_file_count}")
        lines.append(
            f"    📦 Skill files: {result.skill_file_count} in {result.skill_group_count} groups"
        )
        des_icon = "✅" if result.des_installed else "❌"
        lines.append(f"    🔒 DES module: {des_icon}")
        manifest_icon = "✅" if result.manifest_exists else "❌"
        lines.append(f"    📄 Manifest: {manifest_icon}")

        if result.missing_essential_files:
            lines.append("")
            lines.append("    ⚠️ Missing essential files:")
            for filename in result.missing_essential_files:
                lines.append(f"      ❌ {filename}")
            lines.append("")
            lines.append("    💡 Re-run the nWave installer to restore missing files")

        if not result.manifest_exists:
            lines.append("")
            lines.append("    💡 Re-run the nWave installer to create the manifest")

    lines.extend(_preserved_not_managed_lines(result.unaccounted_files))

    return "\n".join(lines)


def _preserved_not_managed_lines(unaccounted_files: dict[str, list[str]]) -> list[str]:
    """Informational listing of files preserved on disk, not managed by nWave.

    Provenance is unprovable (a user-created asset and a pre-manifest orphan
    are indistinguishable by record membership), so the listing is purely
    informational — never a deletion suggestion. Empty families render nothing.
    """
    families = {
        family: names for family, names in sorted(unaccounted_files.items()) if names
    }
    if not families:
        return []
    lines = ["", "    📄 Preserved, not managed by nWave:"]
    lines.extend(
        f"      {family}: {', '.join(names)}" for family, names in families.items()
    )
    return lines


def format_json_output(result: VerificationResult, verbose: bool = False) -> str:
    """Format verification result as JSON.

    Args:
        result: VerificationResult from verification run.
        verbose: If True, include all fields. If False, minimal output.

    Returns:
        JSON string representation of the verification result.
    """
    output = {
        "success": result.success,
        "agent_file_count": result.agent_file_count,
        "command_file_count": result.command_file_count,
        "skill_file_count": result.skill_file_count,
        "skill_group_count": result.skill_group_count,
        "des_installed": result.des_installed,
        "manifest_exists": result.manifest_exists,
        "missing_essential_files": result.missing_essential_files,
        # Always present, even when empty: an absent listing is "no orphan
        # visibility", not a clean bill (informational, never a failure).
        "unaccounted_files": result.unaccounted_files,
    }

    if result.error_code:
        output["error_code"] = result.error_code

    if not result.success:
        output["remediation"] = "Re-run the nWave installer to restore missing files."

    if verbose:
        output["message"] = result.message

    return json.dumps(output, indent=2)


def main(
    args: list[str] | None = None,
    claude_config_dir: Path | None = None,
) -> int:
    """Main entry point for standalone verification.

    Parses arguments, runs verification, and outputs results in the
    appropriate format based on context and flags.

    Args:
        args: Command line arguments. If None, uses sys.argv.
        claude_config_dir: Optional path to Claude config directory for testing.

    Returns:
        Exit code: 0 for success, 1 for verification failure.
    """
    parsed_args = parse_args(args)

    # Determine output mode early to configure logger appropriately
    use_json = parsed_args.json or is_claude_code_context()

    # Initialize logging to shared installation log file
    # In JSON mode, suppress console output to avoid polluting JSON output
    config_dir = claude_config_dir or PathUtils.get_claude_config_dir()
    log_file = config_dir / "nwave-install.log"
    logger = RichLogger(log_file=log_file, silent=use_json)

    if not use_json:
        print_logo(logger)
        logger.info("")
        logger.info("  🔍 nWave verification started")

    platform = getattr(parsed_args, "platform", "claude-code")
    native_platforms = (
        list(_NATIVE_PLATFORMS) if platform == "all"
        else [platform] if platform in _NATIVE_PLATFORMS
        else []
    )
    run_claude_code = platform in ("claude-code", "all")

    overall_success = True

    # Claude Code verification
    if run_claude_code:
        result = run_verification(claude_config_dir=claude_config_dir)
        if result.success:
            logger.info(
                f"  ✅ Verification passed: {result.agent_file_count} agents, "
                f"{result.command_file_count} commands, "
                f"{result.skill_file_count} skills, DES installed"
            )
        else:
            logger.error(f"  ❌ Verification failed: {result.message}")
            if result.missing_essential_files:
                logger.error(
                    f"    ⚠️ Missing: {', '.join(result.missing_essential_files)}"
                )
            overall_success = False

        if use_json:
            output = format_json_output(result, verbose=parsed_args.verbose)
        else:
            output = format_terminal_output(result, verbose=parsed_args.verbose)
        print(output)

    # Native platform verification (Codex, Cursor, Devin)
    native_results: dict[str, list[PluginResult]] = {}
    for p in native_platforms:
        p_results = verify_native_platform(p, config_dir, logger)
        native_results[p] = p_results
        if not all(r.success for r in p_results):
            overall_success = False
        if not use_json:
            print(format_native_results(p, p_results, verbose=parsed_args.verbose))

    if use_json and native_results:
        native_summary = {
            p: {
                "success": all(r.success for r in rs),
                "checks": [
                    {"plugin": r.plugin_name, "success": r.success, "message": r.message,
                     "errors": r.errors}
                    for r in rs
                ],
            }
            for p, rs in native_results.items()
        }
        print(json.dumps({"platforms": native_summary}, indent=2))

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
