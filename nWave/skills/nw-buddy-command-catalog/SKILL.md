---
name: nw-buddy-command-catalog
description: All /nw-* commands — what they do, when to use them, which agent they invoke. For the buddy agent to help users pick the right command.
user-invocable: false
disable-model-invocation: true
---

# Command Catalog

## Wave Commands (run in order per feature)

| Command | Wave | Agent | When to Use |
|---------|------|-------|-------------|
| `/nw-discover` | DISCOVER | product-discoverer (Scout) | Validate problem exists, customer interviews, opportunity mapping |
| `/nw-diverge` | DIVERGE | diverger (Flux) | Evaluate multiple solution approaches before committing |
| `/nw-discuss` | DISCUSS | product-owner (Luna) | Define user stories, journeys, acceptance criteria |
| `/nw-design` | DESIGN | system-designer, ddd-architect, solution-architect | Route to the right architect — system (scalability), domain (DDD), or application (components) |
| `/nw-devops` | DEVOPS | platform-architect | CI/CD, infrastructure, observability, deployment strategy |
| `/nw-distill` | DISTILL | acceptance-designer | Create executable acceptance tests (Given-When-Then) |
| `/nw-deliver` | DELIVER | software-crafter | Full implementation: roadmap -> execute -> finalize |

## Routing Commands

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/nw-new` | Guided wizard for new features | Starting something new — asks what you're building, recommends starting wave |
| `/nw-continue` | Resume in-progress feature | Returning to a feature — detects progress, starts at next wave |
| `/nw-fast-forward` | Run remaining waves without pausing | When you trust the agents to proceed without review between waves |

## DELIVER Inner Loop Commands (manual mode)

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/nw-execute` | Run single roadmap step | Implementing one step at a time (learning mode) |
| `/nw-review` | Expert review of artifacts | Quality check on roadmap, code, or step output |
| `/nw-mutation-test` | Test suite effectiveness (DEPRECATED, FR-1) | Opt-in only — NOT a default step. Deprecated 2026-07-04: green ATs + EXAMINE (Vera) are the truth; a post-green mutation pass adds cost, not signal. Run explicitly only when you specifically want a mutmut kill-rate. |
| `/nw-finalize` | Archive completed feature | After all steps pass — creates evolution document |

## Cross-Wave Commands (any time)

| Command | Agent | When to Use |
|---------|-------|-------------|
| `/nw-research` | researcher (Nova) | Investigate technologies, patterns, decisions needing evidence |
| `/nw-document` | documentarist + researcher | Create DIVIO-compliant documentation (tutorial, how-to, reference, explanation) |
| `/nw-diagram` | solution-architect | Generate C4 architecture diagrams (Mermaid/PlantUML) |
| `/nw-refactor` | software-crafter | Systematic refactoring using RPP levels L1-L6 |
| `/nw-bugfix` | troubleshooter + crafter | Root cause analysis -> regression test -> fix via TDD |
| `/nw-root-why` | troubleshooter | Root cause analysis (5 Whys) without fix |
| `/nw-hotspot` | (self) | Git change frequency analysis — find most-changed files |
| `/nw-rigor` | (self) | Set quality-vs-token profile (lean/standard/thorough/exhaustive) |
| `/nw-forge` | agent-builder (Zeus) | Create new specialized agents |
| `/nw-mikado` | software-crafter | Complex refactoring roadmaps with visual tracking (experimental) |
| `/nw-buddy` | buddy (Guide) | Ask any question about nWave — methodology, commands, project state |

## `des` Subcommands — the producing tools (NOT slash commands; run in a shell)

The `/nw-*` commands orchestrate waves. `des` is the runtime underneath them: the tools that
PRODUCE the artifacts the gates check. Reach for these instead of hand-building what a gate
verifies — every hand-edit of a checked artifact is a producing tool you did not invoke.

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `des blast-radius --repo . --paths <files>` | Measures a change's real reach — files, lines, boundary files, consumer counts — and classifies it S/M/L | BEFORE choosing how to do a piece of work. The line count is NOT the radius: a 2-line change to a symbol with 6 callers measures M. Errors degrade toward L, never silently toward S |
| `des commit --owned-paths <p...> --step-id <id> --message <m>` | **The SAFE commit when more than one agent shares the working tree.** Holds an exclusive lock AND builds from a temporary index containing only the owned paths | Whenever a sibling instance or a dispatched agent may be writing to the same tree. A bare `git commit` lets the second writer sweep up files the first had staged — measured 8 work-losses in one day |
| `des commit-slice ...` | Correct-by-construction slice commit: stages, stamps the `Slice-Id` and `Gate-Scope` trailers, folds in verify-then-record | Committing a delivered slice. Never hand-add a Gate-Scope trailer |
| `des examine-fixture --out <dir>` | Builds a real, drivable repository the certification gate accepts, with slices flippable red/green by editing one line | Before dispatching an examiner (Vera): she cannot read source, so she needs a surface she can REACH and BREAK. Do not hand-build one |
| `des record-examine-verdict ...` | Records the examiner's charter-sealed verdict | After an examine, before the commit. A PASS carrying ≥1 flag is refused mechanically — the orchestrator does not get to decide |
| `des verify-red-green --record-red --test-file <f>` | Seals the observed RED, bound to the file's current CONTENT | After the ATs are authored and failing. Editing the file afterwards VOIDS the seal — re-run it |
| `des dispatch --mode atdd_pure --project-id <id> --slice <s> --phase <p>` | GENERATES a compliant agent dispatch with its mandatory sections | Dispatching a crafter or reviewer. Hand-assembling the prompt is how a mandatory section goes missing | <!-- mode-ref-ok -->
| ⚠️ `des next --feature-id <id>` | Projects the next legal step in the DELIVER loop | **PARTIAL — do not treat as authoritative.** It reads the markdown Status column, not the ledger. When it disagrees with `.nwave/telemetry/atdd-pure/<id>.jsonl`, believe the LEDGER, and never auto-run the `how` it prints |
| `des refactor --pile <path> --agent-cmd '<cmd>' [--max-parallel N]` | Drains tech-debt items from a pile file (`techdebt.md` -> `paidtechdebt.md`), one item per isolated worktree+venv, with mandatory cleanup on success or failure | "My code needs cleanup" at scale — a hand-authored pile, not a single ad-hoc refactor (`/nw-refactor` for that). ⚠️ `--driver loop` is a known stub (parsed, never wired) — omit it, the default `python` driver is the only one that actually runs today. `des find` (auto-populating the pile) does not exist yet |
| `des bugfix-pipeline-tick` / `des work-exhausted-tick` / `des consolidation-signal-tick` | The three autonomous-loop driving ports (bugfix pipeline, safe-work exhaustion escalation, trunk-health signal intake) | Debugging or manually draining the autonomous loop — normally auto-ticked once per SessionStart, no manual invocation needed for steady state |

> For the full authoritative command reference, read `docs/reference/commands/index.md`.

## Common User Scenarios -> Command

| User Says | Recommend |
|-----------|-----------|
| "I want to build something new" | `/nw-new` (wizard) or `/nw-discover` (if problem unclear) |
| "I'm not sure which approach to take" | `/nw-diverge` |
| "I need user stories for this feature" | `/nw-discuss` |
| "How should I architect this?" | `/nw-design` |
| "I need to set up CI/CD" | `/nw-devops` |
| "I need acceptance tests" | `/nw-distill` |
| "I'm ready to implement" | `/nw-deliver` |
| "I want to continue my feature" | `/nw-continue` |
| "I need to research X" | `/nw-research` |
| "I need documentation" | `/nw-document` |
| "Something is broken" | `/nw-bugfix` or `/nw-root-why` |
| "My code needs cleanup" | `/nw-refactor` |
| "How good are my tests?" | EXAMINE (Vera, `nw-user-examiner`) is the truth — green ATs + independent end-to-end examine. (`/nw-mutation-test` is DEPRECATED/opt-in, FR-1.) |
