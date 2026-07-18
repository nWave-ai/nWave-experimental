"""measure_blast_radius orchestration (slice-01, `--paths` input mode only).

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Architecture & Contract Tests -- `des blast-radius`, Reuse Analysis
  -- New components: `measure_blast_radius` orchestration).

Resolves a `--paths` scope into `BlastRadiusMeasures` + a classified tier:
`files` is the count of named paths (pure filesystem, no git required);
`lines_changed` is `git diff HEAD --numstat -- <paths>` (EXTEND `git_text`,
AD-22 SSOT) degrading to `None` -- never a fabricated `0` -- when the repo is
not a git work-tree or git is absent. `boundary_files`/`consumer_counts` are
NOT YET WIRED this slice (slice-02 scope) -- always empty, with an explicit
`reasons` entry naming that so an empty collection is never read as a real
zero-crossings/zero-consumers measurement (GDP-6 vacuous-truth family).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text
from des.domain.blast_radius import (
    BlastRadiusMeasures,
    BlastRadiusThresholds,
    BlastRadiusTier,
    classify_tier,
)


if TYPE_CHECKING:
    from pathlib import Path


_DEFAULT_THRESHOLDS = BlastRadiusThresholds()

_NOT_WIRED_REASON = (
    "boundary_files and consumer_counts are not yet wired (slice-02 scope) "
    "-- always empty in slice-01, never a real zero-crossings/zero-consumers "
    "measurement"
)


class BlastRadiusInputRejected(Exception):
    """One or more `--paths` entries do not exist under the repo root."""


@dataclass(frozen=True)
class BlastRadiusVerdict:
    """The classified tier + the measures + the self-explaining reasons."""

    tier: BlastRadiusTier
    measures: BlastRadiusMeasures
    reasons: list[str]


def measure_blast_radius(
    repo: Path,
    paths: list[str],
    thresholds: BlastRadiusThresholds = _DEFAULT_THRESHOLDS,
) -> BlastRadiusVerdict:
    """Measure the blast radius of `paths` under `repo` (`--paths` mode).

    Raises `BlastRadiusInputRejected` naming every missing path -- never a
    silent 0-file/0-line S-tier measurement of a typo'd path.
    """
    missing = [p for p in paths if not (repo / p).exists()]
    if missing:
        raise BlastRadiusInputRejected(
            f"the following --paths entries do not exist under {repo}: "
            + ", ".join(missing)
        )

    lines_changed, degrade_reason = _lines_changed(repo, paths)

    measures = BlastRadiusMeasures(files=len(paths), lines_changed=lines_changed)
    tier, tier_reasons = classify_tier(measures, thresholds)

    reasons = list(tier_reasons)
    if degrade_reason is not None:
        reasons.append(degrade_reason)
    reasons.append(_NOT_WIRED_REASON)

    return BlastRadiusVerdict(tier=tier, measures=measures, reasons=reasons)


def _lines_changed(repo: Path, paths: list[str]) -> tuple[int | None, str | None]:
    """Return `(lines_changed, degrade-reason)` -- git failure degrades to `None`."""
    try:
        stdout = git_text(repo, "diff", "HEAD", "--numstat", "--", *paths)
    except FileNotFoundError as exc:
        return None, f"git binary not found -- lines_changed is indeterminate: {exc}"
    except subprocess.CalledProcessError as exc:
        return None, (
            f"{repo} is not a git work-tree (git diff failed, exit "
            f"{exc.returncode}) -- lines_changed is indeterminate: "
            f"{(exc.stderr or '').strip()[:200]}"
        )
    total = 0
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        added_raw, deleted_raw, _path = fields
        if added_raw == "-" or deleted_raw == "-":
            continue
        total += int(added_raw) + int(deleted_raw)
    return total, None


__all__ = ["BlastRadiusInputRejected", "BlastRadiusVerdict", "measure_blast_radius"]
