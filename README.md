# nWave — atdd_pure Preview (Experimental Channel)

> ⚠️ **EXPERIMENTAL — NOT RECOMMENDED FOR PRODUCTION**
>
> This is an active development preview of nWave. Breaking changes are expected. The API, wave structure, and command behavior may change without notice. Use only for evaluation and feedback, not in production systems or critical projects.
>
> This repository is **private and access-controlled** — published for preview only to collaborators. There is **no PyPI package** for this channel. You install **locally from this clone**.

**Build:** atdd-pure preview @ `f459fdcac` (source `feature/atdd-pure-staging` `f459fdcac4f5d84a1cdd813c2dae27109d502a47`)

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

**Then restart Claude Code.** The installer wires nWave into your global Claude Code configuration in `~/.claude/`.

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

*Experimental channel — segregated from beta/rc/prod, no PyPI, access limited to collaborators on this private repository.*
