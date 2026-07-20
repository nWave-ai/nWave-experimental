# CLAUDE.md — nWave Developer Experience System

## 🔥 LYRA-DEV MANDATE (this repo, this Claude instance) — PRIORITÀ MASSIMA, marchiato-a-fuoco 2026-05-24

**Il mio compito è il SUCCESSO di nWave OSS, NON di SF.** (Ale 2026-05-24, post YAML-pipeline-composition retraction.)

- **Scope**: T1 OSS (nwave-dev = this repo) publish-target ≥90% PRR + hook-only spine stabilization
- **Out-of-scope**: T2 SF (closed-source proprietary, sister Lyra-SF mandate) + T3 Tsunami (closed-source, sister Lyra-Tsunami mandate)
- **Cross-tree relay**: SERVICE function ONLY, NOT primary objective. Exchange surface = skills + agents + workflows + detector-taxonomy. NEVER source code, gate config, sequencer YAML, or any IP-disclosing impl per [[feedback_oss_sf_ip_separation_directive_2026_05_24]].
- **Architecture invariant**: OSS = hooks (no sequencer, no engine at runtime — Ale STANDING "nwave-dev no sequencer no engine, SOLO hooks"). Mimicking SF architectural patterns (YAML state-machine compose, sequencer interpretation) is IP-blind import + standing-violating.
- **Mandate-check protocol**: before any architectural proposal, ask "OSS-scope? hook-compatible? importing SF mental model?". If any answer suggests SF-import or SF-scope, REFRAME or RETRACT.

**Memory anchors** (must be loaded before any architectural decision):
- `~/.claude-alt/projects/-home-alexd-Projects-nWave-dev/memory/feedback_mandato_oss_non_sf_2026_05_24.md` — this rule, full text
- `~/.claude-alt/projects/-home-alexd-Projects-nWave-dev/memory/feedback_oss_sf_ip_separation_directive_2026_05_24.md` — 3-tier IP framework
- `~/.claude-alt/projects/-home-alexd-Projects-nWave-dev/memory/feedback_atdd_pure_stabilization_max_priority_2026_05_24.md` — atdd_pure stabilization (applies WITHIN OSS tier)

**Anti-pattern caught 2026-05-24** (2 incidents in single afternoon):
1. Q-40 bias-(a) hook-only-as-convergence-target → IP-blind, retracted Q-50
2. F-ATDD-PURE-GATE-YAML-PIPELINE-COMPOSITION proposal → SF mental model import + violates OSS hook-only standing, retracted

If 3rd same-class incident occurs: pause, reload anchors, framing-attack on self before continuing.

**Cross-instance memory contamination caveat**: sisters share memory via symlink. Memory files like `feedback_lyra_mandate_*_success_*.md` may be authored by other instances (Lyra-SF, Lyra-Tsunami) and apply ONLY to their scope. ALWAYS identify instance scope before applying. This instance = Lyra-DEV → OSS mandate ONLY.

---

## What is nWave?

nWave is an AI-powered workflow framework that orchestrates specialized Claude AI agents through disciplined software development waves. It runs inside Claude Code, enforcing TDD, phase tracking, and deterministic validation at every step.

**Core mission**: Replace ad-hoc AI coding with a structured, auditable, wave-based methodology — from discovery to deployment.

**Two packages**:
- `nwave` (this repo, private) — development, full source, CI/CD
- `nwave-ai` (public, PyPI via `nwave-ai/nwave` repo) — installer CLI for end users

---

## 📏 OBJECTIVE PROGRESS MEASUREMENT — `flow-v2-wave-migrations` closure (STANDING, marchiato 2026-06-15)

**The measurement of "is the epic done" is CODE, not Lyra's word.** Ale 2026-06-15, after repeated "done/implemented" claims turned out not-exactly-true (the goal felt like it kept moving because it was anchored to my assertion, not a verifiable criterion).

- **The measure IS `scripts/flow_v2_closure_scorecard.py` — Ale ratified it as THE GOAL CONTRACT (2026-06-15).** Run it — don't re-derive by hand: `uv run python scripts/flow_v2_closure_scorecard.py` (`--with-suite` also runs pytest). Same committed code + same repo state → same number, by construction. Baseline 2026-06-15 = **EPIC 0/10 features DONE**.
- **UNIT = the FEATURE, inside the EPIC** (a slice is too fine — it excludes not-yet-designed work and hides the moving goal). Hierarchy EPIC → FEATURE → SLICE. Every known feature is in the denominator from day one, INCLUDING undesigned ones (phase `to-design`); the denominator grows only if we DISCOVER new work, never shrinks to hide known work.
- **Definition of DONE (anti-overstatement contract)**: a FEATURE is DONE iff a `FeatureEnd` ledger record attests it (that gate internally requires all slices delivered + full suite green + env-e2e + coverage + — for feature-with-modules — modules WIRED into a live hook/flavor gate-stack). NEVER "module exists + ATs green"; **catalogued ≠ wired** (the catalog is the registry, not a firing surface — the iter-1 scorecard bug, fixed). A delivered-but-unattested feature is NOT done. Code committed with `--no-verify` (no `SliceCommitVerified`) is NOT attested → NOT done.
- **Rule for me**: NEVER say "done/implemented/working" for an item without showing the scorecard check output that PASSes. If the measure must change, it is a reviewed git diff to the script (the metric cannot drift silently); the script is fail-closed (unknown/error = FAIL) and is itself §22.0-reviewable.
- SSOT of the closure inventory + sequence: `docs/epic/flow-v2-wave-migrations/RESUME.md §-0.1` + backlog `F-FLOW-V2-EPIC-HONEST-CLOSURE`. See [[feedback_objective_committed_scorecard_not_lyra_word_2026_06_15]].

---

## Repository Topology (three channels, one source)

This is the canonical truth about what is public vs private. Do not infer from filenames — follow the matrix below.

| Channel | What | Visibility | Example paths |
|---------|------|------------|---------------|
| **nWave-dev** (this repo) | Full development environment — source, tests, CI, dev tooling, internal docs, all agents (public + private) | **PRIVATE** (github.com/nWave-ai internal org) | everything you see in `/home/alexd/Projects/nWave-dev` |
| **nWave prod** (github.com/nWave-ai/nWave) | Public-facing source mirror — open-source subset synced from this repo at release time by `release-prod.yml:sync-public`. Strips private agents via `scripts/release/strip_private_agents.py` (fail-closed by catalog), removes `docs/analysis/`, `docs/internal/`, `.github/`, `nWave/checklists/`, caches | **PUBLIC** (open source) | `src/des/`, `scripts/install/`, `scripts/release/`, `nWave/` (public agents only), `nwave_ai/`, `tests/`, `docs/guides/`, `docs/reference/`, `CONTRIBUTING.md`, `LICENSE`, `PRIVACY.md` |
| **nwave-ai** (PyPI wheel) | Minimal installer CLI — `pipx install nwave-ai` entry. Built from the public tree with minimized payload via `patch_pyproject.py` | **PUBLIC** (PyPI, MIT-licensed) | `nwave_ai/` + a narrow force-include subset |
| **nWave-hardening** (worktree `~/Projects/nWave-hardening/`, branch `des-hardening`) — also known as "software factory" | Closed-source enterprise track: DES 3.0 dispatch layer, expectations engine, hardening agents. Never merged to master of this repo | **CLOSED SOURCE** (commercial) | `feature/des-hardening` branch artifacts; never reference from master commits |

### What is open vs closed — the simple rule

- **Open**: everything that lands on `nWave-ai/nWave` after the release rsync. That includes `src/des/` (DES runtime source, open), `scripts/install`, `scripts/release`, `scripts/hooks`, the framework catalog's **public** agents+skills, and user-facing docs.
- **Private (but not closed-source)**: internal analysis docs (`docs/analysis/`, `docs/internal/`), checklists, CI workflow internals (`.github/`), non-public agents (flagged `public: false` in `framework-catalog.yaml`), plus every cache/artifact directory.
- **Closed source**: only the nWave-hardening track lives here. Not in this repo's master branch. See `feedback_branch_isolation.md` / `feedback_no_des_hardening_on_master.md` for the hard rule: **zero references** to DES 3.0, CPE, dispatch layer, expectations engine, or the hardening worktree in any master commit.

### Wheel vs GitHub (for `nwave-ai`)

The **GitHub repo** `nWave-ai/nWave` ships the full open-source tree (source, tests, scripts, docs). The **PyPI wheel** `nwave-ai` is the *install-time-only* subset: the packaged `nwave_ai/` Python module plus the minimum `scripts/install`, `scripts/shared`, `nWave/` assets, and pre-built `lib/python/des/`. Source browsing/forking goes through GitHub — not through `pipx show nwave-ai -v`. When a file appears both on GitHub and in the wheel, it is double-distribution (not a privacy issue but a packaging-bloat concern).

### Release sync rules (for reference)

- `.github/workflows/release-prod.yml:sync-public` does `rsync -avL --delete` from this repo to the public target with explicit excludes: `.github/`, `docs/analysis/`, `docs/internal/`, `nWave/checklists/`, plus caches and bookkeeping files. `docs/*` excluded by default; only `docs/guides/` and `docs/reference/` explicitly included.
- `scripts/release/strip_private_agents.py` then filters the public tree against the catalog's `public: true` allow-list (fail-closed: anything uncatalogued is stripped).
- `scripts/release/patch_pyproject.py` then rewrites `pyproject.toml` for the `nwave-ai` PyPI build, defining a narrow Hatch `force-include` map that controls exactly which paths enter the `.whl`.

**If something is leaking where it shouldn't** (e.g. private agent in public repo, unused script in the PyPI wheel), the fix path is usually: (a) update `framework-catalog.yaml` `public:` flags, (b) tighten rsync excludes, or (c) narrow `patch_pyproject.py` force-include. Do not modify the tests that guard these contracts.

### Repository topology — separation contract (2026-05-15)

Ale 2026-05-15 directive: **nwave-dev and nwave-software-factory are two independent repos**, each with own `.git/`, own origin remote. Worktree-sharing era pre-split (2026-04-09 to 2026-05-15) is decommissioned.

**Hard invariants enforced mechanically**:

1. **Origin URL contract** — this repo's `origin` MUST be `git@github.com:nWave-ai/nwave-dev.git`. Verified by `.git/hooks/pre-push` repo-separation guard (blocks pushes to URLs containing `nwave-software-factory`).
2. **`.git/` independence** — no `git worktree` shared with nwave-software-factory. Each repo has own `.git/`.
3. **No cross-tree code leak** — nwave-dev MUST NOT contain DES 3.0 / CPE / dispatch layer / expectations engine / license_runtime / cost-efficiency-determinism modules. Shared canonical agents+skills DO span both repos by design (most are non-IP-sensitive methodology assets).
4. **Memory rule reinforcement** — `feedback_target_machine_independence_2026_05_15.md` + `feedback_branch_isolation.md` + `feedback_no_des_hardening_on_master.md` enforce zero references to closed-source artifacts in master commits.
5. **CI/release pipeline filters** — release-prod.yml rsync `--exclude 'docs/*'` (catch-all) + framework-catalog `public:` flag + `patch_pyproject.py` force-include narrow gate. Pipeline already filters non-public docs; only `docs/guides/` + `docs/reference/` are public.

**Workflow going forward**:

- nwave-dev work → push `git@github.com:nWave-ai/nwave-dev.git`
- nwave-software-factory work → done in sibling repo `~/Projects/nWave-software-factory/` (sister Lyra), origin = `git@github.com:nWave-ai/nWave-software-factory.git`
- v3.15.0 PyPI release: cosmetic leak detected post-publish (2 references in `nWave/skills/nw-tdd-methodology/SKILL.md`, shared content per Ale, scrubbed via commit `3ab776967`). Re-evaluated as operational data, NOT IP disclosure. Routine 3.15.1 supersede planned.

**Origin story**: 2026-04-09 → 2026-05-15 worktree-shared period mixed histories on nwave-dev remote. ~7 SF-only branches (feat/contract-architecture-test-directive-followup, determinism, feature/bas-core, feature/wave-events-projection-discuss, feature/prism-event-emission-completeness, feature/wave-lang-r1, wt-framework-rationalization-p6-exec) await branch cleanup epic #55.

---

## Project Structure

```
nWave-dev/
├── nWave/                    # Framework definition (agents, commands, skills, templates)
│   ├── agents/               # 23 agent specifications (YAML frontmatter + markdown)
│   ├── tasks/nw/             # 21 slash command definitions (/nw-deliver, /nw-design, etc.)
│   ├── skills/               # 98 agent skill files (deep domain knowledge)
│   ├── templates/            # Methodology templates (TDD schema, pre-commit, README)
│   ├── data/                 # Configuration data, methodologies, research references
│   ├── hooks/                # Agent lifecycle hooks
│   ├── framework-catalog.yaml  # Central metadata registry (agents, commands, quality gates)
│   └── VERSION               # Framework version (synced from pyproject.toml)
│
├── src/des/                  # DES runtime (Deterministic Execution System)
│   ├── domain/               # Business logic (phase events, turn counter, timeout, policies)
│   ├── application/          # Use cases (orchestrator, validators, services)
│   ├── ports/                # Interfaces (driver + driven ports)
│   └── adapters/             # Implementations (hooks, filesystem, config, logging, git)
│
├── nwave_ai/                 # Public CLI package (thin wrapper)
│   └── cli.py                # Entry: install, uninstall, version commands
│
├── scripts/
│   ├── install/              # Installation pipeline
│   │   ├── plugins/          # Plugin system (agents, commands, DES, skills, templates, utilities)
│   │   ├── install_nwave.py  # Main installer orchestrator
│   │   ├── preflight_checker.py
│   │   └── installation_verifier.py
│   ├── hooks/                # Pre-commit hook scripts (all Python, zero shell)
│   ├── framework/            # Build utilities (sync names, create tarballs, docgen)
│   ├── validation/           # YAML & frontmatter validators
│   └── build_dist.py         # Distribution builder
│
├── tests/                    # 5-layer test suite
│   ├── des/                  # DES tests (unit/, integration/, acceptance/, e2e/)
│   ├── installer/            # Installer tests (unit/, acceptance/, e2e/)
│   ├── plugins/              # Plugin system tests
│   ├── bugs/                 # Regression tests
│   ├── build/                # Build script tests
│   └── conftest.py           # Root fixtures, auto-marking by directory
│
├── docs/
│   ├── guides/               # Tutorials and how-tos (public)
│   ├── reference/            # Auto-generated API/command reference (public)
│   ├── architecture/         # ADRs, design decisions (public)
│   └── analysis/             # Internal analysis (EXCLUDED from public sync)
│
├── .github/workflows/
│   ├── ci.yml                # 4-stage CI (lint → validate → test → sync)
│   └── release.yml           # 5-job release (bump → build → release → sync → pypi)
│
└── pyproject.toml            # Single source of truth for versions and tool config
```

---

## Architecture: DES (Deterministic Execution System)

DES follows **hexagonal architecture** (ports & adapters):

```
Claude Code Hooks (pre-tool-use, subagent-stop, post-tool-use)
        │
        ▼
┌─ Adapters (drivers) ──────────────────────────────────────┐
│  claude_code_hook_adapter.py  →  JSON hook protocol        │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Application Layer ───────────────────────────────────────┐
│  DESOrchestrator       — prompt rendering, phase execution │
│  PreToolUseService     — validates before Agent invocation │
│  SubagentStopService   — validates after sub-agent returns │
│  TemplateValidator     — checks 9 mandatory sections       │
│  StaleExecutionDetector — detects abandoned phases         │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Domain Layer ────────────────────────────────────────────┐
│  PhaseEvent, TurnCounter, TimeoutMonitor, TDDSchema       │
│  DES enforcement policies, Result<T,E> types              │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Ports (driven) ──────────────────────────────────────────┐
│  FileSystemPort, ConfigPort, TimeProvider, AuditLogWriter  │
│  LoggingPort, TaskInvocationPort                           │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Adapters (driven) ───────────────────────────────────────┐
│  RealFileSystem, EnvironmentConfigAdapter, SystemTimeProvider│
│  JsonlAuditLogWriter, GitCommitVerifier                    │
│  (+ in-memory/null variants for testing)                   │
└────────────────────────────────────────────────────────────┘
```

**TDD 3-Phase Canon** (ADR-025, 2026-05-07):
1. RED — unskip the acceptance test scaffold authored by DISTILL (fail-for-right-reason gate: collected ≥ 1, failures ≥ 1, semantic AssertionError); write PBT unit tests ONLY when the AT cannot reach GREEN without them. DISTILL retains canonical AT authorship — DELIVER does NOT re-author ATs.
2. GREEN — minimal implementation to make AT + any RED-authored unit tests pass.
3. COMMIT — refactor, stage, conventional commit with `Step-Id:` trailer. No regressions.

**Legacy 5-Phase Contract** (ADR-024 era, schema `step-tdd-cycle-schema.json` v4.0 — preserved for audit-log replay of pre-2026-05-07 commits):
1. PREPARE — setup test fixtures
2. RED_ACCEPTANCE — write failing acceptance test
3. RED_UNIT — write failing unit tests
4. GREEN — implement until all tests pass
5. COMMIT — refactor, finalize, no regressions

References to RED_ACCEPTANCE / RED_UNIT in existing execution logs describe the legacy contract; new work treats them as merged inside RED.

---

## Key Files (Quick Reference)

| File | Purpose |
|------|---------|
| `pyproject.toml` | Version, dependencies, tool config (THE source of truth) |
| `nWave/framework-catalog.yaml` | Agent/command/quality-gate registry |
| `nWave/VERSION` | Framework version (synced from pyproject.toml) |
| `src/des/application/orchestrator.py` | DES core orchestration (1,086 lines) |
| `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py` | Hook entry point |
| `scripts/install/plugins/des_plugin.py` | DES installation plugin (core complexity) |
| `scripts/install/install_nwave.py` | Main installer orchestrator |
| `nwave_ai/cli.py` | Public CLI entry (`install`, `uninstall`, `version`) |
| `.releaserc` | Semantic-release config (branches, plugins) |
| `tests/conftest.py` | Root test config, auto-markers, fixtures |
| `scripts/docgen.py` | Documentation generator from frontmatter |

---

## Development Commands

```bash
# Setup (one-time per clone)
uv sync                                    # Install project + dev group (PEP 735)

# Testing
uv run poe test                            # All tests
uv run poe test-des-unit                   # DES unit tests only
uv run poe test-unit                       # All unit tests
uv run poe test-not-slow                   # Skip slow tests
uv run poe test-coverage                   # With coverage (fail_under=60)

# Linting & Formatting
uv run poe lint                            # Lint (ruff check src/ scripts/ tests/)
uv run poe format                          # Format (88 chars, double quotes)
uv run poe typecheck                       # Type check (mypy src/des/, strict mode)

# Pre-commit hooks
uv run pre-commit run --all-files          # All hooks
uv run pre-commit run --hook-stage pre-push # Push-time hooks only

# Build & Install
uv run poe build                           # Build distribution
uv run python -m nwave_ai.cli install      # Install nWave locally

# Documentation
uv run poe docgen                          # Regenerate reference docs

# Mutation testing
uv run poe mutation-test                   # Run mutation tests
```

> Task aliases live in `[tool.poe.tasks]` (`pyproject.toml`); run `uv run poe` to list them. See [ADR-PLAT-004](docs/product/architecture/ADR-PLAT-004-uv-dev-workflow.md) for the pipenv→uv decision.

### Work-progress dashboard (visual status — the Jira alternative)

A self-contained HTML dashboard of the backlog SSOT — To Do grouped by derived epic-theme and ordered by urgency (Critical→Low), master/detail (click an item → full description), In-Progress + Done-this-session. Published as a claude.ai Artifact (shareable link, no Jira board/cache friction). Regenerate in two steps:

```bash
uv run python scripts/backlog_to_jira_csv.py          # 1. refresh the data CSV from backlog.md
uv run python scripts/gen_status_dashboard.py <out.html>   # 2. render the HTML (default: docs/analysis/nwave-status.html)
```

Then publish `<out.html>` via the Artifact tool (same file path redeploys to the same URL). Epics are DERIVED thematically by keyword in `gen_status_dashboard.py:EPICS` (the backlog has no formal epic field yet — edit that map to retune the grouping). Priority comes from the backlog `## Critical/High/Medium/Low` section. The Jira mirror (`scripts/backlog_to_jira_sync.py`, WTBD board) is the other view — it sets the priority field + reranks the To Do column by priority via the Agile API; run it with `~/.nwave/jira-mirror.env` sourced.

---

## Development Paradigm

object-oriented

Rationale: hexagonal architecture (`src/des/{domain,application,ports,adapters}/`), heavy use of dataclasses + ABC + dependency injection via constructor. Crafter dispatch defaults to `@nw-software-crafter`.

## Mutation Testing Strategy

DEPRECATED (FR-1, Ale 2026-07-04)

Mutation testing (mutmut) is a slow, deprecated post-green ceremony REMOVED from the velocity-v2 methodology — green ATs + EXAMINE (independent end-to-end verification) are the truth, and a coverage-after-green / mutation pass adds cost, not signal (see FR-1/FR-2/FR-3 in `docs/product/velocity-v2-progress-tracker.md`). `.nwave/des-config.json` keeps `mutation_enabled=false`; the `mutation-test` poe task remains available for an explicit, opt-in run only — it is NOT part of any per-feature or nightly gate. Do not run it as a default step.

## Conventions

### Commits
- **Conventional commits required**: `type(scope): subject`
- Types: `feat` (minor), `fix`/`perf`/`refactor` (patch), `docs`/`test`/`ci`/`chore` (no release)
- `BREAKING CHANGE:` in body/footer triggers major bump
- Enforced by: gitlint (commit-msg hook) + commitlint (CI)
- **gitlint hard limits — get these right the FIRST time (no wasted retries):**
  - **T1 — subject ≤ 100 chars** (the whole `type(scope): subject` line). Long scope names (e.g. `f-wave-contract-coherence`) eat the budget — keep the subject terse.
  - **B1 — every body line ≤ 120 chars.** WRAP the body; never write one long paragraph-line. Blank line between subject and body.
  - Note: `—` (em-dash) and other multibyte chars count toward the char limit — prefer `-`/`(...)`.
  - `des commit-slice` appends the `Gate-Scope:` trailer mechanically (a ~76-char line, gitlint-safe) — do NOT hand-add one. Slice commits carry a `Slice-Id: slice-NN` trailer.

### Versioning (Two-Track)
- **nwave-dev** (this repo): semantic-release from conventional commits (`v2.17.5`)
- **nwave-ai** (public): auto-bumped patch from `public_version` floor in `[tool.nwave]` (`1.1.0`)

### Code Style
- Python >= 3.10, type hints everywhere (mypy strict)
- Ruff v0.15.20: line length 88, double quotes
- Naming: snake_case (functions/vars), PascalCase (classes), UPPER_SNAKE (constants)
- Docs: kebab-case filenames
- Zero shell scripts policy — all hooks in Python

### Testing (5-Layer Framework)
1. **Unit** — fast, isolated, one concern per test (pre-commit)
2. **Integration** — components with real resources (pre-push)
3. **Acceptance** — BDD Given-When-Then scenarios (pre-push)
4. **E2E** — complete workflows end-to-end (pre-push)
5. **Mutation** — test suite effectiveness validation (manual/CI)

Markers auto-applied by `conftest.py` based on directory path.

### Plugin System
Installation uses a plugin registry with topological dependency resolution:
- `base.py` — `InstallationPlugin` ABC, `InstallContext`, `PluginResult`
- Each plugin: `validate_prerequisites()` → `install()` → `verify()`
- DES plugin uses `$HOME` in hook commands for portability (never `.venv/` paths)
- Import rewriting: `from src.des` → `from des` at install time

---

## CI/CD Pipeline

### CI (`.github/workflows/ci.yml`) — Every push/PR
| Stage | Jobs | Duration |
|-------|------|----------|
| 1. Fast checks | commitlint, code-quality, file-quality, security | ~1 min |
| 2. Framework validation | catalog schema, version consistency, docs freshness | ~1 min |
| 3. Cross-platform tests | Ubuntu × Python 3.11/3.12 matrix | ~10 min |
| 4. Agent sync | Verify agent name synchronization | ~1 min |

### Release (`.github/workflows/release.yml`) — Manual dispatch or tag
1. **version-bump** — semantic-release calculates next version
2. **build** — `build_dist.py`, tarballs, SHA256SUMS
3. **github-release** — changelog from commits, GitHub Release + assets
4. **publish-to-nwave** — rsync to `nwave-ai/nwave`, auto-bump public version
5. **publish-to-pypi** — wheel build, twine publish, smoke test

Slack notifications on failure (RED) and recovery (GREEN).

---

## Wave Methodology

The canonical development sequence (7 waves, 5 optional upstream, mandatory floor DISTILL→DELIVER):

```
DISCOVER(opt) → DIVERGE(opt) → DISCUSS(opt) → DESIGN(opt) → DEVOPS(opt) → DISTILL → DELIVER
```

| Wave | Command | Agent | Output | Mandatory |
|------|---------|-------|--------|-----------|
| DISCOVER | `/nw-discover` | product-discoverer | Evidence, opportunity validation | Optional |
| DIVERGE | `/nw-diverge` | diverger | Design directions, competitive analysis | Optional |
| DISCUSS | `/nw-discuss` | product-owner | User stories, acceptance criteria | Optional |
| DESIGN | `/nw-design` | solution-architect | Architecture, component boundaries | Optional |
| DEVOPS | `/nw-devops` | platform-architect | Infrastructure, CI/CD, deployment | Optional |
| DISTILL | `/nw-distill` | acceptance-designer | BDD test scenarios (Given-When-Then) | **Mandatory** |
| DELIVER | `/nw-deliver` | software-crafter | Working code via Outside-In TDD | **Mandatory** |

> **DESIGN skip is NOT a self-serve default — the default is DESIGN RUNS; skipping requires explicit HUMAN authorization (ask).** (Ale 2026-07-19.) "Optional" means a human MAY authorize skipping the wave for a given feature — it does not license the spine/agent to skip it unilaterally. For a FEATURE, DESIGN runs by default; emitting a `## Wave: DESIGN / [REF] Design Skipped` witness is an AUTHORIZATION act, and per asymmetric-authority (controls veto, only humans authorize) it must be human-granted on ask, NEVER self-authored by the agent. A self-written skip witness is a violation — ASK before skipping. (Same discipline applies to any upstream-wave skip that pushes named decisions downstream.)

**Cross-wave agents**: researcher, troubleshooter, documentarist, test-optimizer, security-analyst, agent-builder, workshopper (diagrams are produced via the `/nw-diagram` command, owned by the solution-architect — there is no separate visual-architect agent)
**Reviewers**: 11 peer review agents (one per specialist + specialized reviewers)

**Deprecation**: SPIKE was a canonical wave phase prior to v3.16.0 and is now deprecated. Spike/analysis work is embedded in the DESIGN wave. The `/nw-spike` command remains for backward compatibility.

---

## Important Gotchas

- **Version source of truth**: `pyproject.toml:project.version` — everything else is synced
- **`docs/analysis/`**: Internal only, excluded from public repo sync via rsync rules
- **DES hook commands**: Use `$HOME` shell variable, never hardcoded paths
- **Pre-commit hooks**: Will block commits with failing tests, stale docs, or bad formatting
- **Plugin install rewrites imports**: `from src.des` becomes `from des` for standalone operation
- **No shell scripts**: Cross-platform policy enforced by pre-commit hook
- **Coverage threshold**: 60% minimum (will fail CI if below)
- **Ruff version pinned**: v0.15.20 in `pyproject.toml` `[dependency-groups]` (the single source of truth). CI sources the version from there (`.github/workflows/ci.yml` code-quality job) and the pre-push `autofix-python` hook uses the venv ruff — so a bump to the pyproject pin propagates everywhere automatically; do not hardcode a ruff version elsewhere
- **Script distribution is whitelist-only**: Only scripts listed in `UTILITY_SCRIPTS` in `build_dist.py` are shipped to users. Everything else in `scripts/` stays in the repo. Check the whitelist before assuming a script will or won't be distributed.

---

## Architectural Constraints (STANDING — marchiati 2026-05-31)

These are hard, non-negotiable constraints. Violations are tech-debt tracked in [`ARCH_TECH_DEBT.md`](ARCH_TECH_DEBT.md). Re-read before any gate/wave/design proposal.

### Gate Design Principles — GDP-1..7 (STANDING, Ale 2026-07-07)

The design contract EVERY gate must satisfy. Audit every gate against this checklist; a gap is a plan item to correct that gate.

- **GDP-1 — Intercept EARLY (timing).** Fire at the earliest point the defect is detectable — BEFORE the effort it guards is spent and the value delivered. A gate that fires after delivery only COMMENTS, it cannot prevent. Efficacy ladder: **proactive-inline ≫ reactive-before-completion ≫ advisory-after-completion**.
- **GDP-2 — Proactive INLINE affordance.** Pair the reactive gate with guidance inline at the authoring surface, so the block is rarely reached — a gate that fires is already too late to teach. Keep the gate, ADD the inline guidance.
- **GDP-3 — Self-explaining (WHAT/WHY/HOW).** Every rejection states WHAT failed, WHY, and HOW to fix — directly, no investigation needed. A bare `FAILED`/exit-code is itself a defect.
- **GDP-4 — The HOW invokes the PRODUCING TOOL.** The HOW routes to the system tool that produces the valid artifact (`des dispatch`, `des feature-delta-doctor`), never manual repair. No producing tool yet → the gate is the signal to build one (M2).
- **GDP-5 — Cost on the SYSTEM.** The system produces/generates the checked artifact (hook injects / script generates / gate verifies); the operator never hand-assembles it. System-pays = capability; operator-pays = ceremony. The fix relocates the production, never removes the check.
- **GDP-6 — Reliability: NO silent-wrong.** Degrade-LOUD / INDETERMINATE, never false-green nor silently-wrong. Silent-wrong destroys trust worse than loud-fail; fix correctness before pushing adoption.
- **GDP-7 — Agnostic + execution-observing.** Python-only / language-agnostic (no `git`/tool hard-dep in gate logic — behind an optional degrade-loud port); where it can, OBSERVE real execution (the fixed floor), not merely asserted state.

### Spine-driven dispatch — NEVER bare-invoke an agent (Ale 2026-06-21)

- **NEVER invoke an agent directly without explicit HUMAN permission — epic & feature
  implementation MUST be driven through the SPINE (Ale 2026-06-21; the bare-dispatch error
  cost ~500k tokens).** Do NOT call `Agent(...)` / Task on ANY agent (architect, PO,
  acceptance-designer, crafter, reviewer, researcher) unless Ale has explicitly granted it
  for that dispatch. **Epic and feature work is driven through the spine** — the
  wave-execution mechanism invoked via the `/nw-*` wave commands (`/nw-discuss` ·
  `/nw-design` · `/nw-distill` · `/nw-deliver`), which run the wave WITH its mandated
  anti-drift sections + gates (reuse-first, C4, the `[REF]` sections, wave-decision
  reconciliation, the review gate). A bare-agent dispatch skips exactly that discipline —
  the very sections whose absence causes architectural drift. In the bootstrap "the spine"
  = the installed nWave `/nw-*` methodology (contamination-free, never OSS source); the SF
  engine being built becomes the spine for its own future features.

### Generality & target-machine agnosticism — depend ONLY on Python

- **The only runtime dependency is Python.** nWave gates and waves must run on any target machine with Python 3.10+ and nothing else assumed present.
- **`git` (and every other external CLI tool) is NOT a dependency.** Gates and waves **MUST NOT** require `git`, `gh`, `curl`, `shasum`, etc. to function. Anything language- or tool-bound must be extracted behind a port + per-language/per-tool plugin (the genericità/agnosticismo mandate). A gate that shells out to `git` to do its job is a portability violation, not an implementation detail.
  - Corollary: gate/wave **logic** is Python + filesystem only. Where git/tool data is genuinely needed (e.g. commit verification), it must sit behind an optional driven-port adapter that degrades loudly (INDETERMINATE, never silent-pass) when the tool is absent — never a hard requirement baked into the gate.
  - This extends ADR-PLAT-001 (pure-Python deps for install) to the **runtime gate/wave layer**, and operationalizes `[[feedback_target_machine_independence_2026_05_15]]` + the genericità mandate `[[feedback_language_adapter_plugin_architecture_2026_05_24]]`.
- **Mechanical enforcement of gates is Python-only, git-free, cross-OS, language-agnostic** (filesystem snapshot + per-language AST adapter port), per the AT-as-specification mandate.

### ADR SSOT — one canonical folder for permanent ADRs

- **Permanent/active platform ADRs live in exactly one folder: `docs/product/architecture/`** (per `docs/architecture/adr-ssot-document-model.md` §Model, line 36). Do not create new permanent ADRs under `docs/adrs/` or `docs/architecture/` (those locations are being consolidated; see AD-20 in ARCH_TECH_DEBT.md).
- **Feature-local design ADRs stay with their feature** (`docs/feature/{id}/design/adrs/...`) — they are delta, not SSOT, and are NOT consolidated.
- **Archived ADRs** (`docs/archive/.../adrs/...`) are frozen historical records — never moved or renumbered.
- ADR numbers are an SSOT join-key — they must be globally unique within the permanent folder (no two `ADR-001`).
