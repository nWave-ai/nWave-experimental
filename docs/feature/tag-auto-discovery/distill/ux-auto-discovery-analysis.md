# UX Analysis: Release Train Tag Auto-Discovery

**Author**: Luna (nw-product-owner)
**Date**: 2026-02-23
**Epic**: Release Train UX Improvement
**Status**: Requirements ready for DESIGN wave (review-updated 2026-02-23)
**Reviewer**: Eclipse (nw-product-owner-reviewer)
**Review status**: APPROVED after addressing 3 findings

## 1. Current Pain: Alessandro's Journey

```
Alessandro wants to promote a dev build to RC.

 TRIGGER                    GITHUB ACTIONS UI              OUTCOME
 --------                   -------------------            -------
 "Let's ship               +------------------------+
  the RC"                   | Source dev tag          |
 Confident                  | [________________]     |     "What do I
              ------------> | required: true         | --> type here?"
                            +------------------------+     Confused

                            He opens a new tab,            "There are
                            navigates to Tags page,         dozens of
                            scrolls through tags...         tags..."
                            Anxious                        Overwhelmed

                            Types: v1.1.22.dev8            Wrong tag.
                            (meant v1.1.23.dev1)           Pipeline fails.
                            Frustrated                     Defeated
```

**Emotional arc (current)**: Confident -> Confused -> Overwhelmed -> Frustrated -> Defeated

The core problem: a required free-text field with zero context forces the user to **leave the workflow UI**, **research** available tags, **remember** the right one, and **type it without error**. Every step is a failure point.

## 2. Proposed Solution: Journey with Auto-Discovery

```
Alessandro wants to promote a dev build to RC.

 TRIGGER                    GITHUB ACTIONS UI                 OUTCOME
 --------                   -------------------               -------
 "Let's ship               +-------------------------------+
  the RC"                   | Source dev tag                 |
 Confident                  | (leave empty for latest,      |
              ------------> |  or enter e.g. v1.1.23.dev1)  |  "I'll just
                            | [________________________]    |   leave it
                            | required: false               |   empty"
                            +-------------------------------+   Confident

                            Pipeline log shows:               "It picked
                            "Auto-selected: v1.1.23.dev1     the right one"
                             (latest dev tag)"               Reassured

                            run-name: "RC Release from       Visible
                            v1.1.23.dev1"                    confirmation.
                            Confident                        Done.
```

**Emotional arc (proposed)**: Confident -> Confident -> Reassured -> Done

The empty-means-latest pattern eliminates the **research**, **recall**, and **typing** steps entirely. The power-user override preserves explicit control for those who need it.

## 3. Interaction Design Validation

### 3.1 "Empty = latest, explicit = override" Pattern

This is a well-established UX pattern (progressive disclosure with sensible defaults). It works here because:

| Criterion | Assessment |
|---|---|
| Default is safe | Yes. Latest dev tag is the most common choice. |
| Override is discoverable | Yes. Placeholder text shows the format. |
| Feedback is clear | Yes. Pipeline logs and run-name both show which tag was selected. |
| Failure is clear | Yes. If no tags exist, a specific error explains why. |

**Verdict**: Sound pattern for this use case.

### 3.2 Label and Placeholder Design

**Current (RC workflow):**
```
description: "Source dev tag to promote (e.g. v1.1.22.dev3)"
required: true
```

**Proposed (RC workflow):**
```
description: "Source dev tag (leave empty for latest, or enter e.g. v1.1.23.dev1)"
required: false
default: ""
```

**Current (Stable workflow):**
```
description: "Source RC tag to promote (e.g. v1.1.22rc1)"
required: true
```

**Proposed (Stable workflow):**
```
description: "Source RC tag (leave empty for latest, or enter e.g. v1.1.23rc2)"
required: false
default: ""
```

**Recommendation**: The labels are clear. One refinement: the word "latest" could be ambiguous (latest by time? by version number?). Since the auto-discovery uses semantic version sorting, the description should match. Suggested:

```
"Source dev tag (leave empty for highest version, or enter e.g. v1.1.23.dev1)"
```

However, "highest version" is less natural than "latest" for most users. Since the log output says "latest dev tag" and the sort guarantees it is the highest semantic version, **"latest" is acceptable** as long as the sort implementation is correct. The log message clarifies the behavior.

### 3.3 Run-Name Traceability

**Current run-name:**
```yaml
run-name: "RC Release from ${{ inputs.source_dev_tag }}"
```

When the input is empty, this would render as "RC Release from " (blank). The run-name must reflect the resolved tag.

**Required change**: The resolved tag must flow back into the run-name. Since `run-name` is evaluated at trigger time (before any job runs), and auto-discovery happens inside a job, the run-name cannot show the auto-discovered tag directly.

**Options:**

| Option | Approach | Tradeoff |
|---|---|---|
| A | Two-line run-name with ternary | Shows "(auto)" when empty, actual tag appears in job summary |
| B | Step summary + annotations | Run-name is generic, but annotations show the resolved tag |
| C | Resolve in a pre-job, pass via outputs | Adds complexity; run-name still cannot use job outputs |

**Recommendation**: Option A is the pragmatic choice.

```yaml
run-name: "RC Release from ${{ inputs.source_dev_tag || '(auto-latest)' }}${{ inputs.dry_run == true && ' (dry run)' || '' }}"
```

This clearly signals to anyone browsing the Actions list that auto-discovery was used. The actual resolved tag appears in job logs, step summary, and Slack notification.

## 4. Edge Cases and UX Risks

### 4.1 Critical: Lexicographic Sort Trap

**Risk**: String sorting `v1.1.23.dev9` > `v1.1.23.dev10` gives the wrong result.

**Already addressed** in the proposal via integer tuple sort. The `next_version.py` script already uses `packaging.Version` which handles this correctly. The auto-discovery logic should use the same library.

**Recommendation**: Reuse `packaging.Version` for tag discovery sorting, not a hand-rolled regex. This guarantees PEP 440 compliance and correct ordering.

### 4.2 Mixed Base Versions in Tags

**Scenario**: Tags exist for multiple base versions:
```
v1.1.22.dev1, v1.1.22.dev2, v1.1.23.dev1
```

**Question**: Does "latest" mean `v1.1.23.dev1` (highest semantic) or `v1.1.22.dev2` (latest in the 1.1.22 series)?

**Recommendation**: Highest semantic version across all bases. This is what `packaging.Version` comparison naturally gives: `1.1.23.dev1 > 1.1.22.dev2`. This matches user expectation of "latest."

### 4.3 No Matching Tags Exist

**Scenario**: Alessandro runs Stage 2 but no `v*.dev*` tags exist yet.

**Current behavior**: The workflow would fail at the validate-source step with "Tag not found."

**Proposed behavior**: The auto-discovery step should fail **before** validate-source with a specific message:

```
Error: No dev tags found matching pattern 'v*.dev*'.
Run Stage 1 (Dev Release) first to create a dev snapshot.
```

This transforms a cryptic "tag not found" into actionable guidance.

### 4.4 Stale Tags: Unreleased Commits After Auto-Discovered Tag

**Scenario**: The latest dev tag is `v1.1.23.dev1` but 12 commits have landed on master since then. Alessandro might not realize he's promoting a stale snapshot that excludes recent work.

**Key insight**: Staleness is not about calendar time. If master hasn't moved since the tag, there's nothing to warn about. The real signal is **unreleased commits sitting on master after the tag**.

**Detection**: `git rev-list --count v1.1.23.dev1..HEAD`. Zero means the tag is current.

**Recommendation**: When auto-discovering a tag with unreleased commits behind it, add a warning annotation:

```
Auto-selected: v1.1.23.dev1 (latest dev tag)
::warning::12 commits on master are not included in v1.1.23.dev1. Consider creating a fresh dev release first.
```

When the tag points at HEAD (zero commits behind):
```
Auto-selected: v1.1.23.dev1 (latest dev tag, at HEAD)
```

This does not block the pipeline but makes the user aware that code is being left behind. The warning is actionable: cancel and run Stage 1 first.

### 4.5 Explicit Tag That Does Not Exist

**Scenario**: Alessandro explicitly types `v1.1.23.dev99` which does not exist.

**Current behavior**: Fails at validate-source with "Tag not found" and lists available tags.

**Proposed behavior**: No change needed. The current error message is good. The available tags list helps the user correct the typo.

### 4.6 Stable Workflow: RC Tag Ordering

**Scenario**: Multiple RC tags exist: `v1.1.22rc1`, `v1.1.22rc2`, `v1.1.23rc1`.

`packaging.Version` correctly orders these: `1.1.23rc1 > 1.1.22rc2 > 1.1.22rc1`. The user would want `v1.1.23rc1`, which is the highest. No issue here.

### 4.7 Concurrent Releases

**Scenario**: Two team members both trigger Stage 2 with auto-latest at the same time.

**Mitigation**: The existing `concurrency` group (`release-rc-${{ github.ref }}`) with `cancel-in-progress: false` means the second run will queue. Both will discover the same latest tag, and the second will fail gracefully at the tag-creation step (tag already exists). This is acceptable and already handled.

### 4.8 GitHub Actions Input Type Behavior

**Technical note**: When `required: false` and `type: string` with no `default`, GitHub Actions passes an empty string `""` to the workflow. The auto-discovery logic should treat both empty string and whitespace-only as "use auto-discovery."

```python
if not source_dev_tag or not source_dev_tag.strip():
    # auto-discover
```

## 5. Acceptance Criteria

### US-1: Auto-Discover Latest Dev Tag for RC Release

**Problem (The Pain)**:
Alessandro Digioia is a release engineer who triggers RC releases via the GitHub Actions Web UI. He finds it frustrating and error-prone to manually look up the correct dev tag from a separate page, then type it into a blank text field without any guidance.

**Who (The User)**:
- Release engineer using GitHub Actions Web UI
- Triggers RC releases monthly or after each sprint
- Wants the release done quickly and correctly

**Solution (What We Build)**:
Make the `source_dev_tag` input optional. When left empty, auto-discover the highest semantic version dev tag. When explicitly provided, use that exact tag (existing behavior).

**Domain Examples:**

**Example 1: Happy path, auto-discover**
Alessandro Digioia opens the "Release: RC (Stage 2)" workflow, leaves the source dev tag field empty, and clicks "Run workflow." Tags on the repo include `v1.1.22.dev1`, `v1.1.22.dev2`, and `v1.1.23.dev1`. The pipeline selects `v1.1.23.dev1` as the highest semantic version and proceeds to create `v1.1.23rc1`.

**Example 2: Power user override**
Mike Brissoni wants to promote a specific older dev build (`v1.1.22.dev2`) because `v1.1.23.dev1` introduced an experimental feature. He types `v1.1.22.dev2` in the input field. The pipeline uses that exact tag and proceeds normally.

**Example 3: No dev tags exist**
Priya Sharma, a new team member, tries to run Stage 2 without having run Stage 1 first. She leaves the field empty. The pipeline fails with: "No dev tags found matching pattern 'v*.dev*'. Run Stage 1 (Dev Release) first to create a dev snapshot."

**Example 4: Explicit tag typo**
Alessandro types `v1.1.23.dev99` which does not exist. The pipeline fails at validate-source with "Tag v1.1.23.dev99 not found" and lists the 10 most recent dev tags, helping him identify the correct one.

**Example 5: Stale tag warning (unreleased commits)**
Alessandro leaves the field empty. The latest dev tag `v1.1.23.dev1` exists but 12 commits have landed on master since. The pipeline selects it and logs: "Auto-selected: v1.1.23.dev1 (latest dev tag)." A warning annotation shows: "12 commits on master are not included in v1.1.23.dev1. Consider creating a fresh dev release first." The pipeline continues but Alessandro decides to cancel and run Stage 1 to capture the recent work.

**UAT Scenarios (BDD):**

```gherkin
Feature: Auto-discover latest dev tag for RC release

  Scenario: Auto-discover when field is left empty
    Given dev tags v1.1.22.dev1, v1.1.22.dev2, and v1.1.23.dev1 exist on the repository
    When Alessandro triggers "Release: RC (Stage 2)" with source_dev_tag left empty
    Then the pipeline resolves the source tag to v1.1.23.dev1
    And the pipeline log shows "Auto-selected: v1.1.23.dev1 (latest dev tag)"
    And the RC version is calculated from base version 1.1.23

  Scenario: Explicit tag override preserves existing behavior
    Given dev tags v1.1.22.dev1, v1.1.22.dev2, and v1.1.23.dev1 exist on the repository
    When Mike triggers "Release: RC (Stage 2)" with source_dev_tag set to "v1.1.22.dev2"
    Then the pipeline uses v1.1.22.dev2 as the source tag
    And the RC version is calculated from base version 1.1.22

  Scenario: No dev tags exist
    Given no dev tags exist on the repository
    When Priya triggers "Release: RC (Stage 2)" with source_dev_tag left empty
    Then the pipeline fails with error "No dev tags found"
    And the error message includes guidance to run Stage 1 first

  Scenario: Explicit tag does not exist
    Given dev tag v1.1.23.dev1 exists on the repository
    When Alessandro triggers "Release: RC (Stage 2)" with source_dev_tag set to "v1.1.23.dev99"
    Then the pipeline fails with error "Tag v1.1.23.dev99 not found"
    And the error output lists available dev tags

  Scenario: Integer sort, not string sort
    Given dev tags v1.1.23.dev2, v1.1.23.dev9, and v1.1.23.dev10 exist
    When Alessandro triggers "Release: RC (Stage 2)" with source_dev_tag left empty
    Then the pipeline resolves the source tag to v1.1.23.dev10
    And not to v1.1.23.dev9

  Scenario: Stale tag warning when unreleased commits exist after auto-discovered tag
    Given dev tag v1.1.23.dev1 exists on the repository
    And 12 commits exist on master after v1.1.23.dev1
    When Alessandro triggers "Release: RC (Stage 2)" with source_dev_tag left empty
    Then the pipeline resolves the source tag to v1.1.23.dev1
    And the pipeline log shows "Auto-selected: v1.1.23.dev1 (latest dev tag)"
    And a GitHub Actions warning annotation shows "12 commits on master are not included in v1.1.23.dev1"
    And the pipeline continues normally (warning does not block)

  Scenario: No warning when auto-discovered tag is at HEAD
    Given dev tag v1.1.23.dev2 exists on the repository
    And v1.1.23.dev2 points to the current HEAD of master
    When Alessandro triggers "Release: RC (Stage 2)" with source_dev_tag left empty
    Then the pipeline resolves the source tag to v1.1.23.dev2
    And no staleness warning is shown
```

**Acceptance Criteria:**
- [ ] `source_dev_tag` input is optional (required: false, default: "")
- [ ] Empty input triggers auto-discovery of the highest semantic version dev tag
- [ ] Auto-discovery uses `packaging.Version` for sorting (behavioral test: dev10 > dev9)
- [ ] Pipeline log clearly states which tag was auto-selected
- [ ] Run-name shows "(auto-latest)" when input was empty
- [ ] Explicit tag input works identically to current behavior
- [ ] Missing tags produce a clear error with actionable guidance
- [ ] validate-source outputs the resolved tag; all downstream jobs use that output, not the raw input
- [ ] When unreleased commits exist after auto-selected tag, a warning annotation is shown (Should)
- [ ] When auto-selected tag is at HEAD, no warning is shown

**Technical Notes:**
- Auto-discovery runs inside the `validate-source` job, before CI gate
- Uses `git tag -l "v*.dev*"` to list candidates, then `packaging.Version` to sort
- MUST use `packaging.Version` for sorting. MUST NOT use bash sort or regex. Enforced by behavioral test (dev10 > dev9).
- Treat empty string and whitespace-only input as "auto-discover"
- validate-source outputs `resolved_tag` replacing raw `inputs.source_dev_tag` for all downstream references
- Staleness check: `git rev-list --count <tag>..HEAD`. Zero = at HEAD (no warning). Non-zero = warn with commit count.
- Concurrency group prevents race conditions between simultaneous triggers

---

### US-2: Auto-Discover Latest RC Tag for Stable Release

**Problem (The Pain)**:
Alessandro Digioia is a release engineer who triggers Stable releases via the GitHub Actions Web UI. He must manually identify the correct RC tag to promote, which involves the same frustrating lookup and typing process as Stage 2.

**Who (The User)**:
- Same release engineer persona as US-1
- Triggers stable releases after RC validation period

**Solution (What We Build)**:
Make the `source_rc_tag` input optional. When left empty, auto-discover the highest semantic version RC tag. When explicitly provided, use that exact tag.

**Domain Examples:**

**Example 1: Happy path, auto-discover**
Alessandro leaves the source RC tag field empty. Tags include `v1.1.22rc1`, `v1.1.22rc2`, and `v1.1.23rc1`. The pipeline selects `v1.1.23rc1` and produces stable `v1.1.23`.

**Example 2: Power user override**
Mike explicitly enters `v1.1.22rc2` to release the 1.1.22 series while 1.1.23 RC is still under validation. The pipeline uses that exact tag.

**Example 3: No RC tags exist**
Priya leaves the field empty but no RC tags exist. The pipeline fails with: "No RC tags found matching pattern 'v*rc*'. Run Stage 2 (RC Release) first to create a release candidate."

**UAT Scenarios (BDD):**

```gherkin
Feature: Auto-discover latest RC tag for stable release

  Scenario: Auto-discover when field is left empty
    Given RC tags v1.1.22rc1, v1.1.22rc2, and v1.1.23rc1 exist on the repository
    When Alessandro triggers "Release: Stable (Stage 3)" with source_rc_tag left empty
    Then the pipeline resolves the source tag to v1.1.23rc1
    And the pipeline log shows "Auto-selected: v1.1.23rc1 (latest RC tag)"
    And the stable version is calculated as 1.1.23

  Scenario: Explicit tag override preserves existing behavior
    Given RC tags v1.1.22rc1, v1.1.22rc2, and v1.1.23rc1 exist on the repository
    When Mike triggers "Release: Stable (Stage 3)" with source_rc_tag set to "v1.1.22rc2"
    Then the pipeline uses v1.1.22rc2 as the source tag
    And the stable version is calculated as 1.1.22

  Scenario: No RC tags exist
    Given no RC tags exist on the repository
    When Priya triggers "Release: Stable (Stage 3)" with source_rc_tag left empty
    Then the pipeline fails with error "No RC tags found"
    And the error message includes guidance to run Stage 2 first

  Scenario: Integer sort for RC numbers
    Given RC tags v1.1.23rc2, v1.1.23rc9, and v1.1.23rc10 exist
    When Alessandro triggers "Release: Stable (Stage 3)" with source_rc_tag left empty
    Then the pipeline resolves the source tag to v1.1.23rc10
    And not to v1.1.23rc9

  Scenario: Dry run with auto-discovery
    Given RC tag v1.1.23rc1 exists on the repository
    When Alessandro triggers "Release: Stable (Stage 3)" with source_rc_tag left empty and dry_run true
    Then the pipeline auto-selects v1.1.23rc1
    And the dry run summary shows the resolved tag
    And no tags, releases, or publishes are created

  Scenario: Stale RC tag warning when unreleased commits exist
    Given RC tag v1.1.23rc1 exists on the repository
    And 5 commits exist on master after v1.1.23rc1
    When Alessandro triggers "Release: Stable (Stage 3)" with source_rc_tag left empty
    Then the pipeline resolves the source tag to v1.1.23rc1
    And a GitHub Actions warning annotation shows "5 commits on master are not included in v1.1.23rc1"
    And the pipeline continues normally (warning does not block)
```

**Acceptance Criteria:**
- [ ] `source_rc_tag` input is optional (required: false, default: "")
- [ ] Empty input triggers auto-discovery of the highest semantic version RC tag
- [ ] Auto-discovery uses `packaging.Version` for sorting (behavioral test: rc10 > rc9)
- [ ] Pipeline log clearly states which tag was auto-selected
- [ ] Run-name shows "(auto-latest)" when input was empty
- [ ] Explicit tag input works identically to current behavior
- [ ] Missing tags produce a clear error with actionable guidance
- [ ] Dry run mode works correctly with auto-discovered tags
- [ ] validate-source outputs the resolved tag; all downstream jobs use that output, not the raw input
- [ ] When unreleased commits exist after auto-selected tag, a warning annotation is shown (Should)

**Technical Notes:**
- Same implementation pattern as US-1, with `v*rc*` tag pattern
- The `validate-source` job already handles explicit tag validation; add auto-discovery branch
- MUST use `packaging.Version` for sorting. MUST NOT use bash sort or regex. Enforced by behavioral test (rc10 > rc9).
- validate-source outputs `resolved_tag` replacing raw `inputs.source_rc_tag` for all downstream references (changelog, trace message, sync, Slack)
- Staleness check: `git rev-list --count <tag>..HEAD`. Zero = no warning. Non-zero = warn with commit count.
- Concurrency group prevents race conditions between simultaneous triggers

---

## 6. Implementation Scope Boundary

### What changes:

| File | Change |
|---|---|
| `.github/workflows/release-rc.yml` | Input becomes optional; add auto-discover step in validate-source; update run-name; propagate resolved tag |
| `.github/workflows/release-prod.yml` | Input becomes optional; add auto-discover step in validate-source; update run-name; propagate resolved tag |
| `docs/release/release-train-howto.md` | Update instructions to document auto-discovery |

### What stays unchanged:

| Item | Reason |
|---|---|
| `scripts/release/next_version.py` | Version calculation logic is not affected |
| `scripts/release/ci_gate.py` | CI gate logic is not affected |
| `scripts/release/trace_message.py` | Receives resolved tag via validate-source output (not raw input) |
| `scripts/release/patch_pyproject.py` | Not affected |
| `.github/workflows/release-dev.yml` | Stage 1 has no tag input (uses HEAD) |
| `pyproject.toml [tool.nwave]` | Version floor mechanism is orthogonal |
| Three-stage gate sequence | Architecture unchanged |
| `dry_run` option | Works with resolved tag |

### New code needed:

| File | Purpose |
|---|---|
| `scripts/release/discover_tag.py` | Testable Python script using `packaging.Version` for tag discovery and sorting |
| `tests/release/test_discover_tag.py` | Behavioral tests including the dev9 vs dev10 integer sort trap |

**Why a script, not inline bash**: `packaging.Version` is testable, reusable across both workflows, and avoids bash sort fragility. The existing `next_version.py` already uses `packaging.Version`, establishing the pattern.

Suggested interface:
```
python scripts/release/discover_tag.py --pattern "dev" [--tag-list TAG1,TAG2,...]
# output: {"tag": "v1.1.23.dev1", "version": "1.1.23.dev1", "found": true, "commits_behind": 0}
#    or:  {"tag": null, "found": false, "error": "No dev tags found..."}
```

### Critical handoff contract:

The `validate-source` job in both workflows must output `resolved_tag` (auto-discovered or explicit). All downstream jobs reference `needs.validate-source.outputs.resolved_tag`, **never** `inputs.source_dev_tag` or `inputs.source_rc_tag` directly. This includes:
- Changelog generation (compare range)
- Trace message (`--dev-tag` argument)
- Sync to beta/public repos
- Slack notification
- Dry run summary

## 7. Recommendations Summary

| # | Recommendation | Priority | Review note |
|---|---|---|---|
| 1 | Use `packaging.Version` for tag discovery sort, enforced by behavioral test (dev10 > dev9) | **Must** | Upgraded: AC + behavioral test, not just recommendation |
| 2 | Show "(auto-latest)" in run-name when input is empty | **Must** | Actual resolved tag appears in logs + Slack |
| 3 | Propagate resolved tag (not raw input) to all downstream references via validate-source output | **Must** | Critical handoff: changelog, trace_message, sync, Slack |
| 4 | Fail with actionable guidance when no matching tags exist | **Must** | |
| 5 | Create `scripts/release/discover_tag.py` + `tests/release/test_discover_tag.py` | **Must** | Upgraded from Should: testability is non-negotiable |
| 6 | Warn when unreleased commits exist after auto-selected tag (commit-distance, not calendar days) | **Should** | Upgraded from Could, reframed from calendar to commit distance |
| 7 | Keep "latest" wording in description (natural, log clarifies meaning) | **Should** | |
| 8 | Update `release-train-howto.md` to document auto-discovery | **Must** | |
