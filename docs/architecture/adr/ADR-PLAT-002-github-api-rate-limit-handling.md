# ADR-PLAT-002: GitHub API Rate Limit Handling

## Status

**Accepted**

## Context

The versioning and release management feature requires querying the GitHub API for:

1. **Latest release information** (`/nw:version` and `/nw:update`)
2. **Release asset URLs** (`/nw:update`)
3. **Release checksums** (`/nw:update`)

GitHub API has rate limits:

| API Type | Unauthenticated | Authenticated |
|----------|-----------------|---------------|
| REST API | 60 requests/hour | 5,000 requests/hour |
| Per IP address | Yes | Per token |

### The Problem

Users running `/nw:version` frequently could hit rate limits, especially:
- CI/CD pipelines checking versions
- Multiple users behind same corporate NAT
- Automated scripts

### Mike's Decision

**Graceful offline fallback by default; if user has `gh` CLI with auth, use the token for GitHub API calls to bypass rate limits.**

## Decision

**Implement a tiered authentication strategy with graceful degradation.**

### Authentication Tiers

| Tier | Detection | Rate Limit | Use Case |
|------|-----------|------------|----------|
| **1. gh CLI token** | `gh auth token` | 5,000/hour | Power users with gh installed |
| **2. GITHUB_TOKEN env** | Environment variable | 5,000/hour | CI/CD environments |
| **3. Unauthenticated** | Default | 60/hour | Casual users |

### Fallback Strategy

When rate limited or offline:

| Condition | Behavior |
|-----------|----------|
| Rate limited | Use cached watermark, warn user |
| Network unreachable | Use cached watermark, show "(Unable to check)" |
| No cache available | Show local version only |

## Implementation

### Token Resolution Order

```python
def get_github_token() -> Optional[str]:
    """Resolve GitHub token with fallback chain."""

    # Tier 1: gh CLI token
    token = get_gh_cli_token()
    if token:
        return token

    # Tier 2: Environment variable
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        return token

    # Tier 3: Unauthenticated
    return None

def get_gh_cli_token() -> Optional[str]:
    """Extract token from gh CLI if available and authenticated."""
    try:
        result = subprocess.run(
            ['gh', 'auth', 'token'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
```

### API Request with Rate Limit Handling

```python
import requests
from typing import Optional

def github_api_request(endpoint: str, token: Optional[str] = None) -> dict:
    """Make GitHub API request with rate limit handling."""
    headers = {'Accept': 'application/vnd.github.v3+json'}

    if token:
        headers['Authorization'] = f'token {token}'

    response = requests.get(
        f'https://api.github.com{endpoint}',
        headers=headers,
        timeout=10
    )

    # Check rate limit headers
    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    if response.status_code == 403 and remaining == 0:
        raise RateLimitError(reset_time)

    response.raise_for_status()
    return response.json()
```

### Graceful Degradation

```python
def check_latest_version(watermark: Watermark) -> VersionCheckResult:
    """Check latest version with graceful fallback."""

    try:
        token = get_github_token()
        release_info = github_api_request('/repos/owner/repo/releases/latest', token)
        latest_version = release_info['tag_name'].lstrip('v')

        # Update watermark on success
        watermark.update(latest_version)

        return VersionCheckResult(
            latest_version=latest_version,
            source='github_api'
        )

    except RateLimitError as e:
        # Use cached version from watermark
        if watermark.latest_version:
            return VersionCheckResult(
                latest_version=watermark.latest_version,
                source='watermark_cache',
                warning=f"Rate limited. Using cached version. Resets in {e.minutes_until_reset} minutes."
            )
        return VersionCheckResult(
            latest_version=None,
            source='rate_limited',
            warning="Rate limited. Unable to check for updates."
        )

    except requests.RequestException:
        # Network error - use cache
        if watermark.latest_version:
            return VersionCheckResult(
                latest_version=watermark.latest_version,
                source='watermark_cache'
            )
        return VersionCheckResult(
            latest_version=None,
            source='offline',
            message="Unable to check for updates"
        )
```

## Consequences

### Positive

1. **Zero configuration for most users**: Works without any setup
2. **Power user optimization**: gh CLI users get full rate limit
3. **CI/CD compatibility**: GITHUB_TOKEN works automatically
4. **Graceful degradation**: Never fails hard on rate limit
5. **Privacy respecting**: No forced authentication

### Negative

1. **gh CLI dependency**: Optional but provides best experience
2. **Cached data staleness**: May show outdated version if rate limited
3. **Complexity**: Three-tier strategy has more code paths

### Neutral

1. **Watermark freshness**: 24-hour staleness threshold balances API calls vs freshness
2. **User awareness**: Rate limit warning informs but doesn't block

## Rate Limit Scenarios

### Scenario 1: Casual User (Unauthenticated)

```
$ /nw:version
nWave v1.2.3 (up to date)

[Later, after 60 checks in an hour]
$ /nw:version
nWave v1.2.3 (using cached check from 2 hours ago)
```

### Scenario 2: Power User with gh CLI

```
$ gh auth status
Logged in to github.com as username

$ /nw:version
nWave v1.2.3 (update available: v1.3.0)
```

### Scenario 3: CI/CD Pipeline

```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

steps:
  - run: /nw:version  # Uses GITHUB_TOKEN automatically
```

### Scenario 4: Offline User

```
$ /nw:version
nWave v1.2.3 (Unable to check for updates)
```

## Security Considerations

1. **Token handling**: Never logged, never stored beyond process lifetime
2. **gh CLI trust**: We trust gh CLI's token management
3. **No token prompting**: Never ask user to paste tokens
4. **Environment variable**: Standard GitHub Actions pattern

## Alternatives Considered

### Alternative 1: Always Require Authentication

Force users to configure a GitHub token.

**Rejected because**: User friction, privacy concerns, not needed for basic use.

### Alternative 2: No Rate Limit Handling

Let API calls fail when rate limited.

**Rejected because**: Poor UX, users can't check version when they need to.

### Alternative 3: Own Backend Service

Proxy GitHub API through our own service.

**Rejected because**: Adds infrastructure, privacy concerns, single point of failure.

## References

- GitHub API Rate Limits: https://docs.github.com/en/rest/rate-limit
- GitHub CLI: https://cli.github.com/
- GITHUB_TOKEN in Actions: https://docs.github.com/en/actions/security-guides/automatic-token-authentication

## Decision Record

| Field | Value |
|-------|-------|
| Decision | ADR-PLAT-002 |
| Date | 2026-01-28 |
| Author | Apex (platform-architect) |
| Status | Accepted |
| Deciders | Mike (stakeholder) |
