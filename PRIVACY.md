# Privacy Policy

**Last updated**: 2026-09-26

nWave is an open-source AI workflow framework that runs inside [Claude Code](https://claude.com/product/claude-code) and stores all data locally on your machine. This privacy policy explains what data nWave handles and how.

## No User Data Collection

nWave collects no analytics, telemetry, tracking or usage reports. Workflow artifacts are stored locally. Explicitly authorized external-service calls, described below, send only the permitted request data.

## Local-Only Storage

Workflow artifacts are stored on your machine:

| Data | Location | Purpose |
|------|----------|---------|
| DES audit logs | `~/.nwave/des/` | TDD phase compliance records |
| Execution logs | `docs/feature/{project}/execution-log.json` | Per-feature delivery tracking |
| Skill loading log | `~/.nwave/des/skill-loading.log` | Debug log for skill file loading |
| Configuration | `~/.nwave/des-config.json` | Rigor profile and settings |

nWave does not automatically upload these files. An explicitly authorized Jev question can include a minimal permitted excerpt; authorization is not permission to upload a repository or log dump. You can delete local artifacts at any time.

## Outbound Network Calls

nWave can make an **optional update check** on session start to notify you of available updates:

- `https://pypi.org/pypi/nwave-ai/json` — checks latest PyPI version
- `https://api.github.com/repos/nWave-ai/nWave/releases/latest` — checks latest GitHub release

**What is sent**: a standard HTTPS GET request with no user-identifiable information. These requests are anonymous and unauthenticated. If they fail (network unavailable, rate limit), nWave silently continues without blocking your session.
**What is not sent**: no user data, no machine identifiers, no usage statistics.

You can disable this check entirely by setting `update_check.frequency` to `"never"` in `~/.nwave/des-config.json`:

```json
{
  "update_check": {
    "frequency": "never"
  }
}
```

## No Third-Party Data Sharing

nWave operates no collection server. Your coding host handles its AI-provider communication. If you explicitly authorize Jev, its request is sent to TypeSafe as described below; this is external processing, not local-only computation.

## Optional Jev External Processing

Jev is a remote service at `https://api.typesafe.ai/v1/systemone`. The local
client sends the caller-supplied `state`, model and typed questions over HTTPS,
with the configured API credential in the authorization header. Results and
request records remain local unless you separately authorize sharing them.

An explicit user instruction or persistent service enablement authorizes calls
within the stated data scope. Having `TYPESAFE_API_KEY` alone does not establish
that authorization. Once authorized and available, supported semantic questions
use Jev under the shared skill; no repeated permission is needed for that scope.

Send minimal permitted task summaries or excerpts. Do not transmit secrets,
personal data, hidden review material or unapproved private third-party content.
Independent reviewers own their questions and must not inherit producer-owned
classifications. Source-blind EXAMINE retains its current isolated-access limit.
Service failures are explicit and local work can continue without invented
results. nWave makes no claim here about the remote provider's retention policy.

To stop Jev use, revoke its authorization in your working instructions or remove
the credential. This does not disable the rest of nWave.

## Does nWave See My Code?

Yes — like any Claude Code extension, nWave agents can read and analyze files in your project when you ask them to work on it. This happens entirely within your local Claude Code session. nWave does not automatically upload your code. Jev source excerpts require actual authorization within the permitted data scope. Your prompts and code are subject to [Anthropic's privacy policy](https://www.anthropic.com/privacy).

## Open Source

nWave is MIT licensed. The complete source code is available at [github.com/nWave-ai/nWave](https://github.com/nWave-ai/nWave) for audit and verification.

## Contact

Questions about this privacy policy: [hello@nwave.ai](mailto:hello@nwave.ai)
