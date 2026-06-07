"""
StaleExecutionDetector Application Service

LAYER: Application Layer (Hexagonal Architecture)

BUSINESS PURPOSE:
Scans the steps directory for IN_PROGRESS phases that exceed a configurable
staleness threshold, returning a StaleDetectionResult.

CONFIGURATION:
- Default threshold: 30 minutes
- Environment variable: DES_STALE_THRESHOLD_MINUTES

DEPENDENCIES:
- Domain: StaleExecution (value object)
- Domain: StaleDetectionResult (entity)
- Infrastructure: File system (pure file scanning, no DB/HTTP)

USAGE:
    detector = StaleExecutionDetector(project_root=Path("/path/to/project"))
    result = detector.scan_for_stale_executions()

    if result.is_blocked:
        print(result.alert_message)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from des.domain.stale_detection_result import StaleDetectionResult
from des.domain.stale_execution import StaleExecution
from des.domain.value_objects import PhaseStatus


class StaleExecutionDetector:
    """
    Application service for detecting stale executions in steps directory.

    Scans all .json files in steps/ directory, identifies IN_PROGRESS phases,
    and flags those exceeding the staleness threshold.

    Attributes:
        project_root: Path to project root directory
        threshold_minutes: Staleness threshold in minutes (default 30)
        uses_external_services: False (pure file scanning, no DB/HTTP)
        is_session_scoped: True (no daemon, terminates with session)
    """

    def __init__(self, project_root: Path):
        """
        Initialize StaleExecutionDetector with project root.

        Args:
            project_root: Path to project root directory

        Configuration:
            Reads DES_STALE_THRESHOLD_MINUTES environment variable.
            Defaults to 30 minutes if not set or invalid.
            Validates that threshold is a positive integer.
        """
        self.project_root = Path(project_root)

        env_value = os.environ.get("DES_STALE_THRESHOLD_MINUTES", "30")
        try:
            threshold = int(env_value)
            if threshold <= 0:
                threshold = 30
        except ValueError:
            threshold = 30

        self.threshold_minutes = threshold
        self.uses_external_services = False
        self.is_session_scoped = True

    def scan_for_stale_executions(self) -> StaleDetectionResult:
        """
        Scan steps directory for stale IN_PROGRESS phases.

        Returns:
            StaleDetectionResult with list of detected stale executions

        Business Logic:
            1. Find all .json files in steps/ directory
            2. For each file, load JSON and check for IN_PROGRESS phases
            3. Calculate age of each IN_PROGRESS phase
            4. Flag phases exceeding threshold as stale
            5. Return StaleDetectionResult with aggregated results

        Error Handling:
            - Missing steps directory: returns empty result
            - Corrupted JSON files: skips file, continues scan
            - Missing fields: skips phase, continues scan
        """
        stale_executions = []
        warnings = []

        steps_dir = self.project_root / "steps"

        if not steps_dir.exists():
            return StaleDetectionResult(stale_executions=[], warnings=[])

        for step_file in steps_dir.glob("*.json"):
            try:
                stale_execution = self._check_step_file_for_staleness(step_file)
                if stale_execution:
                    stale_executions.append(stale_execution)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                warnings.append(
                    {"file_path": f"steps/{step_file.name}", "error": str(e)}
                )
                continue

        return StaleDetectionResult(
            stale_executions=stale_executions, warnings=warnings
        )

    def _check_step_file_for_staleness(self, step_file: Path) -> StaleExecution | None:
        """
        Check a single step file for stale IN_PROGRESS phases.

        Args:
            step_file: Path to step file to check

        Returns:
            StaleExecution if stale phase found, None otherwise

        Raises:
            json.JSONDecodeError: If file contains invalid JSON
            KeyError: If required fields are missing
            ValueError: If timestamp parsing fails
        """
        step_data = json.loads(step_file.read_text())

        if step_data.get("state", {}).get("status") != PhaseStatus.IN_PROGRESS:
            return None

        tdd_cycle = step_data.get("tdd_cycle")
        if not tdd_cycle:
            return None

        phase_execution_log = tdd_cycle.get("phase_execution_log", [])

        for phase in phase_execution_log:
            if phase.get("status") == PhaseStatus.IN_PROGRESS:
                started_at = phase.get("started_at")
                if not started_at:
                    continue

                age_minutes = self._calculate_age_minutes(started_at)

                if age_minutes > self.threshold_minutes:
                    return StaleExecution(
                        step_file=f"steps/{step_file.name}",
                        phase_name=phase.get("phase_name", "UNKNOWN"),
                        age_minutes=age_minutes,
                        started_at=started_at,
                    )

        return None

    def _calculate_age_minutes(self, started_at: str) -> int:
        """
        Calculate age in minutes from ISO 8601 timestamp to now.

        Args:
            started_at: ISO 8601 timestamp string

        Returns:
            Age in minutes (integer)

        Raises:
            ValueError: If timestamp cannot be parsed
        """
        started_datetime = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if started_datetime.tzinfo is None:
            started_datetime = started_datetime.replace(tzinfo=timezone.utc)
        age_delta = datetime.now(timezone.utc) - started_datetime
        return int(age_delta.total_seconds() / 60)
