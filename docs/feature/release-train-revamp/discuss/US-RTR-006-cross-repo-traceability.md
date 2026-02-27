# US-RTR-006: Cross-Repo Traceability

## Problem (The Pain)
Mike is the nwave-dev maintainer who debugs issues reported against the public nwave-ai package.
He finds it time-consuming to trace a public release back to its source: the current commit message in nWave public (`chore(release): v1.1.21`) contains no reference to the source commit SHA, the dev tag, or the pipeline run that produced it. He has to manually cross-reference tags across three repositories to find the origin.

## Who (The User)
- Mike, debugging a reported issue and needing to find the exact source commit
- Mike, auditing that a public release came from a legitimate pipeline run
- Future maintainers who need to understand the release provenance

## Solution (What We Build)
Enhance the cross-repo commit messages to include a full traceability chain: source commit SHA, dev tag, RC tag, and pipeline run URL. Create a reverse-lookup marker tag on nwave-dev (`vX.Y.Z`) that enables tracing from any public version back to the dev commit in a single query.

## Domain Examples

### Example 1: Tracing forward (dev to public)
Mike tagged `v1.1.22.dev3` on nwave-dev at commit abc123d. He promoted it to `v1.1.22rc1`, then to stable `v1.1.22`. The nWave public repo's commit for v1.1.22 reads:
```
chore(release): v1.1.22

Source: nwave-dev@abc123def456789
Dev tag: v1.1.22.dev3
RC tag: v1.1.22rc1
Stable tag: v1.1.22
Pipeline: https://github.com/Undeadgrishnackh/crafter-ai/actions/runs/12345
```

### Example 2: Tracing backward (public to dev)
A user reports a bug in nwave-ai v1.1.22. Mike runs `git tag -l "v1.1.22"` on nwave-dev and finds the tag. He runs `git log -1 v1.1.22` and sees the exact commit and its annotation "Published as nwave-ai v1.1.22". He can now bisect from that point.

### Example 3: Beta repo traceability
A beta tester reports an issue with RC `v1.1.22rc1` on nWave-beta. Mike looks at the nWave-beta commit message and finds "Source: nwave-dev@abc123d, Dev tag: v1.1.22.dev3" which tells him exactly which dev snapshot was promoted.

## UAT Scenarios (BDD)

### Scenario: Public repo commit has full traceability
Given a stable release completes for v1.1.22 (public v1.1.22)
When inspecting the nWave public repo commit for v1.1.22
Then the commit message contains "Source: nwave-dev@" followed by a 40-char SHA
And the commit message contains "Dev tag: v1.1.22.dev3"
And the commit message contains "RC tag: v1.1.22rc1"
And the commit message contains "Stable tag: v1.1.22"
And the commit message contains a pipeline run URL

### Scenario: Beta repo commit has traceability
Given an RC release completes for v1.1.22rc1
When inspecting the nWave-beta commit for v1.1.22rc1
Then the commit message contains the source commit SHA
And the commit message contains the dev tag

### Scenario: Reverse lookup via marker tag
Given stable release created marker tag "v1.1.22"
When Mike runs "git show v1.1.22" on nwave-dev
Then the tag annotation shows "Published as nwave-ai v1.1.22"
And the tag points to the correct source commit

### Scenario: Forward lookup across three repos
Given the traceability chain: dev3 -> rc1 -> stable -> public v1.1.22
When Mike starts from commit abc123d on nwave-dev
Then he can find tag v1.1.22.dev3 (dev)
And he can find tag v1.1.22rc1 (RC)
And he can find tag v1.1.22 (stable)
And he can find tag v1.1.22 (public marker)

## Acceptance Criteria
- [ ] Public repo commits include: source SHA, dev tag, RC tag, stable tag, pipeline URL
- [ ] Beta repo commits include: source SHA, dev tag, pipeline URL
- [ ] Marker tag `vX.Y.Z` created on nwave-dev for each public release
- [ ] Marker tag annotation includes "Published as nwave-ai vX.Y.Z"
- [ ] Any public version can be traced to its source commit in a single git command

## Technical Notes
- Requires passing the full traceability chain through workflow outputs between stages
- Marker tag format: `v{nwave_ai_version}` (PEP 440 compliant, no prefix)
- Commit message template should be centralized (in the reusable sync workflow)
- Dependency: US-RTR-004 (reusable sync workflow is where commit messages are composed)
