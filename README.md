# nWave — atdd_pure Preview (Experimental Channel)

> ⚠️ **EXPERIMENTAL — NOT RECOMMENDED FOR PRODUCTION**
>
> - **Breaking changes are expected.** The API, wave structure, and command behavior may change without notice. Use only for evaluation and feedback, not in production systems or critical projects.
> - **No PyPI on this channel.** This preview is not published to PyPI. You install **locally from this clone**.
> - **Token usage is materially higher than a plain coding session.** This preview runs delivery in parallel (see *Parallel delivery*, below) — concurrent lanes mean concurrent contexts, each reasoning independently. Parallelism buys wall-clock time; it costs tokens.
> - **Standing loops don't survive a restart.** A restart, a crash, or a killed session disarms nWave's background disciplines (see *Standing loops*, below) silently — nothing will tell you they stopped. They should re-arm in the next session and say so; if a session starts and nobody mentions them, ask: *"check the standing loops and tell me which are active."* That one sentence is the whole recovery.

**Build:** atdd-pure preview @ `02a972e` (source `feature/atdd-pure-staging` `02a972e5aaedc389d91f2e4ea476c85f19b030bd`)

---

## What nWave Does

nWave replaces ad-hoc AI coding with a structured, auditable, wave-based methodology. It orchestrates specialized AI agents through seven disciplined development waves — from discovery to deployment. Each wave produces artifacts you review and approve before the next begins. The machine never runs unsupervised end-to-end. Quality gates at each phase catch issues early and enforce TDD discipline automatically.

---

## How It Works — The Waves at a Glance

The seven waves form a methodology graph (entry point depends on your context):

| Wave | One-line summary |
|------|------------------|
| **DISCOVER** (`/nw-discover`) | Explore the market and problem space; validate the opportunity |
| **DIVERGE** (`/nw-diverge`) | Structured brainstorming; compare design directions and competitive landscape |
| **DISCUSS** (`/nw-discuss`) | Gather requirements and user journeys; write user stories and acceptance criteria |
| **DESIGN** (`/nw-design`) | Architecture, domain modeling, and component boundaries |
| **DEVOPS** (`/nw-devops`) | Infrastructure, CI/CD, and deployment strategy |
| **DISTILL** (`/nw-distill`) | Write acceptance tests (Given-When-Then scenarios) |
| **DELIVER** (`/nw-deliver`) | TDD implementation (red → green → refactor) |

**Mandatory floor**: DISTILL → DELIVER. Every feature ends with acceptance tests and test-driven code. The five upstream waves (DISCOVER through DEVOPS) are optional; entry point depends on your context (greenfield, brownfield, bug fix, refactoring).

---

## What's New — Standing Loops, Parallel Delivery, DES Across the Waves

### Standing loops

The orchestrator runs recurring background disciplines while it works — standing checks it applies to its own behaviour:

- routes feature work through the full methodology instead of firing off a lone agent
- reconciles worktrees left behind by a task that stopped mid-way
- never leaves a single in-flight task idling
- checks delivery throughput before a heavy stage
- makes every failure explain what went wrong, why, and how to fix it
- drains two queues — one for tech debt, one for bugs — instead of letting them pile up

Nine loops carry those six disciplines — each queue gets one loop that finds work and a separate one that drains it — and the orchestrator names them `Loop 1/9` through `Loop 9/9` when it arms them, so a missing number is visible at a glance.

They're session-scoped (see the warning at the top of this page): at the start of a session the orchestrator checks which loops are live, arms any that aren't, and then tells you it did — naming what each one does and how to stop them. **They're on by default: you opt out, not in.** Arming isn't the sensitive act; arming *silently* is. Background agents spend tokens the whole time they run, so you have an unconditional right to know they started — which is why the disclosure is mandatory even though the permission isn't. To turn them off, say *"stop the standing loops"*. They stop immediately, without argument, and stay off for the rest of that session.

### Parallel delivery — the worktree is the mechanism

Delivery now runs in parallel, under one rule: **many cloud lanes, one lane on your box.** Reasoning work — investigating root causes, writing acceptance tests, reviewing — fans out across concurrent lanes, because it costs almost nothing on your machine. What stays serialized is the work that touches your machine directly: committing, running the full test suite, merging back.

The mechanism that makes the fan-out safe is the **isolated worktree**: each unit of work gets its own checkout and its own environment, so concurrent agents never step on each other's files or share a test run. A unit's life cycle is create → author → implement → examine (an independent check that the result behaves as promised) → merge back (serially) → remove the worktree as soon as the merge succeeds.

This also protects anything you have running. A build against your main checkout can restart a live service repeatedly while a fix is in progress; a build in an isolated worktree can't touch it.

### Consolidation and bugfix loops

Two of those loops turn what gets discovered mid-work into work that actually gets fixed, instead of a list that only grows.

The **consolidation** loop watches the health of your main branch — drift, unmerged work, stale branches, failing gates — and files each real problem it finds as one queue item. The **bugfix** loop catches a defect the moment you hit it and works it through the full fix process, one bug per isolated worktree. A matching pair does the same for tech debt.

Both loops are honest about what "done" means: an item counts as fixed when a ledger entry — a system record — says so, never just when a summary says so.

### DES now spans the waves, not just delivery

The Deterministic Execution System (DES) is nWave's enforcement layer. It guards every wave, not just DELIVER: DISCUSS, DESIGN, DEVOPS, DISTILL, DELIVER, and the feature-end cycle each get a generated dispatch envelope — the instructions and guardrails DES hands the wave — and every wave gate records its verdict to a ledger.

The feature-end cycle is itself a phase you can invoke, rather than an informal habit: deep review, an end-to-end check against a real environment, a full test-suite run, and a signed, recorded result.

That cycle is what catches *false-done* — work that looks finished piece by piece but doesn't hold together as a whole feature.

### A CLI built for the assistant, not just for you

`des`, nWave's CLI, is built so an LLM can drive it directly: every command either produces an artifact or fails with what went wrong, why, and exactly how to fix it — including which command to run next. The idea is that the orchestrating agent reaches for the tool that produces the right thing, instead of hand-assembling what a gate is checking for. For you, that mostly shows up as fewer dead ends: when a gate rejects something, the rejection carries its own fix.

A few worth knowing:

```bash
des next                  # read-only: what the delivery loop says to do next
des blast-radius          # how big a change really is, measured, not guessed
des feature-end run       # close one feature (run-batch closes several on one full-suite run)
des refactor --pile       # work through a tech-debt pile, one item per worktree
des --help                # the full command list
```

---

## We Want Your Feedback

This preview shapes the official release. **Please tell us what works, what's confusing, and where the friction is.** Your feedback directly influences what nWave ships next.

### What to report

Capture in your local feedback log (see "How to collect feedback" below):

- **Methodology friction**: Did a wave feel unclear? Did a command's output mislead you? Did the gate reject something without explaining why? (Frame your feedback around the *tool's behavior*, not your specific project.)
- **Time per wave**: How long did each wave take? Timeboxes help us tune defaults.
- **Token and cost consumption**: Report estimated tokens and cost per wave so we can optimize efficiency.

### How to collect feedback

nWave maintains a **local, git-ignorable feedback log** at `.nwave/beta-feedback.md` in your project. After each wave, open this file and log your observations. Format is free-form — describe what happened and what confused you.

**Privacy-critical**: This log must contain **ZERO project content, code snippets, usernames, secrets, or identifying details**. Describe *how nWave behaved* ("the DISCUSS gate rejected my requirements without explaining the validation rule" or "DELIVER took 45 minutes on a 200-line module"), never *what you were building* ("authentication service for medical records").

**Transmission**: Nothing is auto-transmitted. You review `.nwave/beta-feedback.md` after your session, scrub any accidental project detail if needed, and share it manually via GitHub Issues on this experimental repo or email.

### Feedback channel

File issues at [github.com/nWave-ai/nWave-experimental/issues](https://github.com/nWave-ai/nWave-experimental/issues) with a label `feedback` or `beta`. Include relevant entries from `.nwave/beta-feedback.md` (scrubbed for privacy). Or email directly with the log attached.

---

## Install (local — no PyPI for this preview)

### Prerequisites

- **Python 3.10+**
- **Claude Code**
- **`uv`** (recommended) or **`pipx`** (supported fallback)

If you don't have `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If you prefer `pipx` (supported, not recommended):
```bash
pip install pipx
pipx ensurepath
```

### One-step install

```bash
git clone https://github.com/nWave-ai/nWave-experimental.git
cd nWave-experimental
uv run python -m nwave_ai.cli install
```

**Then restart Claude Code.** The installer wires nWave into your global Claude Code configuration in `~/.claude/`. Agents, skills, and commands are read once at startup, so a running session keeps the old versions until you reopen it.

Restarting also disarms the standing loops. They should re-arm themselves in the new session and tell you so — if nothing mentions them, ask: *"check the standing loops and tell me which are active."*

**pip alternative** (Python 3.10+): `pip install -e . && nwave-ai install`

**Windows**: Use WSL (`wsl --install`).

---

## Activate nWave in Each Project You Test

The install above wires nWave into Claude Code globally. In **each project** where
you want to try nWave, run:

```bash
cd /path/to/your-project
nwave-ai project enable
```

This asks your permission, then adds a short **nWave (beta)** section to that
project's `CLAUDE.md` — it tells the LLM how to drive the spine and how to log
feedback locally. (No `CLAUDE.md` yet? It creates a minimal one.) Your own
content is never touched. Pass `--yes` to skip the prompt.

When you're done testing in a project:

```bash
nwave-ai project disable
```

This removes the managed section (and the file, if nWave created it) — your
content stays intact.

---

## Update to the Latest Preview

```bash
cd nWave-experimental
git pull
uv run python -m nwave_ai.cli install
```

---

## Uninstall

```bash
uv run python -m nwave_ai.cli uninstall
```

Both the CLI tool and all agents/commands/configuration are removed from `~/.claude/`. Your project files stay unchanged.

---

## Important Notes

- **Use the local CLI install above.** The Claude plugin-marketplace install path does **not** enable DES enforcement (an upstream Claude Code limitation) — without the local CLI install you lose phase enforcement, TDD validation, rigor profiles, and audit logging, which are the core of nWave.

- **This preview tracks `feature/atdd-pure-staging`.** The experimental publisher (`scripts/release/publish_experimental.py`) refreshes this repository periodically. The build SHA at the top of this README identifies the exact source commit.

- **User-facing docs** are under `docs/guides/` (tutorials and how-to guides) and `docs/reference/` (agents, commands, configuration reference) in this tree.

- **Privacy**: nWave stores all data locally. See [PRIVACY.md](../PRIVACY.md) in this repo for complete details. The experimental preview follows the same privacy guarantees — no telemetry, no automatic transmission of your project data.

---

*Experimental channel — segregated from beta/rc/prod, no PyPI: you install locally from this clone.*
