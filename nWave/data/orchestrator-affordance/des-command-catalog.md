## des producing-tools + gates — reach for these instead of hand-editing

Every hand-edit of a checked artifact is a producing tool you didn't invoke. The catalog
(the system pays, not you):

**Where am I in the loop? What is the next legal step?**
- `des next --feature-id <id> [--format json]` — projects the next atdd_pure DELIVER-loop step (DISTILL the next slice · GREEN via crafter · examine · commit-slice) from the AT-completion ledger (`.nwave/telemetry/atdd-pure/<feature-id>.jsonl`) — terminal ledger evidence (`SliceCommitVerified`) wins over a stale markdown `Status` column. **One tracked narrow gap**: a slice cleared by a mechanical seal (pytest-regression, no `ATReviewVerdict` event) can get stuck advising "not yet GREEN" instead of advancing — if you hit that, trust the ledger over the advisory.

**Which lane? MEASURE the blast radius first — the line count is not the radius**
- `des blast-radius --repo . --paths <files...>` — measures a change's tier (S/M/L) from REAL data: files, lines (git diff), boundary/consumer signals (honest `not yet wired` reasons where unimplemented — never fabricated zeros). Errors degrade toward L, never silently toward S.
- **S lane** (measured small: ≤2 files/≤10 lines, no boundary): charter(PO) → orchestrator applies fix+test DIRECTLY → RED seal → Vera-haiku (real CLI) → commit-slice (tier-capped: an over-cap diff is refused+escalated). RCA optional when the cause is known.
- **M lane** (stable design): @prefactoring if needed → ONE DISTILL pass (all ATs) → resident crafter (skeleton-first, incremental commits) → ONE Vera → the FULL feature-end cycle (deep review · env-e2e · full-suite · sign+emit), never skipped.
- **L lane** (emergent design / boundary / many consumers): the per-slice cycle, unchanged.
- **Test pyramid default**: ONE `@walking_skeleton` subprocess-E2E per FEATURE; every other AT in-process/in-memory. Wiring = the WS + Vera on the real surface + feature-end backstop.

**Authoring the dispatch / feature-delta**
- `des dispatch --mode atdd_pure --project-id <id> --slice <slice> --phase A_GREEN [--lane bugfix --defect <d> --regression-test <t>] [--at-kind pytest-regression --regression-test-file <f>] --intent "<task>"` — GENERATES a gate-valid crafter dispatch prompt by construction. Never hand-assemble the marker block / 12 sections. Add `--at-kind pytest-regression --regression-test-file <f>` for a feature whose AT is a pytest file (not gherkin).
- `des feature-delta-doctor <path>` — one-pass gap aggregator over a feature-delta.md (missing sections, malformed Wave headings, malformed/unjustified Reuse Analysis). Run BEFORE DISTILL; fix every gap it lists.
- `des validate-feature-delta <path> --require-slice-plan --require-reuse-analysis` — structural validator (the readiness gate's view).

**Sealing the AT (before dispatching the crafter)**
- `des verify-red-green --record-red --test-file <f>` — records the RedObserved seal (bound to the file's current content; re-run if the file changes).
- `des verify-negative-at --test-file <f> --all-critical` — verifies ≥1 negative AT present.
- `des record-at-review-verdict --feature-id <id> --slice-id <s> --verdict APPROVED --reviewer-agent-id <a> --at-kind pytest-regression --regression-test-file <f>` — records an AT-review verdict (the reviewer-verdict path clears the carpaccio gate for a pytest AT).
- `des carpaccio-slice-gate --feature-id <id> --entering-slice <slice> [--at-kind pytest-regression --regression-test-file <f>]` — run it DIRECTLY to see the full what/why/how when the hook-truncated `ATReviewGateRejected` fires.

**After the crafter (examine + commit)**
- `des examine-fixture --out <dir> [--feature-id <id>]` — BUILDS a real, drivable repository the certification gate (`des verify-slice-commit`) accepts on the clean case (a shipped+attested slice, an entering slice, a deliberately-red work-ahead slice, each flippable red/green by editing one line) — so an examiner (Vera) who cannot read source can still REACH and BREAK the gate's real surface. Reach for THIS instead of hand-building an examine fixture.
- `des record-examine-verdict --repo . --feature-id <id> --slice <s> --charter <path> --verdict PASS --observations "<Vera's findings>" --examiner nw-user-examiner` — records Vera's charter-sealed verdict. A PASS with ≥1 flag is REFUSED (mechanical).
- `des commit-slice ...` — correct-by-construction slice commit (stages, Slice-Id trailer, folds in verify-then-record). Stamps Gate-Scope — do not hand-add.
- `des commit --owned-paths <p...> --step-id <id> --message <msg>` — **the SAFE commit when more than one agent shares this working tree.** A plain `git commit` from two concurrent agents races: the second sweeps up files the first staged but had not yet committed, and hooks that auto-stage formatter fixes widen the window — misattributed commits and a corrupted `Step-Id:` chain. This holds an exclusive `flock` AND builds the commit from a TEMPORARY index seeded with HEAD plus ONLY the owned paths, so the scope is correct **by construction**: a foreign file, a concurrently-staged file, or a hook's auto-staged file CANNOT enter it. Another agent's staged work is left intact. Reach for this — not bare `git commit` — whenever a sibling instance or a dispatched agent may be writing to the same tree.

**Autonomous consolidation/bugfix-loop commands**
- `des bugfix-pipeline-tick --feature-id <id> --project-root . --defect-id <slug> --action {stage-started,stage-completed,stage-failed,claim-drained} [--stage {rca,charter-authoring,at-authoring,red-seal,crafter-green,vera-examine,commit-slice}] --now <iso8601> [--reason <r>]` — the GENERAL bugfix-queue-draining pipeline: cloud-lane stages (rca/charter-authoring/at-authoring) fan out freely; box-lane stages (red-seal/crafter-green/vera-examine/commit-slice) are serialized to exactly ONE in-flight defect — a second `stage-started` into a box-lane stage while one is already occupied is NOT refused (exit 0) but records `BoxLaneEntryDeferred` with the occupying defect named, so you always know when you've violated the invariant, even after the fact. **Register every dispatched bugfix here** — running multiple bugfix lanes as an ad-hoc swarm without this bypasses the exact discipline this command exists to enforce.
- `des consolidation-signal-tick --feature-id <id> --project-root . --signal-type {drift,unmerged-work,stale-branch,failing-gate} --signal-key <k> --now <iso8601>` — ONE narrow intake path INTO the bugfix pipeline above, specifically for already-detected TRUNK-HEALTH signals (not general bugs/frictions — those still belong in `docs/product/backlog.md` until entered into the pipeline via `bugfix-pipeline-tick` directly). Unsupported `--signal-type` is refused LOUDLY with a ledger record (not a silent argparse error).
- `des work-exhausted-tick --feature-id <id> --project-root . --now <iso8601>` — the third autonomous-loop driving port (stops an idle-holding loop instead of spinning forever). All three ports are auto-ticked once per SessionStart (`handle_session_start()`, fail-open per domain) — no manual invocation needed for the steady-state loop, but direct invocation is the debugging/manual-drain path.

**Tech-debt pile drain**
- `des refactor --pile <path> --agent-cmd 'scripts/refactor_agent.py {prompt}' [--max-parallel N] [--regression-test-file <path>]` — **`scripts/refactor_agent.py` IS the shipped actuator**: pass it, do not invent a command. `--agent-cmd` is run as a real executable (the harness probes the first token with `shutil.which`), so a placeholder or an Agent-tool dispatch is NOT a valid value; before this script shipped the only usable value was `true`, which drains nothing. It receives the rendered prompt file as `{prompt}`, already runs with cwd set to the isolated worktree, drives a headless fixer there, and fails LOUD with what/why/how (exit 2 malformed input, 3 missing CLI, the fixer's own code otherwise — never a false success). Tune via NWAVE_REFACTOR_AGENT_{MODEL,PERMISSION,MAX_TURNS,CLI}. — drains pending tech-debt items from a pile file (`techdebt.md` -> `paidtechdebt.md`), one item per worktree+venv: dispatches the configured agent, runs fast+impacted green-to-green, merges into a clean integration branch, and mandatorily cleans up the worktree/branch on success OR failure (never leaves a stray worktree). `--max-parallel 1` (default) drains exactly one item; `N>1` drains a batch concurrently, each item isolated. Pile item grammar (only documented here — the CLI's own rejection message repeats it, but nothing surfaces it proactively before you hit the wall): `- [ ] <item_id>: paradigm=<object-oriented|functional> defect="<defect>" proposed_solution="<solution>" discovered_by=<channel>`. `discovered_by=` is OPTIONAL in the grammar (rows authored before the field existed still parse) and records HOW the defect was found, from the CLOSED set `{slice-execution, lane-report, systematic-audit, code-search, operational-incident, adversarial-review, gate-refusal, unattributed}` (SSOT `src/des/domain/refactor/discovery_method.py:RecognizedDiscoveryMethod`) -- it is the denominator of yield-per-verification-method, and a row that omits it is reported in `PileParseReport.unattributed_item_ids` instead of being counted as attributed. Declare the channel that SURFACED the defect, never the one that later verified it (a row that says `MISURATO` was measured, not discovered, by that act), and prefer `unattributed` over a classification you cannot support. `paradigm=` MUST be one of the CLOSED set `{object-oriented, functional}` -- the code-refactoring RPP lenses `des refactor` recognises (SSOT `src/des/domain/refactor/paradigm_select.py:RecognizedParadigm`). DERIVE it from the TARGET project's DECLARED development paradigm (its `## Development Paradigm` section, or the equivalent declaration the project ships) -- NEVER infer it from the file's language (a language is not a paradigm) and NEVER put the defect CLASS there (`SSOT`, `code`, `duplication` are defect taxonomy, not paradigms; that is what `defect=` is for). An unrecognised value makes the drain REFUSE the row. **`--driver {python,loop}` is a KNOWN STUB — do not rely on `loop` behaving differently from the `python` default:** the flag is parsed but never consulted; both values run the identical path today.

**⚠️ `des verify-worktree-cleanup --repo . --target-branch <b> [--check-only]`** — mechanically removes a worktree it classifies as safe (its `is_ancestor(head, target_branch)` check trivially returns true for a worktree that has made ZERO commits of its own the moment `target_branch` merely advances past its starting point via UNRELATED work — not just a genuine merge). This is a confirmed data-loss risk: NEVER run this in ACT mode (i.e. without `--check-only`) against any real, in-progress, or shared worktree — only against a disposable scratch worktree you created for that specific purpose.

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

## Full verb catalog (generated)

Every `des <verb>` subcommand, one row per `des.cli.__main__._REGISTRY` entry, generated
so this table can never silently drift from the registry the way M-III's defect found it
(declared-facts-reachable-recorded, slice-04).

<!-- GENERATED:des-command-catalog START — source of truth: src/des/cli/__main__.py::_REGISTRY; do not hand-edit (docgen renders this region) -->
| Verb | Module | Description |
| --- | --- | --- |
| `loop` | `des.cli.loop` | Public ``des loop`` command over the canonical standing-loop facade. |
| `log-phase` | `des.cli.log_phase` | CLI: Append a phase entry to execution-log.json with a real UTC timestamp. |
| `init-log` | `des.cli.init_log` | Legacy execution-log boundary for migration and read-only replay. |
| `resolve-workflow-mode` | `des.cli.resolve_workflow_mode` | Resolve the one active workflow mode without mutating the project. |
| `verify-integrity` | `des.cli.verify_deliver_integrity` | CLI: Verify deliver integrity before finalize. |
| `roadmap` | `des.cli.roadmap` | CLI: Roadmap init and validate tool. |
| `health-check` | `des.cli.health_check` | CLI: Verify nWave installation health with 7 diagnostic checks. |
| `verify-commit-trailers` | `des.cli.verify_commit_trailers` | AT-completion-ledger audit window for delivered slice commits. |
| `verify-slice-commit` | `des.cli.verify_slice_commit_completeness` | des-verify-slice-commit-completeness -- slice-commit verify-then-record gate. |
| `walking-skeleton-gate` | `des.cli.walking_skeleton_gate` | des.cli.walking_skeleton_gate -- the tiered production-like walking-skeleton gate. |
| `walking-skeleton-done-gate` | `des.cli.walking_skeleton_done_gate` | des.cli.walking_skeleton_done_gate -- the "feature done" block check. |
| `carpaccio-slice-gate` | `des.cli.carpaccio_slice_gate` | Carpaccio slice gate CLI -- the ATDD-pure DELIVER entry gate. |
| `classify-features` | `des.cli.classify_features` | des.cli.classify_features -- the `des-classify-features` detection CLI. |
| `convert-to-atdd-pure` | `des.cli.convert_to_atdd_pure` | des.cli.convert_to_atdd_pure -- the `des-convert-to-atdd-pure` conversion CLI. |
| `reverify-slice-commit` | `des.cli.reverify_slice_commit` | des-reverify-slice-commit -- recover an orphaned carpaccio slice. |
| `verify-seal-provenance` | `des.cli.verify_seal_provenance` | des-verify-seal-provenance -- did a sealed slice's AT exist at its own seal? |
| `verify-environmental-e2e` | `des.cli.verify_environmental_e2e` | des.cli.verify_environmental_e2e -- the shared cross-tree environmental-e2e gate. |
| `run-contract-gate` | `des.cli.run_contract_gate` | des-run-contract-gate -- the single canonical ATDD-pure contract gate. |
| `commit-slice` | `des.cli.commit_slice` | des commit-slice -- the mechanical correct-by-construction slice commit. |
| `emit-feature-end` | `des.cli.emit_feature_end` | des emit-feature-end -- the orchestrator-run feature-end record emitter. |
| `feature-end` | `des.cli.feature_end` | des feature-end -- the consolidated feature-end command namespace (DDD-7). |
| `check-slice-at-completeness` | `des.cli.check_slice_at_completeness` | des-check-slice-at-completeness -- feature-scoped E1-only completeness wrapper. |
| `doctor` | `des.cli.doctor` | des doctor CLI -- per-target-language language-adapter gap report. |
| `runner-probe` | `des.cli.runner_probe` | des runner-probe CLI -- QW5, mikado.md:47: the runner-capability probe report. |
| `verify-readiness-pre-dispatch` | `des.cli.verify_readiness_pre_dispatch` | D1 readiness pre-dispatch gate -- verify-readiness-pre-dispatch. |
| `verify-wave-dispatch` | `des.cli.verify_wave_dispatch` | Wave-dispatch guard gate -- ``des verify-wave-dispatch`` (slice-05, DDD-8/9). |
| `verify-slice-ledger-evidence` | `des.cli.verify_slice_ledger_evidence` | des verify-slice-ledger-evidence -- spine-ledger aggregator subcommand. |
| `validate-feature-delta` | `des.cli.validate_feature_delta` | validate_feature_delta — schema validator for lean feature-delta.md (C14). |
| `feature-delta-schema` | `des.cli.feature_delta_schema` | feature_delta_schema — the feature-delta section-schema algebra. |
| `feature-delta-doctor` | `des.cli.feature_delta_doctor` | des feature-delta-doctor -- one-pass structural gap aggregator (WS-2 / M2). |
| `flavor-scaffold` | `des.cli.flavor_scaffold` | des flavor-scaffold -- the PRODUCING tool for the mode 4-tuple (GDP-4/5). |
| `record-discuss-review` | `des.cli.discuss_review_verdict` | DISCUSS PO-review verdict PRODUCER -- ``des record-discuss-review`` (slice-07b). |
| `verify-discuss-review` | `des.cli.verify_discuss_review` | DISCUSS PO-review CONSUMER veto gate -- ``des verify-discuss-review`` (OB-2). |
| `record-at-review-verdict` | `des.cli.at_review_verdict` | AT-review verdict producer (ADR-029 D5 -- PRODUCER half; amended by |
| `commit` | `des.cli.commit` | CLI: Commit a step's owned files under an exclusive lock (issue #51, ADR-027). |
| `record-prose-delivered` | `des.cli.record_prose_delivered` | Prose-delivered record producer (DDD-5 -- PRODUCER half). |
| `verify-fresh-clone` | `des.cli.verify_fresh_clone` | ``des verify-fresh-clone`` -- the P0.1 evidence-by-execution gate. |
| `verify-red-green` | `des.cli.verify_red_green` | ``des verify-red-green`` -- the P0.2 RED->GREEN non-vacuity seal. |
| `verify-negative-at` | `des.cli.verify_negative_at` | ``des verify-negative-at`` -- the P0.3 negative-AT mandate gate. |
| `verify-refactor-trigger` | `des.cli.verify_refactor_trigger` | ``des verify-refactor-trigger`` -- the P1.3 signal-driven refactor trigger. |
| `verify-doc-coherence` | `des.cli.verify_doc_coherence` | ``des verify-doc-coherence`` -- the P0.5 evidence-by-execution gate. |
| `verify-execution-reach` | `des.cli.verify_execution_reach` | ``des verify-execution-reach`` -- the P0.4 evidence-by-execution gate. |
| `verify-spec-coverage` | `des.cli.verify_spec_coverage` | ``des verify-spec-coverage`` -- the P3.2 spec-coverage gate. |
| `record-examine-verdict` | `des.cli.record_examine_verdict` | ``des record-examine-verdict`` -- the User-Examiner verdict PRODUCER (P1.2). |
| `mode-locus-gate` | `des.cli.mode_locus_gate` | mode-locus-gate — Layer-A guardrail (mode-registry-single-locus slice-05). |
| `mode-registry-completeness` | `des.cli.mode_registry_completeness` | mode-registry-completeness — Layer-B guardrail (mode-registry-single-locus slice-05). |
| `skill-normative-gate` | `des.cli.skill_normative_gate` | CLI driving port #1 for the skill-normative-content gate. |
| `wave-clear` | `des.cli.wave_clear` | des wave-clear -- the sanctioned operator command for clearing a wave floor. |
| `verify-declared-events` | `des.cli.verify_declared_events` | des verify-declared-events -- prose claims a ledger/event exists; does code emit it? |
| `gate-design-at-coherence` | `des.cli.gate_g` | gate-G — the mechanical design↔AT coherence gate (f-coherence-and-attestation slice-03). |
| `self-attest` | `des.cli.self_attest` | des self-attest -- the thin CLI driver over the self-attest verdict classifier. |
| `verify-test-runner` | `des.cli.run_tests` | des.cli.run_tests -- the TestRunnerPort CLI composition root (ADR-042). |
| `run-slice-ats` | `des.cli.run_slice_ats` | des run-slice-ats -- the slice-scoped EXECUTOR (THE ACCELERATION). |
| `verify-wave-contract-coherence` | `des.cli.verify_wave_contract_coherence` | verify-wave-contract-coherence — the git-free wave-contract coherence gate. |
| `record-design-review` | `des.cli.design_review_verdict` | DESIGN review verdict PRODUCER -- ``des record-design-review`` (slice-01). |
| `verify-design-review` | `des.cli.verify_design_review` | DESIGN review CONSUMER veto gate -- ``des verify-design-review`` (slice-01). |
| `record-devops-review` | `des.cli.devops_review_verdict` | DEVOPS review verdict PRODUCER -- ``des record-devops-review`` (slice-02). |
| `verify-devops-review` | `des.cli.verify_devops_review` | DEVOPS review CONSUMER veto gate -- ``des verify-devops-review`` (slice-02). |
| `verify-deliver-entry-contract` | `des.cli.verify_deliver_entry_contract` | verify-deliver-entry-contract — the DELIVER-entry contract-freeze gate. |
| `attest-bundled-slice` | `des.cli.attest_bundled_slice` | des-attest-bundled-slice -- attest a bundle-delivered carpaccio slice. |
| `dispatch` | `des.cli.dispatch` | des dispatch -- render a GATE-VALID atdd_pure dispatch prompt from the |
| `verify-catalog-coherence` | `des.cli.verify_catalog_coherence` | des verify-catalog-coherence -- registry <-> catalog <-> per-gate-file drift. |
| `check-contract-shape` | `des.cli.check_contract_shape_declarations` | des check-contract-shape -- mechanical Contract-Shape (Principle 11) check. |
| `charter-scaffold` | `des.cli.charter_scaffold` | des charter-scaffold -- the producing tool for expectation-charter scaffolds |
| `feature-end-preconditions-scaffold` | `des.cli.feature_end_preconditions_scaffold` | des feature-end-preconditions-scaffold -- the producing tool for the two |
| `blast-radius` | `des.cli.blast_radius` | des blast-radius -- the blast-radius measurement primitive (slice-02 complete). |
| `record-review-verdict` | `des.cli.record_review_verdict` | ``des record-review-verdict`` -- the general reviewer-verdict PRODUCER (#45). |
| `verify-charter-filled` | `des.cli.verify_charter_filled` | des verify-charter-filled -- the backstop gate for expectation-charter |
| `find-similar-responsibility` | `des.cli.find_similar_responsibility` | des find-similar-responsibility -- the observable CLI over the additive |
| `next` | `des.cli.next_step` | ``des next`` -- read-only advisory projection of the atdd_pure DELIVER loop. |
| `feature-open` | `des.cli.feature_open` | ``des feature-open`` -- create one evidence-aware initial feature context. |
| `examine-fixture` | `des.cli.examine_fixture` | des examine-fixture -- the producing tool for an examiner-drivable |
| `refactor` | `des.cli.refactor` | des refactor -- the fixer-swarm CLI (ADR-SWARM-001, des-refactor-fixer-swarm). |
| `work-exhausted-tick` | `des.cli.work_exhausted_tick` | des-work-exhausted-tick -- the wall-clock work-exhausted escalation ladder. |
| `bugfix-pipeline-tick` | `des.cli.bugfix_pipeline_tick` | des-bugfix-pipeline-tick -- the two-lane bugfix pipeline (D-4). |
| `consolidation-signal-tick` | `des.cli.consolidation_signal_tick` | des-consolidation-signal-tick -- trunk-health signal intake into the |
| `verify-worktree-cleanup` | `des.cli.verify_worktree_cleanup` | ``des verify-worktree-cleanup`` -- the mechanical worktree-cleanup gate. |
| `parallel-safety-report` | `des.cli.parallel_safety_report` | des parallel-safety-report -- advisory measured cross-check of a plan's |
| `plan` | `des.cli.delivery_plan` | `des plan` -- advisory ready-set and unused-parallelism report. |
<!-- GENERATED:des-command-catalog END -->
