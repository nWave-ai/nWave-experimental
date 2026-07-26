"""Centralized installation path constants -- single source of truth.

Replaces 10+ scattered hardcoded path constructions across installer
plugins, verifier, and build scripts.

All consumers should import from this module::

    from scripts.shared.install_paths import AGENTS_SUBDIR, agents_dir
"""

from __future__ import annotations

import os
import sys
from pathlib import Path, PureWindowsPath


def _standard_temp_roots() -> list[Path]:
    """The hand-maintained enumeration of standard ephemeral-directory roots.

    This is a DECLARED ENUMERATION, not a computed property -- "this
    directory will be cleaned up out from under a running process" is not
    something the filesystem can be asked; it is convention, platform by
    platform. A list that admits it is a list invites the next reader to
    add a case when a new convention shows up (e.g. a fifth OS, a new
    container runtime's scratch mount); dressing this up as something
    derived would instead convince them there is nothing left to add. Keep
    it a visible, literal list -- extend THIS function, never bolt a
    special case onto the caller.

    ``tempfile.gettempdir()`` is deliberately NOT consulted here, and
    exactly one candidate from it (a fresh boot's likely pick) is NOT
    equivalent to this list. ``gettempdir()`` returns exactly ONE root --
    whichever standard candidate was first writable when the interpreter
    started -- never the full set of standard ephemeral locations. A
    guard that keys on it alone leaves every OTHER standard root open: on
    a box where ``gettempdir()`` picked ``/tmp``, an interpreter rooted
    under ``/var/tmp`` or ``/usr/tmp`` -- equally standard, equally
    ephemeral -- would be judged durable. That is the exact
    one-known-bad-shape mistake this whole predicate exists to fix,
    reappearing one level down inside the function written to fix it.

    Worse, ``tempfile.gettempdir()`` has a documented LAST-RESORT
    fallback: when every standard root above is unwritable, it returns
    the process's OWN current working directory. Consulting it directly
    would then treat the CWD as ephemeral too -- on such a machine, EVERY
    interpreter under a developer's checkout (including its own
    ``.venv/bin/python``) would be rejected. This function's list never
    includes the CWD, on purpose: it enumerates ONLY genuine, named
    system/user ephemeral-directory conventions, sourced by hand rather
    than through the stdlib's own candidate search
    (``tempfile._candidate_tempdir_list()``, deliberately not imported --
    it is a private API that can change without notice, and importing it
    would import its CWD fallback entry right along with it, as if that
    were one of THIS guard's roots).

    Sources (named, not derived): the environment variables the stdlib
    itself consults first when set (``$TMPDIR``, ``$TEMP``, ``$TMP``, in
    that order), then the platform's standard directories: POSIX
    ``/tmp``, ``/var/tmp``, ``/usr/tmp``; Windows
    ``%LOCALAPPDATA%\\Temp``, ``%SYSTEMROOT%\\Temp``, ``C:\\TEMP``,
    ``C:\\TMP``, ``\\TEMP``, ``\\TMP``.

    The Windows six are NOT a uniform list, and this docstring says so
    rather than staying silent about it:

    - The first two (``%LOCALAPPDATA%\\Temp`` via ``Path.expanduser()``,
      ``%SYSTEMROOT%\\Temp`` via ``os.path.expandvars()``) are RESOLVED
      at call time into concrete, fully-qualified paths.
    - The last four (``C:\\Temp``, ``C:\\Tmp``, ``\\Temp``, ``\\Tmp``)
      are literal templates, unresolved beyond ``Path.resolve()`` in
      ``is_durable_interpreter_path``.
    - Of those four, ``\\Temp`` and ``\\Tmp`` are DRIVE-RELATIVE, not
      absolute: Windows resolves a leading-backslash-no-drive path
      against whichever drive is current for the process, not
      necessarily ``C:``. This predicate does not special-case that
      resolution -- it relies on ``Path.resolve()`` to do whatever the
      OS itself would do with a drive-relative path, and does not verify
      the result on Windows (this module is authored and evaluated from
      a POSIX box). Documented here as a known, stated limitation rather
      than a silent gap: if drive-relative resolution ever proves wrong
      in practice, THIS is where to fix it, and the fix is either
      normalizing these two entries to a specific drive, or removing
      them and accepting narrower Windows coverage -- not silently
      trusting an unverified assumption.
    """
    roots: list[Path] = []
    for env_var in ("TMPDIR", "TEMP", "TMP"):
        value = os.environ.get(env_var)
        if value:
            roots.append(Path(value))
    if sys.platform.startswith("win"):
        roots.extend(
            Path(candidate)
            for candidate in (
                Path(r"~\AppData\Local\Temp").expanduser(),
                os.path.expandvars(r"%SYSTEMROOT%\Temp"),
                r"C:\Temp",
                r"C:\Tmp",
                r"\Temp",
                r"\Tmp",
            )
        )
    else:
        roots.extend(Path(candidate) for candidate in ("/tmp", "/var/tmp", "/usr/tmp"))
    return roots


def is_durable_interpreter_path(path: str) -> bool:
    """Return True iff ``path`` is safe to persist for later execution.

    Answers ONLY the durability question -- will this path still exist
    when the persisted artifact (settings.json hook command, git shim,
    Copilot/Codex/OpenCode hook config) is invoked in the future? This is
    a DIFFERENT question from portability (whether the exact path is
    valid on a different machine): a ``$HOME``-rooted project ``.venv``
    is durable but not portable, and each call site's own ``.venv`` guard
    -- unchanged by this predicate -- answers that separate question.

    Rejects any path rooted under one of ``_standard_temp_roots()`` --
    see that function's docstring for why this is a hand-maintained
    enumeration rather than ``tempfile.gettempdir()`` alone, and why the
    current working directory is excluded from it on purpose.

    Both ``path`` and each candidate root are RESOLVED (``Path.resolve()``
    -- symlinks followed, ``.``/``..`` collapsed) before comparison. A
    lexical-only prefix check is not enough: on macOS, ``/tmp`` is itself
    a symlink to a different real path than the per-process ``$TMPDIR``
    (which lives under ``/var/folders/...``); an interpreter captured
    with the literal ``/tmp/...`` shape -- the exact shape of the
    2026-07-24 incident this predicate exists for -- resolves through
    that symlink into the real temp root and would escape a
    string-prefix-only comparison entirely. Do not simplify this back to
    a plain ``str.startswith`` "to keep it simple": the case that
    motivates the resolve is invisible on a box where none of the
    standard roots happen to be symlinks, which is exactly what makes it
    easy to remove by someone who cannot reproduce it locally.
    """
    if not path:
        return False
    candidate = Path(path).resolve()
    for root in _standard_temp_roots():
        resolved_root = root.resolve()
        if candidate == resolved_root or resolved_root in candidate.parents:
            return False
    return True


# Relative path segments (appended to claude_dir by callers)
AGENTS_SUBDIR = Path("agents") / "nw"
SKILLS_SUBDIR = Path("skills")
TEMPLATES_SUBDIR = Path("templates")
DES_LIB_SUBDIR = Path("lib") / "python" / "des"
SCRIPTS_SUBDIR = Path("scripts")
COMMANDS_LEGACY_SUBDIR = Path("commands") / "nw"  # deprecated, cleanup only
MANIFEST_FILENAME = "nwave-manifest.txt"
GLOBAL_CONFIG_FILENAME = "global-config.json"


def host_neutral_runtime_dir() -> Path:
    """Return the shared DES runtime root, independent of any host adapter."""
    return Path.home() / ".nwave" / "runtime"


def agents_dir(claude_dir: Path) -> Path:
    """Return the agents installation directory."""
    return claude_dir / AGENTS_SUBDIR


def skills_dir(claude_dir: Path) -> Path:
    """Return the skills installation directory."""
    return claude_dir / SKILLS_SUBDIR


def templates_dir(claude_dir: Path) -> Path:
    """Return the templates installation directory."""
    return claude_dir / TEMPLATES_SUBDIR


def des_dir(claude_dir: Path) -> Path:
    """Return the DES library installation directory."""
    return claude_dir / DES_LIB_SUBDIR


def manifest_path(claude_dir: Path) -> Path:
    """Return the installation manifest file path."""
    return claude_dir / MANIFEST_FILENAME


# -- Python command resolution ------------------------------------------------

# Literal pattern used in source templates for portable Python resolution.
# Installed files replace this with the resolved concrete path.
PYTHON_CMD_SUBSTITUTION = "$(command -v python3 || command -v python)"


def resolve_python_command() -> str:
    """Return the base Python command name for skill/command templates.

    Returns 'python3' unconditionally. Templates that consume this value
    are rendered into markdown documents that run in contexts with PATH
    resolution, so the base command name is what callers want -- never
    an absolute path.

    For contexts that need an absolute path (non-shell spawn), see
    resolve_python_command_for_spawn(). For $HOME-prefixed paths in
    shell-execution contexts (settings.json hook commands), see
    DESPlugin._resolve_python_path().
    """
    return "python3"


def resolve_python_command_for_spawn() -> str:
    """Return an absolute forward-slash path to the current Python interpreter.

    Use when the consuming code spawns the interpreter without a shell:
    TypeScript Bun.spawn, Node child_process.spawn, Python subprocess.run
    without shell=True, posix_spawn/CreateProcess directly.

    Cross-platform safety: uses Path.as_posix() so the result contains no
    backslashes on any platform. This lets the path embed safely into a
    TypeScript double-quoted string literal without triggering escape-
    sequence interpretation (e.g. \\U unicode escape, \\n newline).
    Windows APIs accept forward-slash paths since Windows 2000.

    The .venv fallback is preserved: when the installer runs from a
    project-local virtual environment (development, CI), returns 'python3'
    to avoid leaking development paths into user-installed artifacts.

    For shell-execution contexts (settings.json hook commands, bash
    scripts where $HOME is expanded), use the existing $HOME-based
    pattern in DESPlugin._resolve_python_path() instead.
    For markdown templates consumed by various runtimes, use
    resolve_python_command() (basename-only) instead.
    """
    python_path = sys.executable
    if not is_durable_interpreter_path(python_path):
        return "python3"
    if "/.venv/" in python_path or "\\.venv\\" in python_path:
        return "python3"
    return (
        PureWindowsPath(python_path).as_posix()
        if "\\" in python_path
        else Path(python_path).as_posix()
    )


def resolve_des_lib_path_for_spawn() -> str:
    """Return an absolute forward-slash path to the DES library directory.

    Same rationale as resolve_python_command_for_spawn: consumers pass
    this to non-shell contexts (Bun.spawn env vars setting PYTHONPATH,
    Python subprocess.run without shell=True) where shell variable
    expansion does NOT happen, so '$HOME' stays literal and must be
    resolved at install time.
    """
    return host_neutral_runtime_dir().as_posix()
