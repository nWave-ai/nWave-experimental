"""Wave-agnostic execution-log path resolver.

Resolves the execution-log.json path for a DES project without assuming any
specific wave subdirectory (deliver/, bugfix/, design/, distill/, etc.).

Resolution algorithm (Option 2 from RCA):
1. If docs/feature/{project_id}/deliver/execution-log.json exists → use it
   (preserves backward compat for DELIVER-wave — the common case is fast).
2. Else glob docs/feature/{project_id}/*/execution-log.json:
   - Exactly 1 match → use it
   - 0 matches → raise FileNotFoundError
   - 2+ matches → raise ValueError (ambiguous; cannot determine active wave)

Root cause fixed:
    DES-PROJECT-ID encodes only the feature id, not the wave subdirectory.
    Both subagent_stop_handler.py and deliver_progress_handler.py previously
    hardcoded deliver/ as that missing segment — a relic of the DELIVER-only era.
    Bugfix, design, and distill features write logs to their own wave subdirs.
"""

from pathlib import Path


_DEFAULT_BASE = Path("docs") / "feature"


def resolve_execution_log_path(
    project_id: str,
    base: Path = _DEFAULT_BASE,
) -> Path:
    """Return the execution-log.json path for *project_id*.

    Args:
        project_id: The feature identifier (value of DES-PROJECT-ID marker).
        base: Parent directory containing per-project directories.
              Defaults to docs/feature (relative to cwd). Pass an absolute
              path when the cwd is not the repo root (e.g., in tests).

    Returns:
        Path to the execution-log.json file.

    Raises:
        FileNotFoundError: No execution-log.json found under the project dir.
        ValueError: Multiple execution-log.json files found and deliver/ is
                    absent — cannot determine which wave is active.
    """
    project_dir = base / project_id

    deliver_log = project_dir / "deliver" / "execution-log.json"
    if deliver_log.exists():
        return deliver_log

    candidates = list(project_dir.glob("*/execution-log.json"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            f"No execution-log.json under {project_dir}. "
            "The project may not have been initialized for this wave."
        )
    raise ValueError(
        f"Ambiguous: {len(candidates)} execution-log.json files found under "
        f"{project_dir}. Cannot determine active wave. "
        f"Candidates: {[str(c) for c in sorted(candidates)]}"
    )
