"""Regression contract: the pre-push pytest tiers are diff-aware, not always-on.

Defect ``fix-pre-push-suite-not-diff-aware`` (RCA-approved fix, option a):
``pytest-quick-tiers`` and ``pytest-e2e`` carried ``always_run: true``, which
disables pre-commit 4.6.0's NATIVE pushed-range file classification
(``PRE_COMMIT_FROM_REF``/``TO_REF`` -> ``git diff --name-only from...to``).
A docs-only push therefore paid the full 3-15 min suite for changes no test
reads. Test SCOPE (whole-tree suite) was conflated with TRIGGER (always run).

This module locks BOTH halves of the fixed contract:

1. Config-shape -- on the two suite tiers ONLY: no ``always_run: true`` and an
   ``exclude`` allowlist present. The cheap/semantically-always-relevant hooks
   (``pytest-fast-gate``, ``des-declare-done-pre-push``) MUST keep
   ``always_run: true`` -- their always-on contract must not silently erode.
2. Behavioral -- the actual ``exclude`` regex from the config, compiled with
   pre-commit's own semantics (``re.compile`` as-is + ``.search``; the inline
   ``(?x)`` flag carries verbosity), classifies a fixed path table:
   test-irrelevant docs are SKIPPED (loud native ``(no files to check)
   Skipped``), while every test-consumed path class still TRIGGERS the suite.

Evidence basis for the allowlist (RCA-verified per path): no quick-tier or e2e
test reads ``docs/analysis/``, ``docs/feature/``, ``docs/archive/``,
``docs/internal/``, ``docs/product/backlog.md``, ``docs/product/done.md``, or
``docs/reference/`` (except ``docs/reference/global-config.md``) from the real
repo. Test-consumed classes (``docs/epic/``, ``docs/guides/``, glossary,
outcomes, ``docs/architecture/``, ``global-config.md``, root ``*.md``, all
non-docs) stay OUT of the allowlist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"

#: The two whole-suite pre-push tiers whose TRIGGER must be diff-aware.
DIFF_AWARE_HOOK_IDS = ("pytest-quick-tiers", "pytest-e2e")

#: Hooks that MUST stay always-on (cheap and/or semantically always-relevant).
ALWAYS_ON_HOOK_IDS = ("pytest-fast-gate", "des-declare-done-pre-push")

#: Docs-only, test-irrelevant paths: the exclude allowlist MUST match these,
#: so a push touching only them natively skips the suite tiers.
SKIPPED_CLASS_PATHS = (
    "docs/analysis/foo.md",
    "docs/feature/x/feature-delta.md",
    "docs/product/backlog.md",
    "docs/product/done.md",
    "docs/reference/skills/index.md",
    "docs/archive/old/adr-1.md",
    "docs/internal/notes.md",
)

#: Test-consumed path classes: the exclude allowlist MUST NOT match these --
#: a push touching any of them keeps triggering the full suite tiers.
TRIGGERING_CLASS_PATHS = (
    "docs/reference/global-config.md",
    "docs/epic/e1/epic-delta.md",
    "docs/guides/tutorial-x/setup.py",
    "docs/product/glossary.md",
    "docs/architecture/adr-025.md",
    "src/des/cli/foo.py",
    "tests/build/test_x.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "nWave/skills/nw-deliver/SKILL.md",
    "README.md",
    "conftest.py",
)


def _hooks_by_id() -> dict[str, dict]:
    """All hook definitions in .pre-commit-config.yaml, keyed by id."""
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    hooks: dict[str, dict] = {}
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            hooks[hook["id"]] = hook
    return hooks


def _hook(hook_id: str) -> dict:
    hooks = _hooks_by_id()
    assert hook_id in hooks, (
        f"hook `{hook_id}` not found in .pre-commit-config.yaml -- it was "
        f"renamed or removed. This regression contract pins it by id; update "
        f"the contract AND the fix together, never silently."
    )
    return hooks[hook_id]


def _exclude_pattern(hook_id: str) -> re.Pattern[str]:
    """The hook's exclude regex, compiled with pre-commit's semantics.

    pre-commit compiles ``exclude`` as-is (no external flags -- the inline
    ``(?x)`` flag inside the pattern carries verbosity) and classifies files
    with ``pattern.search(filename)``.
    """
    hook = _hook(hook_id)
    raw = hook.get("exclude")
    assert raw is not None, (
        f"hook `{hook_id}` has NO `exclude` allowlist -- without it every "
        f"pushed file (including test-irrelevant docs) triggers the suite "
        f"tier. Fix: add the docs-only allowlist regex "
        f"(anchor `&docs_only_test_irrelevant` on pytest-quick-tiers, alias "
        f"`*docs_only_test_irrelevant` on pytest-e2e) per the approved RCA."
    )
    return re.compile(raw)


# ---------------------------------------------------------------------------
# Half 1 -- config shape
# ---------------------------------------------------------------------------


def _check_no_always_run(hook_id: str) -> None:
    """``always_run: true`` must be ABSENT on the suite tiers.

    It disables pre-commit's native pushed-range file classification, so
    docs-only pushes pay the full suite. Scope stays whole-tree
    (``pass_filenames: false`` + the pytest cmdline); only the TRIGGER
    becomes file-aware.
    """
    hook = _hook(hook_id)
    assert hook.get("always_run") is not True, (
        f"hook `{hook_id}` declares `always_run: true`, which disables "
        f"pre-commit's native PRE_COMMIT_FROM_REF/TO_REF diff classification "
        f"-- docs-only pushes run the whole suite for nothing. Fix: remove "
        f"`always_run: true` (keep `pass_filenames: false`; scope is "
        f"unchanged, only the trigger becomes diff-aware)."
    )


def _check_exclude_present(hook_id: str) -> None:
    """The docs-only ``exclude`` allowlist must be PRESENT on the suite tiers."""
    _exclude_pattern(hook_id)  # asserts presence with the WHAT/WHY/HOW message


@pytest.mark.parametrize(
    "check",
    (_check_no_always_run, _check_exclude_present),
    ids=("no-always-run", "exclude-present"),
)
@pytest.mark.parametrize("hook_id", DIFF_AWARE_HOOK_IDS)
def test_suite_tier_trigger_is_diff_aware(hook_id: str, check) -> None:
    """Config-shape contract per suite tier: the TRIGGER is diff-aware.

    Two independent checks per hook, each its own parametrized case so one
    failure never masks the other's message: (a) no ``always_run: true``,
    (b) the ``exclude`` allowlist exists. Fix both in .pre-commit-config.yaml
    per the approved RCA (option a, zero new scripts).
    """
    check(hook_id)


def test_quick_tiers_and_e2e_share_one_exclude_pattern() -> None:
    """Both suite tiers must use the IDENTICAL allowlist regex.

    The fix expresses this as one YAML anchor (`&docs_only_test_irrelevant`)
    aliased on the second hook -- divergent copies would let the two tiers
    silently classify the same push differently.
    """
    quick = _hook("pytest-quick-tiers").get("exclude")
    e2e = _hook("pytest-e2e").get("exclude")
    assert quick is not None and e2e is not None, (
        "one or both suite tiers lack the `exclude` allowlist -- add the "
        "shared anchor/alias per the approved RCA fix."
    )
    assert quick == e2e, (
        "pytest-quick-tiers and pytest-e2e carry DIFFERENT exclude patterns "
        "-- the allowlist must be one YAML anchor/alias so the two tiers "
        "always classify a pushed range identically."
    )


@pytest.mark.parametrize("hook_id", ALWAYS_ON_HOOK_IDS)
def test_always_on_hooks_keep_always_run(hook_id: str) -> None:
    """The cheap / semantically-always-relevant hooks stay ``always_run``.

    The diff-aware fix applies ONLY to the two expensive suite tiers. If
    ``pytest-fast-gate`` or ``des-declare-done-pre-push`` loses
    ``always_run: true``, the always-on safety contract erodes silently --
    restore the flag on that hook.
    """
    hook = _hook(hook_id)
    assert hook.get("always_run") is True, (
        f"hook `{hook_id}` no longer declares `always_run: true` -- it is "
        f"cheap and/or semantically always-relevant and MUST run on every "
        f"push regardless of the pushed file set. Restore `always_run: true`."
    )


# ---------------------------------------------------------------------------
# Half 2 -- behavioral regex contract (pre-commit classification semantics)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", SKIPPED_CLASS_PATHS)
@pytest.mark.parametrize("hook_id", DIFF_AWARE_HOOK_IDS)
def test_exclude_matches_test_irrelevant_docs(hook_id: str, path: str) -> None:
    """Docs-only test-irrelevant paths MUST be excluded (suite skipped).

    A pushed range containing ONLY such paths yields pre-commit's loud
    native ``(no files to check) Skipped`` line for the suite tier.
    """
    pattern = _exclude_pattern(hook_id)
    assert pattern.search(path), (
        f"hook `{hook_id}` exclude allowlist does NOT match `{path}` -- a "
        f"push touching only this test-irrelevant path would still pay the "
        f"full suite tier. Extend the allowlist regex to cover its path "
        f"class (RCA-verified: no quick-tier/e2e test reads it from the "
        f"real repo)."
    )


@pytest.mark.parametrize("path", TRIGGERING_CLASS_PATHS)
@pytest.mark.parametrize("hook_id", DIFF_AWARE_HOOK_IDS)
def test_exclude_keeps_test_consumed_paths_triggering(hook_id: str, path: str) -> None:
    """Test-consumed path classes MUST NOT be excluded (suite triggers).

    Over-excluding any of these would let a change tests actually read slip
    past the pre-push suite -- the fail-closed direction of this contract.
    """
    pattern = _exclude_pattern(hook_id)
    assert not pattern.search(path), (
        f"hook `{hook_id}` exclude allowlist MATCHES `{path}`, but tests "
        f"consume this path class from the real repo -- excluding it lets a "
        f"test-relevant change push without running the suite. Narrow the "
        f"allowlist regex so this path class keeps triggering."
    )
