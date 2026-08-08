"""JsonlAuditLogReader - driven adapter for reading audit events.

Implements the AuditLogReader port by reading JSONL files.
Uses the same log directory resolution as JsonlAuditLogWriter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from des.domain.audit_log_path_resolver import AuditLogPathResolver
from des.ports.driven_ports.audit_log_reader import AuditLogReader


if TYPE_CHECKING:
    from pathlib import Path


_AGENT_USAGE_EVENT = "AGENT_USAGE_OBSERVED"
_USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


@dataclass(frozen=True)
class AgentUsageStageAggregate:
    """Deduped token totals for one `stage` bucket of one feature's usage.

    Deduplication follows the proven `dedup-by-request_id, MAX-per-category`
    recipe (`docs/analysis/actual-usage-by-request-2026-07-26.md`): within a
    `request_id` group every category is IDENTICAL except `output_tokens`
    (early rows are partial streaming snapshots), so MAX is correct and safe
    uniformly across all four categories -- never a sum of raw records, which
    over-counts by ~2x on this exact event shape (one row per assistant
    transcript entry, not per API request).
    """

    stage: str | None
    request_count: int
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    unattributed_record_count: int
    """Records in this stage bucket carrying NO `request_id` -- cannot be
    deduped, so their tokens are EXCLUDED from the totals above rather than
    summed in raw (which would silently reintroduce the over-count the
    dedup exists to remove). Counted here so the gap is visible, never
    silently dropped (GDP-8 arity)."""


@dataclass(frozen=True)
class AgentUsageByFeatureReport:
    """`AGENT_USAGE_OBSERVED` records for one `feature_id`, grouped by stage."""

    feature_id: str
    stages: tuple[AgentUsageStageAggregate, ...] = field(default_factory=tuple)
    total_records_scanned: int = 0
    """Every AGENT_USAGE_OBSERVED record matching `feature_id`, before any
    dedup/grouping split -- `0` is the honest, computed fact "no record
    named this feature_id" (never a guess), distinct from "records exist but
    none attributed cleanly". The caller renders `0` as could-not-verify."""

    unreadable_file_count: int = 0
    """Log files this scan could not read at all (OSError/PermissionError).

    Their records are absent from every total above, so a non-zero value means
    the totals are a LOWER BOUND, never the measured truth. Before 2026-08-06
    these files were skipped with a bare `continue`: a corpus whose logs were
    unreadable reported byte-identically to a corpus that genuinely held no
    matching event, which is the silent-wrong GDP-6 forbids and the exact claim
    the capture spec requires -- "capture failures are distinguishable from
    genuine zero eligible events". A probe with three corpora (genuinely empty /
    one unreadable file holding 3 events / 3 corrupt records) returned the same
    report for all three; see `tests/des/unit/adapters/
    test_agent_usage_capture_failure_is_not_zero.py`."""

    undecodable_line_count: int = 0
    """Lines that were read but were not valid JSON, for the same reason.

    Counted separately from `unreadable_file_count` because they fail at a
    different boundary and a caller may reasonably treat them differently: a
    whole missing file is a capture outage, a scattering of corrupt lines is a
    writer defect."""

    @property
    def capture_is_complete(self) -> bool:
        """True only when nothing was lost on the way in.

        Ask THIS before reading a total as a measurement. A `False` here turns
        every figure in this report into a lower bound."""
        return self.unreadable_file_count == 0 and self.undecodable_line_count == 0


class JsonlAuditLogReader(AuditLogReader):
    """Reads audit events from JSONL files.

    Scans today's log file backward to find the most recent matching entry,
    falling back to yesterday's (UTC) file when today's has no match -- a
    write just before UTC midnight and a read just after must not be missed
    just because the two land in different date-rotated files.
    Uses shared AuditLogPathResolver for consistent path resolution with writer.
    """

    def __init__(
        self, log_dir: str | Path | None = None, cwd: str | Path | None = None
    ) -> None:
        resolved = AuditLogPathResolver(log_dir=log_dir, cwd=cwd).resolve()
        self._log_dir = resolved

    def read_last_entry(
        self,
        event_type: str | None = None,
        feature_name: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Read the most recent audit entry matching the given filters.

        Scans today's log file from end to start for efficiency, falling back
        to yesterday's file when today's has no match (or does not exist yet).
        The writer and reader rotate independently on UTC-date, so a write
        just before UTC midnight and a read just after would otherwise land
        in different files and the entry would be missed (GDP-6: a miss must
        not be indistinguishable from "nothing happened").

        Returns:
            Most recent matching entry as dict, or None if not found in
            either of today's or yesterday's log file.
        """
        for log_file in self._candidate_log_files():
            entry = self._last_matching_entry_in(
                log_file, event_type, feature_name, step_id
            )
            if entry is not None:
                return entry
        return None

    def _last_matching_entry_in(
        self,
        log_file: Path | None,
        event_type: str | None,
        feature_name: str | None,
        step_id: str | None,
    ) -> dict[str, Any] | None:
        """Scan a single log file backward for the most recent match, else None."""
        if log_file is None or not log_file.exists():
            return None

        try:
            lines = log_file.read_text().strip().splitlines()
        except (OSError, PermissionError):
            return None

        # Scan backward for most recent match
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if self._matches(entry, event_type, feature_name, step_id):
                return entry

        return None

    def _matches(
        self,
        entry: dict,
        event_type: str | None,
        feature_name: str | None,
        step_id: str | None,
    ) -> bool:
        """Check if entry matches all provided filters."""
        if event_type and entry.get("event") != event_type:
            return False
        if feature_name and entry.get("feature_name") != feature_name:
            return False
        return not (step_id and entry.get("step_id") != step_id)

    def _candidate_log_files(self) -> list[Path]:
        """Today's and yesterday's (UTC) log file paths, most-recent first.

        Returns an empty list if the log directory does not exist. Neither
        candidate is checked for existence here -- that is
        `_last_matching_entry_in`'s job, kept a single responsibility.
        """
        if not self._log_dir.exists():
            return []
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return [
            self._log_dir / f"audit-{today}.log",
            self._log_dir / f"audit-{yesterday}.log",
        ]

    def aggregate_agent_usage_by_stage(
        self, feature_id: str
    ) -> AgentUsageByFeatureReport:
        """Deduped `AGENT_USAGE_OBSERVED` token totals for `feature_id`, by stage.

        declared-facts-reachable-recorded DD-12 (slice-07): the reader closing
        the "0 readers" state F1 named. Scans EVERY `audit-*.log` file in the
        log directory (not just today/yesterday -- a feature's work can span
        several days), unlike `read_last_entry`'s 2-day window, because an
        aggregate over a feature's lifetime must not silently miss its own
        earlier days.

        Join key: `feature_id` (also matches `feature_name`, which the writer
        always sets to the same value -- see `_to_audit_event`). Dedup key:
        `request_id`, MAX per category (see `AgentUsageStageAggregate`).
        """
        stage_groups: dict[str | None, dict[str, dict[str, int]]] = {}
        unattributed_by_stage: dict[str | None, int] = {}
        total_scanned = 0
        unreadable_files = 0
        undecodable_lines = 0

        for log_file in sorted(self._log_dir.glob("audit-*.log")):
            try:
                lines = log_file.read_text(encoding="utf-8").splitlines()
            except (OSError, PermissionError):
                # NOT a bare skip: a file we could not read is a capture
                # failure, and its records are missing from every total below.
                unreadable_files += 1
                continue
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    undecodable_lines += 1
                    continue
                if entry.get("event") != _AGENT_USAGE_EVENT:
                    continue
                if (
                    entry.get("feature_id") != feature_id
                    and entry.get("feature_name") != feature_id
                ):
                    continue
                total_scanned += 1
                stage = entry.get("stage")
                request_id = entry.get("request_id")
                if not isinstance(request_id, str) or not request_id:
                    unattributed_by_stage[stage] = (
                        unattributed_by_stage.get(stage, 0) + 1
                    )
                    continue
                requests = stage_groups.setdefault(stage, {})
                group = requests.setdefault(request_id, dict.fromkeys(_USAGE_FIELDS, 0))
                for f in _USAGE_FIELDS:
                    value = entry.get(f)
                    if isinstance(value, int):
                        group[f] = max(group[f], value)

        all_stages = set(stage_groups) | set(unattributed_by_stage)
        stages = tuple(
            AgentUsageStageAggregate(
                stage=stage,
                request_count=len(stage_groups.get(stage, {})),
                input_tokens=sum(
                    g["input_tokens"] for g in stage_groups.get(stage, {}).values()
                ),
                cache_creation_input_tokens=sum(
                    g["cache_creation_input_tokens"]
                    for g in stage_groups.get(stage, {}).values()
                ),
                cache_read_input_tokens=sum(
                    g["cache_read_input_tokens"]
                    for g in stage_groups.get(stage, {}).values()
                ),
                output_tokens=sum(
                    g["output_tokens"] for g in stage_groups.get(stage, {}).values()
                ),
                unattributed_record_count=unattributed_by_stage.get(stage, 0),
            )
            for stage in sorted(all_stages, key=lambda s: (s is None, s))
        )
        return AgentUsageByFeatureReport(
            feature_id=feature_id,
            stages=stages,
            total_records_scanned=total_scanned,
            unreadable_file_count=unreadable_files,
            undecodable_line_count=undecodable_lines,
        )
