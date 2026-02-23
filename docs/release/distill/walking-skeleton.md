# Walking Skeleton: Release Train Tag Auto-Discovery

**Test**: `TestWalkingSkeleton::test_auto_discover_highest_dev_tag`
**File**: `tests/release/test_discover_tag.py`

## Why This Scenario

The walking skeleton answers: "Can a release engineer auto-discover the correct tag?"

It is the simplest path that exercises the full script end-to-end:
- CLI argument parsing (`--pattern dev`, `--tag-list`)
- PEP 440 version parsing and sorting via `packaging.Version`
- JSON output generation with `tag`, `version`, `found` fields
- Exit code 0 for success

## What It Proves

| Aspect | Verified |
|--------|----------|
| Script runs as subprocess | Yes (same pattern as test_next_version.py) |
| Accepts --pattern and --tag-list | Yes |
| Sorts by semantic version (not string) | Yes (v1.1.23.dev1 > v1.1.22.dev2) |
| Returns correct JSON schema | Yes (tag, version, found) |
| Exit code 0 on success | Yes |

## What It Defers

| Aspect | Deferred To |
|--------|-------------|
| 2-digit dev numbers (dev10, dev11) | TestDevTagDigitTransition |
| RC pattern | TestRCTagHappyPath |
| Explicit tag validation | TestExplicitTagValidation |
| Error paths (no tags, invalid input) | TestNoTagsExist, TestInvalidInput |
| Staleness / commits_behind | TestStalenessDetection |

## Stakeholder Demo Script

> "Watch: I leave the source tag field empty and click Run.
> The script discovers v1.1.23.dev1 as the highest dev tag.
> The JSON output confirms it found the right one.
> No manual lookup. No typos. Done."
