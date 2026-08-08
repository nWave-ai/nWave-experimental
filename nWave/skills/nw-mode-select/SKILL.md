---
name: nw-mode-select
description: Choose human-on-the-loop vs auto mode for a piece of work, classify it S/M/L, and pick the matching path before starting. Load at the START of any nWave-adjacent task, before dispatch, when the mode/size has not already been declared by the user in this conversation.
user-invocable: true
---

# nw-mode-select — activation and mode UX (K3-A)

This is a decision skill, not a runtime. It does not sequence, gate, or ledger
anything — it tells YOU, the LLM, which of three conversational postures to
take before you start real work, using only instructions you execute yourself.

## Step 1 — Is a mode already explicit?

If the user already said "human", "auto", "direct", "just do it", "walk me
through it", or otherwise pinned a mode in this conversation, do NOT re-ask.
Re-deriving a mode the user already stated is friction, not safety.
**Direct mode is always available and must stay explicit**: if the user's
intent is a single small, unambiguous, already-scoped action, name it as
"direct mode" in your reply and proceed — never silently promote a direct ask
into a human-on-the-loop or auto workflow, and never record it anywhere; it is
a conversational choice, not a state.

## Step 2 — Classify size (S/M/L)

Ask yourself, from the request text and repo evidence — not from vibes:

- **S (small)**: one file or one narrow behaviour, no cross-cutting design
  decision, reversible, testable in one pass.
- **M (medium)**: several files or one feature-shaped unit of work, at least
  one design decision worth writing down, still reviewable as a single unit.
- **L (large)**: spans an epic/mission, multiple design decisions, or work
  whose shape is not yet known and needs discovery/discuss/design before any
  code.

State the classification and the ONE observable reason for it (file count,
presence of a design decision, unknown shape) before proceeding — a
classification with no reason is a guess, not a decision.

## Step 3 — Choose the path

| Size | Default mode | What that means operationally |
|---|---|---|
| S | direct or auto | No projection needed; act, then report the diff. |
| M | ask: human or auto | State the classification and ask ONE question: "human-on-the-loop (I project each stage to HTML and wait for your GO) or auto (I ask once, then run with minimal interaction)?" |
| L | human-on-the-loop by default | Large/uncertain shape defaults to staged human review; auto is only offered if the user explicitly overrides. |

Never infer "auto" for an L-classified request from silence — silence on an L
request means ask, not assume.

## Human-on-the-loop: what "project to HTML" means here

Human mode is a sequence of LOCAL HTML documents you produce and hand to the
Artifact tool (or write to disk if there is no artifact channel), one per
stage the work actually needs: discovery, discuss, design, test, feedback —
stopping at each stage for the user's GO before continuing. **Reuse an
existing generator instead of inventing a new templating layer**: this repo
already has one reusable HTML-projection mechanism,
`scripts/gen_status_dashboard.py` (backlog SSOT → Artifact HTML). If the
stage's content fits that shape, reuse it; if it does not, write a small
self-contained HTML file directly (inline CSS, no build step, no new
dependency) — do not build a template engine or a second dashboard
generator for this. If no reusable HTML mechanism applies to a given stage,
say so and fall back to a plain markdown turn instead of manufacturing new
infrastructure.

## Auto mode: what "minimal context" means here

Auto mode asks for authorization exactly once — naming what you are about to
do and its blast radius — then executes with minimal further interaction: no
per-stage HTML, no rich intermediate documentation, just the working diff and
a short end-of-run summary. Auto mode is still governed by every existing
nWave/DES rule that already applies to your actions (spine dispatch,
destructive-action confirmation, etc.) — this skill changes ONLY the
human-interaction cadence, never what is safe to do unattended.

## What this skill is explicitly NOT

- Not a sequencer, not a state machine, not a new CLI verb.
- Not a ledger or receipt system — direct-mode and auto-mode choices are
  conversational, never persisted as a workflow record.
- Not a fork of the wave spine (`/nw-*`) — if the classified work already
  maps onto a wave command, use that command; this skill only decides
  WHETHER and HOW to interact with the human before you do, not what runs.
- Not a new gate — a hook that surfaces this skill (SubagentStart's existing
  `additionalContext` reminder) is non-blocking and reused as-is; this skill
  adds no hook code of its own.
