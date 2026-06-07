"""Unit tests for measure_adoption.py KPI script.

Tests validate report generation through the driving port
(generate_report) and assert at output boundary (markdown string).

Test Budget: 3 behaviors x 2 = 6 max. Using 3 tests.

Behaviors tested:
1. Report generation with mock API data -> valid markdown
2. Empty results (0 commits) -> baseline report
3. Adoption ratio calculation -> math correct
"""

import json
from unittest.mock import patch

import pytest

from scripts.framework.measure_adoption import (
    calculate_adoption_metrics,
    generate_report,
)


class TestMeasureAdoption:
    """Tests for KPI measurement script."""

    def test_report_generation(self) -> None:
        """Mock subprocess + HTTP -> valid markdown report."""
        github_response = json.dumps(
            {
                "total_count": 42,
                "items": [{"sha": f"abc{i}"} for i in range(42)],
            }
        ).encode()

        pypi_response = json.dumps(
            {
                "data": {
                    "last_day": 10,
                    "last_week": 75,
                    "last_month": 300,
                },
                "type": "recent_downloads",
                "package": "nwave-ai",
            }
        ).encode()

        with patch("scripts.framework.measure_adoption._fetch_url") as mock_fetch:
            mock_fetch.side_effect = [github_response, pypi_response]
            report = generate_report()

        # Structural validation
        assert report.startswith("# nWave Adoption Report")
        lines = report.splitlines()
        # Must have a table with metrics
        table_lines = [line for line in lines if "|" in line]
        assert len(table_lines) >= 3  # header + separator + data
        # Must contain the actual metric values from mock data
        assert any("42" in line and "commit" in line.lower() for line in lines)
        assert any("300" in line for line in lines)

    def test_empty_results(self) -> None:
        """0 commits, 0 downloads -> baseline report with zeros."""
        github_response = json.dumps(
            {
                "total_count": 0,
                "items": [],
            }
        ).encode()

        pypi_response = json.dumps(
            {
                "data": {
                    "last_day": 0,
                    "last_week": 0,
                    "last_month": 0,
                },
                "type": "recent_downloads",
                "package": "nwave-ai",
            }
        ).encode()

        with patch("scripts.framework.measure_adoption._fetch_url") as mock_fetch:
            mock_fetch.side_effect = [github_response, pypi_response]
            report = generate_report()

        assert "# nWave Adoption Report" in report
        assert "0" in report

    def test_adoption_ratio_calculation(self) -> None:
        """Adoption ratio represents commits as fraction of total installs."""
        metrics = calculate_adoption_metrics(commit_count=100, monthly_downloads=400)

        assert 0 < metrics["adoption_ratio"] <= 1.0  # ratio is a fraction
        assert metrics["adoption_ratio"] == pytest.approx(0.25, abs=0.01)
        assert metrics["commit_count"] == 100
        assert metrics["monthly_downloads"] == 400

    def test_adoption_ratio_zero_downloads(self) -> None:
        """Zero downloads produces zero ratio without division error."""
        metrics = calculate_adoption_metrics(commit_count=10, monthly_downloads=0)

        assert metrics["adoption_ratio"] == 0.0
        assert "commit_count" in metrics
        assert "monthly_downloads" in metrics
