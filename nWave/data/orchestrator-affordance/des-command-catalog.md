## des producing-tools + gates — reach for these instead of hand-editing

Every hand-edit of a checked artifact is a producing tool you didn't invoke. The catalog
(the system pays, not you):

**Authoring the dispatch / feature-delta**
- `des dispatch --mode atdd_pure --project-id <id> --slice <slice> --phase A_GREEN [--lane bugfix --defect <d> --regression-test <t>] [--at-kind pytest-regression --regression-test-file <f>] --intent "<task>"` — GENERATES a gate-valid crafter dispatch prompt by construction. Never hand-assemble the marker block / 12 sections. Add `--at-kind pytest-regression --regression-test-file <f>` for a feature whose AT is a pytest file (not gherkin).
- `des feature-delta-doctor <path>` — one-pass gap aggregator over a feature-delta.md (missing sections, malformed Wave headings, malformed/unjustified Reuse Analysis). Run BEFORE DISTILL; fix every gap it lists.
- `des validate-feature-delta <path> --require-slice-plan --require-reuse-analysis` — structural validator (the readiness gate's view).

**Sealing the AT (before dispatching the crafter)**
- `des verify-red-green --record-red --test-file <f>` — records the RedObserved seal (bound to the file's current content; re-run if the file changes).
- `des verify-negative-at --test-file <f> --all-critical` — verifies ≥1 negative AT present.
- `des at-review-verdict --feature-id <id> --slice-id <s> --verdict APPROVED --reviewer-agent-id <a> --at-kind pytest-regression --regression-test-file <f>` — records an AT-review verdict (the reviewer-verdict path clears the carpaccio gate for a pytest AT).
- `des carpaccio-slice-gate --feature-id <id> --entering-slice <slice> [--at-kind pytest-regression --regression-test-file <f>]` — run it DIRECTLY to see the full what/why/how when the hook-truncated `ATReviewGateRejected` fires.

**After the crafter (examine + commit)**
- `des record-examine-verdict --repo . --feature-id <id> --slice <s> --charter <path> --verdict PASS --observations "<Vera's findings>" --examiner nw-user-examiner` — records Vera's charter-sealed verdict. A PASS with ≥1 flag is REFUSED (mechanical).
- `des commit-slice ...` — correct-by-construction slice commit (stages, Slice-Id trailer, folds in verify-then-record). Stamps Gate-Scope — do not hand-add.

**Producing tools for the hand-fix gates (GDP-4/5)**
- `des flavor-scaffold --flavor-id <id>` — the producing tool for a new workflow flavor (mode-registry-completeness routes here).
- `des check-contract-shape --files <paths>` — the Principle-11 mechanical check (CONTRACT_SHAPE docstrings / acceptance Outcome-anchor / banned-regex names).
- `scripts/hooks/validate_skill_hashes.py --repin` — re-pins the skill-hash baseline after an INTENTIONAL SKILL.md edit (system-pays; do not hand-edit the baseline).
- `des verify-catalog-coherence --repo-root .` — fast (<1s) registry↔catalog↔per-gate drift check (catches what the full suite catches late).
- `des feature-delta-doctor` / `des verify-readiness-pre-dispatch` — the readiness gates' self-explaining view; run before hitting the wall.

**Hygiene**: `uv run ruff format` · `uv run ruff check` · `uv run python scripts/docgen.py` (after frontmatter/description edits — freshness gate) · `uv run python scripts/hooks/check_documentation_freshness.py`.

**Unsure about nWave methodology, a command, or wave status?** `/nw-buddy` — the first
agent to consult for any nWave question (methodology, project navigation, command help,
wave status, migration, troubleshooting). Ask there before guessing.
