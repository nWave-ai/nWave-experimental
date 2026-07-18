"""measure_blast_radius orchestration (slice-02: the complete classifier).

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Architecture & Contract Tests -- `des blast-radius`, Reuse Analysis
  -- New components: `measure_blast_radius` orchestration).

Resolves a scope (`--paths` / `--staged` / `--diff <ref>`) into
`BlastRadiusMeasures` + a classified tier:

- `files` / `lines_changed` -- `git diff ... --numstat` (EXTEND `git_text`,
  AD-22 SSOT), degrading to `None` -- never a fabricated `0` -- when the repo
  is not a git work-tree or git is absent.
- `boundary_files` -- pure glob matching (git-free) against the configured
  `boundary_globs`.
- `consumer_counts` -- for every top-level symbol a touched Python file
  declares (via the existing `CodeFactPort` `query.atoms-in-file` capability,
  scoped to that single file), the number of distinct external call sites
  resolved via `query.callers-of` over the WHOLE repo tree. A touched Python
  file that cannot be parsed degrades its entry to `None` (D2: keyed on the
  file's repo-relative path), never a fabricated `0`.
- Thresholds are read from `DESConfig` (D3: rooted at the measured `--repo`,
  not the orchestrator's cwd), falling back to the canonical defaults when
  absent, and HARD-FAILING (`BlastRadiusConfigRejected`) when a present,
  well-typed value is outside its floor/ceiling.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.git.git_subprocess import git_text
from des.domain.blast_radius import (
    BlastRadiusConfigRejected,
    BlastRadiusMeasures,
    BlastRadiusTier,
    classify_tier,
)
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    CAPABILITY_CALLERS_OF,
    CapabilityDescriptor,
)


if TYPE_CHECKING:
    from des.ports.code_fact_port import CodeFactResult


__all__ = [
    "BlastRadiusConfigRejected",
    "BlastRadiusInputRejected",
    "BlastRadiusVerdict",
    "measure_blast_radius",
]


class BlastRadiusInputRejected(Exception):
    """The requested scope is malformed: a missing `--paths` entry, or the
    exactly-one-input-mode grammar was violated."""


@dataclass(frozen=True)
class BlastRadiusVerdict:
    """The classified tier + the measures + the self-explaining reasons."""

    tier: BlastRadiusTier
    measures: BlastRadiusMeasures
    reasons: list[str]


_ATOMS_DESCRIPTOR = CapabilityDescriptor(
    id=CAPABILITY_ATOMS_IN_FILE,
    stability="stable",
    contract_version="1.0.0",
    io_schema="atoms",
    providing_adapter="code-fact-chain",
)

_CALLERS_DESCRIPTOR = CapabilityDescriptor(
    id=CAPABILITY_CALLERS_OF,
    stability="stable",
    contract_version="1.0.0",
    io_schema="sites",
    providing_adapter="code-fact-chain",
)


def measure_blast_radius(
    repo: Path,
    *,
    paths: list[str] | None = None,
    staged: bool = False,
    diff_ref: str | None = None,
    config: DESConfig | None = None,
) -> BlastRadiusVerdict:
    """Measure the blast radius of the declared scope under `repo`.

    Exactly one of `paths` / `staged` / `diff_ref` is expected to be set by
    the caller (the CLI enforces the exactly-one-input-mode grammar before
    calling this). Raises `BlastRadiusInputRejected` naming every missing
    `--paths` entry -- never a silent 0-file/0-line S-tier measurement of a
    typo'd path. Raises `BlastRadiusConfigRejected` (propagated from
    `DESConfig`) when a configured threshold is present, well-typed, and
    outside its floor/ceiling (D4, GDP-3/GDP-6).
    """
    resolved_config = config or DESConfig(cwd=repo)
    thresholds = resolved_config.resolve_blast_radius_thresholds()

    scope_paths, lines_changed, degrade_reason = _resolve_scope(
        repo, paths=paths, staged=staged, diff_ref=diff_ref
    )

    boundary_files = _boundary_files(scope_paths, thresholds.boundary_globs)
    consumer_counts = _consumer_counts(repo, scope_paths)

    measures = BlastRadiusMeasures(
        files=len(scope_paths),
        lines_changed=lines_changed,
        boundary_files=tuple(boundary_files),
        consumer_counts=consumer_counts,
    )
    tier, tier_reasons = classify_tier(measures, thresholds)

    reasons = list(tier_reasons)
    if degrade_reason is not None:
        reasons.append(degrade_reason)

    return BlastRadiusVerdict(tier=tier, measures=measures, reasons=reasons)


# --- scope resolution (--paths / --staged / --diff <ref>) ------------------


def _resolve_scope(
    repo: Path,
    *,
    paths: list[str] | None,
    staged: bool,
    diff_ref: str | None,
) -> tuple[list[str], int | None, str | None]:
    """Return `(scope_paths, lines_changed, degrade_reason)` for the mode."""
    if paths is not None:
        missing = [p for p in paths if not (repo / p).exists()]
        if missing:
            raise BlastRadiusInputRejected(
                f"the following --paths entries do not exist under {repo}: "
                + ", ".join(missing)
            )
        stdout, degrade_reason = _git_diff_numstat(
            repo, "diff", "HEAD", "--numstat", "--", *paths
        )
        lines_changed = None if stdout is None else _sum_numstat(stdout)
        return list(paths), lines_changed, degrade_reason

    if staged:
        stdout, degrade_reason = _git_diff_numstat(
            repo, "diff", "--cached", "--numstat"
        )
        if stdout is None:
            return [], None, degrade_reason
        scope_paths, lines_changed = _paths_and_sum_numstat(stdout)
        return scope_paths, lines_changed, degrade_reason

    # diff_ref is not None (the CLI already enforced exactly-one-mode).
    stdout, degrade_reason = _git_diff_numstat(
        repo, "diff", diff_ref or "", "--numstat"
    )
    if stdout is None:
        return [], None, degrade_reason
    scope_paths, lines_changed = _paths_and_sum_numstat(stdout)
    return scope_paths, lines_changed, degrade_reason


def _git_diff_numstat(repo: Path, *args: str) -> tuple[str | None, str | None]:
    """Run a `git diff --numstat` variant; degrade to `(None, reason)` on failure."""
    try:
        return git_text(repo, *args), None
    except FileNotFoundError as exc:
        return None, f"git binary not found -- lines_changed is indeterminate: {exc}"
    except subprocess.CalledProcessError as exc:
        return None, (
            f"{repo} is not a git work-tree (git diff failed, exit "
            f"{exc.returncode}) -- lines_changed is indeterminate: "
            f"{(exc.stderr or '').strip()[:200]}"
        )


def _sum_numstat(stdout: str) -> int:
    """Total added+deleted lines across every `--numstat` row (binary rows skipped)."""
    total = 0
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        added_raw, deleted_raw, _path = fields
        if added_raw == "-" or deleted_raw == "-":
            continue
        total += int(added_raw) + int(deleted_raw)
    return total


def _paths_and_sum_numstat(stdout: str) -> tuple[list[str], int]:
    """`(distinct paths, total added+deleted lines)` from a `--numstat` output."""
    paths: list[str] = []
    total = 0
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        added_raw, deleted_raw, path = fields
        paths.append(path)
        if added_raw == "-" or deleted_raw == "-":
            continue
        total += int(added_raw) + int(deleted_raw)
    return paths, total


# --- boundary_files (pure glob matching, git-free) --------------------------

# Tokenizes a doublestar glob left-to-right, longest-match-first: a standalone
# "**/" (leading path segments, zero or more), a standalone "/**" (trailing
# path segments, zero or more), a bare "**" (anything, incl. "/"), a single
# "*" (anything within one path segment), "?" (one char within a segment), or
# any other single literal character (escaped verbatim in the output regex).
_GLOB_TOKEN_RE = re.compile(r"\*\*/|/\*\*|\*\*|\*|\?|.")

_GLOB_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


def _glob_to_regex(glob_pattern: str) -> re.Pattern[str]:
    """Compile `glob_pattern` (doublestar-aware) to an anchored regex.

    `fnmatch` treats `*` as `.*` uniformly, which requires the LITERAL `/`
    in a pattern like `**/schemas/**` to be present in the target string --
    it does NOT match a repo-root path with no leading directory (e.g.
    `schemas/thing.py`). Standard doublestar semantics treat a `**/` /`/**`
    segment as OPTIONAL (zero or more path segments), so this translator
    makes the adjoining `/` optional too.
    """
    cached = _GLOB_REGEX_CACHE.get(glob_pattern)
    if cached is not None:
        return cached
    pieces: list[str] = []
    for token in _GLOB_TOKEN_RE.findall(glob_pattern):
        if token == "**/":
            pieces.append("(?:.*/)?")
        elif token == "/**":
            pieces.append("(?:/.*)?")
        elif token == "**":
            pieces.append(".*")
        elif token == "*":
            pieces.append("[^/]*")
        elif token == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(token))
    compiled = re.compile("^" + "".join(pieces) + "$")
    _GLOB_REGEX_CACHE[glob_pattern] = compiled
    return compiled


def _boundary_files(
    scope_paths: list[str], boundary_globs: tuple[str, ...]
) -> list[str]:
    """The subset of `scope_paths` matching any `boundary_globs` entry, order preserved."""
    return [
        path
        for path in scope_paths
        if any(
            _glob_to_regex(glob).match(PurePosixPath(path).as_posix())
            for glob in boundary_globs
        )
    ]


# --- consumer_counts (CodeFactPort: atoms-in-file + callers-of) -------------


def _consumer_counts(repo: Path, scope_paths: list[str]) -> dict[str, int | None]:
    """`{"<module-stem>.<symbol>": <caller-count-or-None>}` for every touched .py file.

    D1 key format: `"<module-stem>.<symbol-name>"`. D2: an unparseable touched
    file keys on its repo-relative path with value `None`. Non-Python touched
    files contribute no entries.
    """
    consumer_counts: dict[str, int | None] = {}
    repo_chain = CodeFactChain(root=repo)
    for rel_path in scope_paths:
        if not rel_path.endswith(".py"):
            continue
        if not (repo / rel_path).exists():
            # D2: a deleted (staged) touched file has nothing on disk to
            # parse -- `Path.rglob()` on the nonexistent root silently
            # yields `[]`, which would otherwise vanish this file from the
            # payload entirely (neither measured nor flagged unparseable).
            # Degrade to the SAME unparseable-null rule as a genuine syntax
            # error: keyed on the repo-relative path, value None -- never
            # silence.
            consumer_counts[rel_path] = None
            continue
        file_chain = CodeFactChain(root=repo / rel_path)
        atoms_result = file_chain.query(_ATOMS_DESCRIPTOR, {})
        payload = _payload(atoms_result)
        if payload.get("unparseable"):
            consumer_counts[rel_path] = None
            continue
        module_stem = Path(rel_path).stem
        for atom in _string_list(payload.get("atoms")):
            key = f"{module_stem}.{atom}"
            callers_result = repo_chain.query(_CALLERS_DESCRIPTOR, {"symbol": atom})
            sites = _payload(callers_result).get("sites")
            consumer_counts[key] = len(sites) if isinstance(sites, list) else 0
    return consumer_counts


def _payload(result: CodeFactResult | None) -> dict[str, object]:
    """The result's payload as a dict, or `{}` when no tier answered (defensive)."""
    if result is None or not isinstance(result.payload, dict):
        return {}
    return result.payload


def _string_list(value: object) -> list[str]:
    """`value` as a `list[str]`, or `[]` when not a list (defensive)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
