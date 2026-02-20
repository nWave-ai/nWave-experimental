"""Tests for scripts/release/ci_gate.py

CI gate queries the GitHub Check Runs API for a given commit SHA
and returns one of four statuses: green, failed, pending, none.
Exit codes: 0=green, 1=failed, 2=pending, 3=none, 4=API error.

BDD scenario mapping:
  - journey-dev-release.feature: "CI failed on commit prevents tagging" (Scenario 4)
  - journey-dev-release.feature: "CI still running on commit prevents tagging" (Scenario 5)
  - journey-dev-release.feature: "No CI run found on commit prevents tagging" (Scenario 6)
  - journey-rc-release.feature: CI gate scenarios (Scenarios 5-7)
  - journey-stable-release.feature: CI gate scenarios (Scenarios 6-8)
  - All three stages share the same 4-state CI gate logic.
"""

import json
from unittest.mock import patch

import httpx

from scripts.release.ci_gate import evaluate_check_runs, fetch_check_runs
from tests.release.conftest import SAMPLE_REPO, SAMPLE_SHA


# ---------------------------------------------------------------------------
# NOTE: Tests are enabled one at a time as ci_gate.py is implemented.
# ---------------------------------------------------------------------------


class TestCIGateAllGreen:
    """CI gate returns 'green' when all check-runs have conclusion=success."""

    def test_all_checks_passed_returns_green(self, all_green_response):
        """Given all check-runs on a commit are green,
        when the CI gate evaluates the commit,
        then the status is 'green' and exit code is 0.

        Maps to: Happy path CI step in all three stage features.
        """
        result = evaluate_check_runs(all_green_response, SAMPLE_SHA)

        assert result["status"] == "green"
        assert result["exit_code"] == 0

    def test_green_status_message_is_human_readable(self, all_green_response):
        """The 'green' result includes a descriptive message like
        'All 3 check-runs passed on abc123d'.
        """
        result = evaluate_check_runs(all_green_response, SAMPLE_SHA)

        assert result["message"] == f"All 3 check-runs passed on {SAMPLE_SHA[:7]}"


class TestCIGateFailed:
    """CI gate returns 'failed' when any check-run has conclusion=failure."""

    def test_one_failed_check_returns_failed(self, one_failed_response):
        """Given one check-run on a commit has failed,
        when the CI gate evaluates the commit,
        then the status is 'failed' and exit code is 1.

        Maps to: "CI failed on commit prevents tagging" in all stage features.
        """
        result = evaluate_check_runs(one_failed_response, SAMPLE_SHA)

        assert result["status"] == "failed"
        assert result["exit_code"] == 1

    def test_failed_message_names_failing_checks(self, one_failed_response):
        """The 'failed' result message includes the name(s) of the failed check-run(s).
        Example: 'CI failed on abc123d: CI Pipeline'.
        """
        result = evaluate_check_runs(one_failed_response, SAMPLE_SHA)

        assert result["message"] == f"CI failed on {SAMPLE_SHA[:7]}: CI Pipeline"


class TestCIGatePending:
    """CI gate returns 'pending' when any check-run has status=in_progress."""

    def test_pending_check_returns_pending(self, one_pending_response):
        """Given a check-run is still in progress,
        when the CI gate evaluates the commit,
        then the status is 'pending' and exit code is 2.

        Maps to: "CI still running on commit prevents tagging" in all stage features.
        """
        result = evaluate_check_runs(one_pending_response, SAMPLE_SHA)

        assert result["status"] == "pending"
        assert result["exit_code"] == 2

    def test_pending_message_suggests_retry(self, one_pending_response):
        """The 'pending' result message tells the user to retry later.
        Example: 'CI still running on abc123d, retry later'.
        """
        result = evaluate_check_runs(one_pending_response, SAMPLE_SHA)

        assert result["message"] == f"CI still running on {SAMPLE_SHA[:7]}, retry later"


class TestCIGateNone:
    """CI gate returns 'none' when no check-runs exist for the commit."""

    def test_no_check_runs_returns_none(self, no_check_runs_response):
        """Given no check-runs are registered for a commit,
        when the CI gate evaluates the commit,
        then the status is 'none' and exit code is 3.

        Maps to: "No CI run found on commit prevents tagging" in all stage features.
        """
        result = evaluate_check_runs(no_check_runs_response, SAMPLE_SHA)

        assert result["status"] == "none"
        assert result["exit_code"] == 3

    def test_none_message_suggests_push_first(self, no_check_runs_response):
        """The 'none' result message tells the user to push a commit to trigger CI.
        Example: 'No CI run found for abc123d. Push to trigger CI first.'.
        """
        result = evaluate_check_runs(no_check_runs_response, SAMPLE_SHA)

        assert (
            result["message"]
            == f"No CI run found for {SAMPLE_SHA[:7]}. Push to trigger CI first."
        )


class TestCIGateSelfExclusion:
    """CI gate excludes the calling workflow's own check-run from evaluation."""

    def test_calling_workflow_excluded_from_results(self, self_referencing_response):
        """Given the check-runs include the calling workflow (e.g. 'release-dev'),
        when the CI gate evaluates with --exclude-self 'release-dev',
        then only 'CI Pipeline' is evaluated, and status is 'green'.
        """
        result = evaluate_check_runs(
            self_referencing_response, SAMPLE_SHA, self_workflow="release-dev"
        )

        assert result["status"] == "green"
        assert len(result["details"]) == 1
        assert result["details"][0]["name"] == "CI Pipeline"


class TestCIGateAPIError:
    """CI gate handles GitHub API errors gracefully."""

    def test_api_401_returns_error_with_token_hint(self):
        """Given the GitHub API returns 401 Unauthorized,
        when the CI gate queries the API,
        then exit code is 4 and message mentions 'Check GH_TOKEN permissions'.
        """
        mock_response = httpx.Response(
            status_code=401,
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        with patch("scripts.release.ci_gate.httpx.get", return_value=mock_response):
            result = fetch_check_runs(SAMPLE_REPO, SAMPLE_SHA, token="bad-token")

        assert result["exit_code"] == 4
        assert "GH_TOKEN" in result["message"]

    def test_api_500_returns_error(self):
        """Given the GitHub API returns 500,
        when the CI gate queries the API,
        then exit code is 4 and message includes the HTTP status code.
        """
        mock_response = httpx.Response(
            status_code=500,
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        with patch("scripts.release.ci_gate.httpx.get", return_value=mock_response):
            result = fetch_check_runs(SAMPLE_REPO, SAMPLE_SHA, token="tok")

        assert result["exit_code"] == 4
        assert "500" in result["message"]

    def test_network_timeout_returns_error(self):
        """Given the GitHub API request times out,
        when the CI gate queries the API,
        then exit code is 4 and message indicates a connection error.
        """
        with patch(
            "scripts.release.ci_gate.httpx.get",
            side_effect=httpx.ConnectTimeout("Connection timed out"),
        ):
            result = fetch_check_runs(SAMPLE_REPO, SAMPLE_SHA, token="tok")

        assert result["exit_code"] == 4
        assert "connection" in result["message"].lower()


class TestCIGateOutputFormat:
    """CI gate always outputs well-formed JSON to stdout."""

    def test_output_is_valid_json(self, all_green_response):
        """The output must parse as valid JSON with keys:
        'status', 'message', 'details'.
        """
        result = evaluate_check_runs(all_green_response, SAMPLE_SHA)

        # Result must be JSON-serializable
        output = json.dumps(result)
        parsed = json.loads(output)

        assert "status" in parsed
        assert "message" in parsed
        assert "details" in parsed

    def test_details_contains_check_run_names(self, all_green_response):
        """The 'details' field lists individual check-run names and their conclusions."""
        result = evaluate_check_runs(all_green_response, SAMPLE_SHA)

        names = [d["name"] for d in result["details"]]
        assert names == ["CI Pipeline", "Lint", "Type Check"]
        assert all(d["conclusion"] == "success" for d in result["details"])
