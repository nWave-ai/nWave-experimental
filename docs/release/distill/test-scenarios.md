# Test Scenario Inventory: Release Train Tag Auto-Discovery

**Feature**: `scripts/release/discover_tag.py`
**Test file**: `tests/release/test_discover_tag.py`
**Date**: 2026-02-23

## Scenario Map

15 total scenarios. 6 error/edge paths (40%).

| # | Class | Scenario | Roadmap Step | Type |
|---|-------|----------|-------------|------|
| 1 | TestWalkingSkeleton | Auto-discover highest dev tag | Step 1 | Walking skeleton |
| 2 | TestDevTagHappyPath | Mixed base versions return globally highest | Step 1 | Happy path |
| 3 | TestDevTagDigitTransition | dev11 beats dev9 (11-entry fixture) | Step 1 | Sort correctness |
| 4 | TestRCTagHappyPath | Auto-discover highest RC tag | Step 1 | Happy path |
| 5 | TestRCTagDigitTransition | rc11 beats rc9 (11-entry fixture) | Step 1 | Sort correctness |
| 6 | TestExplicitTagValidation | Validate existing tag returns it | Step 1 | Happy path |
| 7 | TestExplicitTagValidation | Validate missing tag returns error | Step 1 | Error path |
| 8 | TestNoTagsExist | No dev tags, Stage 1 guidance | Step 1 | Error path |
| 9 | TestNoTagsExist | No RC tags, Stage 2 guidance | Step 1 | Error path |
| 10 | TestInvalidInput | Invalid pattern exits with code 2 | Step 1 | Error path |
| 11 | TestInvalidInput | Invalid tags filtered, valid sorted | Step 1 | Edge case |
| 12 | TestStalenessDetection | Tag at HEAD, 0 commits behind | Step 2 | Integration |
| 13 | TestStalenessDetection | Tag behind HEAD, N commits behind | Step 2 | Integration |
| 14 | TestStalenessDetection | commits_behind null with --tag-list | Step 2 | Edge case |
| 15 | TestEdgeCases | Empty tag list string = no tags | Step 1 | Edge case |

## Implementation Sequence (one-at-a-time TDD)

1. **TestWalkingSkeleton::test_auto_discover_highest_dev_tag** (enabled)
2. TestDevTagHappyPath::test_mixed_base_versions_returns_globally_highest
3. TestDevTagDigitTransition::test_digit_transition_dev11_beats_dev9
4. TestRCTagHappyPath::test_auto_discover_highest_rc_tag
5. TestRCTagDigitTransition::test_digit_transition_rc11_beats_rc9
6. TestExplicitTagValidation::test_validate_existing_tag_returns_it_directly
7. TestExplicitTagValidation::test_validate_missing_tag_returns_not_found
8. TestNoTagsExist::test_no_dev_tags_returns_stage_1_guidance
9. TestNoTagsExist::test_no_rc_tags_returns_stage_2_guidance
10. TestInvalidInput::test_invalid_pattern_returns_exit_code_2
11. TestInvalidInput::test_invalid_tags_filtered_valid_ones_sorted
12. TestEdgeCases::test_empty_tag_list_string_treated_as_no_tags
13. TestStalenessDetection::test_commits_behind_is_null_with_tag_list
14. TestStalenessDetection::test_tag_at_head_shows_zero_commits_behind
15. TestStalenessDetection::test_tag_behind_head_shows_commit_count

## Fixture Dependencies

| Fixture | Location | Used By |
|---------|----------|---------|
| dev_tags_mixed_versions | conftest.py | Tests 1, 2, 6, 7, 14 |
| dev_tags_digit_transition | conftest.py | Test 3 |
| rc_tags_mixed | conftest.py | Test 4 |
| rc_tags_digit_transition | conftest.py | Test 5 |
| tmp_path | pytest built-in | Tests 12, 13 |
