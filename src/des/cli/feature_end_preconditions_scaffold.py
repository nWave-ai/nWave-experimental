"""des feature-end-preconditions-scaffold -- the producing tool for the two
feature-end certification preconditions the real gates already consume
(feature-end-certifies-real-consumers, slice-01).

- `## Environmental E2E` block (`docs/feature/<id>/feature-delta.md`) --
  consumed by `des verify-environmental-e2e --mode run`
  (`src/des/cli/verify_environmental_e2e.py:516`, presence-checked via
  `has_environmental_e2e_block`).
- `.nwave/demo-recipe.json` -- consumed by `des verify-fresh-clone`
  (`src/des/cli/verify_fresh_clone.py:50`, schema `RECIPE_RELPATH` +
  `{"steps": [{"name", "cmd": [...]}], "timeout_seconds"}`).

Mirrors `charter_scaffold.py`'s shape (DESIGN §New components #1): pure
parse/render core + thin argparse shell, idempotent (never overwrites),
degrade-LOUD JSON verdict on every failure class. Two `--target` modes:

- `--target environmental-e2e --feature-id <id> --e2e-test <path>
  [--repo-root .]` -- appends `## Environmental E2E\\n- test: <path>\\n` when
  absent (idempotent no-op otherwise); degrades LOUD on a missing
  feature-delta or an `--e2e-test` path that is not an existing file.
- `--target demo-recipe [--repo-root .]` -- CONSERVATIVE detection only
  (Earned Trust / GDP-6: a guessed-wrong recipe is worse than none, because
  `verify-fresh-clone` would then degrade LOUD against the WRONG steps).
  Writes `.nwave/demo-recipe.json` ONLY when exactly one confident
  install/build/test convention is detected (a resolvable src+tests layout
  AND a `pyproject.toml [tool.poe.tasks]` declaring install/build/test);
  otherwise degrades LOUD with a HOW telling the operator to hand-author.

CLI contract:
    des feature-end-preconditions-scaffold --target environmental-e2e \\
        --feature-id <id> --e2e-test <path> [--repo-root .]
    des feature-end-preconditions-scaffold --target demo-recipe [--repo-root .]

stdout token (JSON): {target, written, verdict, detail}
`written` is True only when this run put NEW content on disk; `verdict ==
"accepted"` covers both a real write and an idempotent no-op (exit 0
either way); any other verdict is a degrade-LOUD reject (exit non-zero,
`written` never True).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument
from des.cli._scaffold_core import decide_on_exists, emit_scaffold_verdict
from des.cli.axis_b_levers import resolve_layout
from des.cli.validate_feature_delta import VERDICT_ACCEPTED
from des.cli.verify_fresh_clone import RECIPE_RELPATH
from des.domain.environmental_e2e import has_environmental_e2e_block
from des.domain.repo_path_resolver import feature_delta_path


TARGET_ENVIRONMENTAL_E2E = "environmental-e2e"
TARGET_DEMO_RECIPE = "demo-recipe"

#: Degrade-LOUD verdict tokens -- every other verdict this tool can emit is
#: `VERDICT_ACCEPTED` (imported, the SAME acceptance-verdict vocabulary
#: `charter_scaffold`/`validate_feature_delta` already share).
VERDICT_MISSING_FEATURE_DELTA = "missing-feature-delta"
VERDICT_E2E_TEST_NOT_FOUND = "e2e-test-not-found"
VERDICT_LAYOUT_NOT_CONFIDENT = "layout-not-confidently-detected"

_ENVIRONMENTAL_E2E_HEADING = "## Environmental E2E"
_E2E_BLOCK_TEST_LINE_RE = re.compile(
    r"^##\s+Environmental\s+E2E\s*\n-\s+test:\s*(?P<path>.+?)\s*$",
    re.MULTILINE,
)

#: `--target demo-recipe`'s ONE confident detection convention: a
#: `pyproject.toml [tool.poe.tasks]` declaring all three of these tasks.
_REQUIRED_RECIPE_TASKS = ("install", "build", "test")
_POE_TASKS_SECTION_RE = re.compile(
    r"^\[tool\.poe\.tasks\]\s*$(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL
)
_POE_TASK_ENTRY_RE = re.compile(
    r'^\s*([A-Za-z0-9_-]+)\s*=\s*"([^"]*)"\s*$', re.MULTILINE
)


def _emit(target: str, written: bool, verdict: str, detail: str) -> int:
    """Print the shared `{target, written, verdict, detail}` JSON payload and
    return the exit code -- 0 on `accepted`, 1 on any degrade-LOUD verdict.
    Delegates to the shared des.cli._scaffold_core verdict envelope (D49)."""
    return emit_scaffold_verdict(
        {
            "target": target,
            "written": written,
            "verdict": verdict,
            "detail": detail,
        }
    )


# --- --target environmental-e2e -------------------------------------------


def _existing_e2e_test_path(content: str) -> str | None:
    """The declared `- test: <path>` value of an ALREADY-present block, or
    None. Pure."""
    match = _E2E_BLOCK_TEST_LINE_RE.search(content)
    return match.group("path") if match else None


def _environmental_e2e_block(e2e_test_relpath: str) -> str:
    """The well-formed block text to append. Pure."""
    return f"\n{_ENVIRONMENTAL_E2E_HEADING}\n- test: {e2e_test_relpath}\n"


def _run_environmental_e2e(
    repo_root: Path, feature_id: str, e2e_test_relpath: str
) -> int:
    """Append `## Environmental E2E` when absent; idempotent no-op otherwise.
    Not pure (filesystem read/write + stdout print)."""
    delta_path = feature_delta_path(repo_root, feature_id)
    if not delta_path.is_file():
        return _emit(
            TARGET_ENVIRONMENTAL_E2E,
            False,
            VERDICT_MISSING_FEATURE_DELTA,
            f"feature-delta not found for '{feature_id}': {delta_path}",
        )

    content = delta_path.read_text(encoding="utf-8")
    exists_decision = decide_on_exists(
        target_exists=has_environmental_e2e_block(content), policy="skip"
    )
    if exists_decision == "skip":
        existing = _existing_e2e_test_path(content) or "<unreadable>"
        return _emit(
            TARGET_ENVIRONMENTAL_E2E,
            False,
            VERDICT_ACCEPTED,
            f"Environmental E2E block already present (test: {existing}); "
            "left untouched",
        )

    e2e_test_path = repo_root / e2e_test_relpath
    if not e2e_test_path.is_file():
        return _emit(
            TARGET_ENVIRONMENTAL_E2E,
            False,
            VERDICT_E2E_TEST_NOT_FOUND,
            f"--e2e-test path does not exist: {e2e_test_relpath}",
        )

    delta_path.write_text(
        content + _environmental_e2e_block(e2e_test_relpath), encoding="utf-8"
    )
    return _emit(
        TARGET_ENVIRONMENTAL_E2E,
        True,
        VERDICT_ACCEPTED,
        f"appended Environmental E2E block (test: {e2e_test_relpath})",
    )


# --- --target demo-recipe --------------------------------------------------


def _poe_tasks(repo_root: Path) -> dict[str, str] | None:
    """The `[tool.poe.tasks]` name -> command-string map, or None when the
    section/file is absent. Pure (filesystem read). Stdlib-only mini-parser
    (mirrors `axis_b_levers._pyproject_testpath`'s regex extraction -- no
    tomllib/tomli dependency)."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        text = pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    section = _POE_TASKS_SECTION_RE.search(text)
    if section is None:
        return None
    tasks = dict(_POE_TASK_ENTRY_RE.findall(section.group(1)))
    return tasks or None


def _confidently_detected_recipe_steps(
    repo_root: Path,
) -> list[dict[str, object]] | None:
    """The recipe steps for a CONFIDENTLY-detected convention, or None when
    not confidently detectable (GDP-6: conservative, never a guess). Not pure
    (resolves layout + reads pyproject via filesystem).

    Confidence requires BOTH: a resolvable src+tests layout (`resolve_layout`,
    EXTEND) AND a `pyproject.toml [tool.poe.tasks]` declaring all three of
    install/build/test -- the ONE convention this tool trusts.
    """
    layout = resolve_layout(repo_root, source_dir="src", tests_dir="tests")
    if layout.resolution != "resolved":
        return None
    tasks = _poe_tasks(repo_root)
    if tasks is None or not all(
        tasks.get(name, "").strip() for name in _REQUIRED_RECIPE_TASKS
    ):
        return None
    return [
        {"name": name, "cmd": tasks[name].split()} for name in _REQUIRED_RECIPE_TASKS
    ]


def _run_demo_recipe(repo_root: Path) -> int:
    """Write `.nwave/demo-recipe.json` only when confidently detectable;
    idempotent no-op when it already exists. Not pure (filesystem
    read/write + stdout print)."""
    recipe_path = repo_root / RECIPE_RELPATH
    if decide_on_exists(target_exists=recipe_path.is_file(), policy="skip") == "skip":
        return _emit(
            TARGET_DEMO_RECIPE,
            False,
            VERDICT_ACCEPTED,
            f"{RECIPE_RELPATH} already exists; left untouched",
        )

    steps = _confidently_detected_recipe_steps(repo_root)
    if steps is None:
        return _emit(
            TARGET_DEMO_RECIPE,
            False,
            VERDICT_LAYOUT_NOT_CONFIDENT,
            "could not confidently detect a single install/build/test "
            f"convention -- hand-author {RECIPE_RELPATH} yourself, schema: "
            '{"steps": [{"name": "build", "cmd": ["<cmd>", "..."]}], '
            '"timeout_seconds": 600}',
        )

    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(
        json.dumps({"steps": steps, "timeout_seconds": 600}, indent=2) + "\n",
        encoding="utf-8",
    )
    return _emit(
        TARGET_DEMO_RECIPE,
        True,
        VERDICT_ACCEPTED,
        f"wrote {RECIPE_RELPATH} ({len(steps)} steps)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feature-end-preconditions-scaffold",
        description=(
            "Generate the two feature-end certification preconditions -- a "
            "feature's `## Environmental E2E` block, and the project's "
            "`.nwave/demo-recipe.json` -- that verify-environmental-e2e and "
            "verify-fresh-clone already consume. Idempotent (never "
            "overwrites); degrades LOUD (non-zero + JSON verdict/detail) on "
            "every failure class."
        ),
    )
    parser.add_argument(
        "--target",
        choices=(TARGET_ENVIRONMENTAL_E2E, TARGET_DEMO_RECIPE),
        required=True,
        help="Which precondition to scaffold.",
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help="Required for --target environmental-e2e.",
    )
    parser.add_argument(
        "--e2e-test",
        default=None,
        help=(
            "Required for --target environmental-e2e: repo-relative path to "
            "the declared e2e test."
        ),
    )
    add_repo_root_argument(
        parser, "--repo-root", default=".", help="Repository root (default: cwd)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Scaffold one precondition; return 0 on `accepted`, non-zero on any
    degrade-LOUD verdict. Dispatches on `--target`."""
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root)

    if args.target == TARGET_ENVIRONMENTAL_E2E:
        return _run_environmental_e2e(repo_root, args.feature_id, args.e2e_test)
    return _run_demo_recipe(repo_root)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
