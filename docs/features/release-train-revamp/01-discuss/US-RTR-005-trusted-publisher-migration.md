# US-RTR-005: Migrate PyPI Publishing to Trusted Publishers (OIDC)

## Problem (The Pain)
Mike is the nwave-dev maintainer responsible for PyPI publishing security.
He finds the current API token approach risky: the `PYPI_TOKEN` secret stored in GitHub has no expiration date, and if compromised gives indefinite upload access to the nwave-ai package on PyPI. Rotating the token requires manual steps in both PyPI and GitHub Secrets.

## Who (The User)
- Mike, maintaining publishing security for the nwave-ai package
- CI/CD system, authenticating to PyPI during publish steps
- PyPI (as a service), validating upload credentials

## Solution (What We Build)
Configure Trusted Publisher (OIDC) in PyPI project settings for the nwave-ai package, linking the specific GitHub repository and workflow files. Replace `TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}` with the `pypa/gh-action-pypi-publish` action that acquires short-lived OIDC tokens automatically. Remove the stored `PYPI_TOKEN` secret after migration.

## Domain Examples

### Example 1: RC publish with OIDC
Mike triggers an RC release. The `_reusable-publish-pypi.yml` workflow declares `permissions: id-token: write`. The `pypa/gh-action-pypi-publish` action contacts PyPI's OIDC endpoint, presents the GitHub Actions JWT, receives a 15-minute token, uploads `nwave-ai==1.1.22rc1`, and the token expires. No stored secret was used.

### Example 2: Unauthorized workflow blocked
A contributor opens a PR that modifies the publish workflow to point to a different PyPI project. When the workflow runs, PyPI's Trusted Publisher check fails because the OIDC claims (repository, workflow file, environment) do not match the configured publisher. The upload is rejected.

### Example 3: Stable publish to PyPI
Mike triggers a stable release. The publish job runs in the `pypi` GitHub environment, which provides additional approval gates. OIDC authentication succeeds, `nwave-ai==1.1.22` is uploaded as stable. The 15-minute token expires, and there is a full audit trail in PyPI's security log.

## UAT Scenarios (BDD)

### Scenario: OIDC publish succeeds
Given Trusted Publisher is configured for nwave-ai on PyPI
And the workflow has "permissions: id-token: write"
When the publish step runs for "nwave-ai==1.1.22rc1"
Then the package is uploaded to PyPI
And no stored API token was used
And the OIDC token expires within 15 minutes

### Scenario: Separate build and publish jobs
Given the publish workflow has build and publish as separate jobs
When the build job completes
Then artifacts are uploaded via actions/upload-artifact
And the publish job downloads artifacts and publishes
And only the publish job has "id-token: write" permission

### Scenario: GitHub environment provides approval gate
Given the publish job uses the "pypi" GitHub environment
When the stable release publish runs
Then environment protection rules apply
And the publish appears in the environment's deployment history

### Scenario: Fallback path documented
Given OIDC authentication fails unexpectedly
When the publish step errors
Then the error message indicates "Trusted Publisher not configured"
And the documentation describes how to temporarily fall back to API token

## Acceptance Criteria
- [ ] Trusted Publisher configured in PyPI project settings for nwave-ai
- [ ] Publish workflow uses `pypa/gh-action-pypi-publish` with OIDC (no stored tokens)
- [ ] Build and publish are separate jobs (security: minimize OIDC token scope)
- [ ] `permissions: id-token: write` only on publish job
- [ ] GitHub environments "testpypi" and "pypi" created with appropriate protection rules
- [ ] Stored `PYPI_TOKEN` secret removed after successful migration
- [ ] Works for both TestPyPI (dev smoke test) and production PyPI (RC + stable)

## Technical Notes
- PyPI Trusted Publisher setup: PyPI project settings -> Publishing -> Add a new publisher
- Configure: repository owner, repository name, workflow filename, environment name
- TestPyPI and PyPI require separate Trusted Publisher configurations
- The `pypa/gh-action-pypi-publish@release/v1` action handles OIDC automatically
- Must configure for each workflow that publishes: release-dev (TestPyPI), release-rc (PyPI), release-prod (PyPI)
- Dependency: US-RTR-004 (modular workflows must exist with correct filenames for OIDC claim matching)
