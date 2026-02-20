# US-RTR-007: Tag Cleanup and PEP 440 Normalization

## Problem (The Pain)
Mike is the nwave-dev maintainer whose repository has accumulated tags in inconsistent formats from the current pipeline.
He finds the tag namespace cluttered with non-PEP-440 tags (e.g., `v2.17.x` style without proper dev/rc segments) that will conflict with the new 3-stage naming convention. Before the new pipeline can create `v2.18.0.dev1`, the existing tags need to be cleaned up and the tag namespace needs a clear convention.

## Who (The User)
- Mike, cleaning up the tag namespace before enabling the new pipeline
- CI/CD system, which needs unambiguous tag patterns to calculate version counters
- `git tag -l` output that should be human-scannable and PEP 440 compliant

## Solution (What We Build)
A one-time cleanup script and documented tag convention. Remove or rename non-standard tags on nwave-dev, ensure all existing release tags follow `vX.Y.Z` format, and document the tag naming convention for the three stages (dev, RC, stable) plus the public marker convention.

## Domain Examples

### Example 1: Audit existing tags
Mike runs the tag audit script. It finds tags like `v2.17.6`, `v2.17.5` (valid), `nWave_v1.1.0` (valid marker), and potentially any malformed tags. The script reports: "47 tags found. 45 valid, 2 non-standard: [list]."

### Example 2: Dry run cleanup
Mike runs the cleanup script in dry-run mode. It reports what would change: "Would delete 2 non-standard tags: tag-a, tag-b. Would keep 45 tags. No PEP 440 conflicts detected." Mike reviews and confirms.

### Example 3: Document convention for future reference
After cleanup, a `TAG_CONVENTION.md` file in the repo documents: stable tags use `vX.Y.Z`, dev tags use `vX.Y.Z.devN`, RC tags use `vX.Y.ZrcN`, public markers use `nWave_vX.Y.Z`. This becomes the reference for the new pipeline.

## UAT Scenarios (BDD)

### Scenario: Audit identifies non-standard tags
Given the nwave-dev repo has 47 existing tags
When the audit script runs
Then it classifies each tag as: stable (vX.Y.Z), marker (nWave_vX.Y.Z), or non-standard
And it reports the count of each category

### Scenario: Dry run shows planned changes
Given the audit found 2 non-standard tags
When the cleanup script runs in dry-run mode
Then it lists the tags that would be deleted
And it confirms no PEP 440 conflicts exist
And no actual tags are deleted

### Scenario: Cleanup removes non-standard tags
Given Mike approved the cleanup plan
When the cleanup script runs (not dry-run)
Then non-standard tags are deleted from local and remote
And all remaining tags follow the documented convention

### Scenario: Tag convention documented
Given the cleanup is complete
When the tag convention document exists
Then it specifies the format for dev, RC, stable, and marker tags
And it specifies PEP 440 compliance rules

## Acceptance Criteria
- [ ] Audit script lists all tags with classification (standard vs non-standard)
- [ ] Cleanup script has dry-run mode (no side effects until confirmed)
- [ ] Non-standard tags removed from both local and remote
- [ ] All remaining tags follow PEP 440 convention
- [ ] Tag convention documented for future reference
- [ ] No conflicts between existing stable tags and new dev/RC tag patterns

## Technical Notes
- One-time task; the script does not need to be maintained long-term
- Must handle both local and remote tag cleanup (`git push --delete origin <tag>`)
- Should preserve all valid `vX.Y.Z` and `nWave_vX.Y.Z` tags
- Run before enabling US-RTR-001 (dev release pipeline) to avoid counter conflicts
- Consider: should this be a script in `scripts/` or a manual procedure documented in a runbook?
