---
name: nw-mode-select
description: Choose human-on-the-loop vs auto mode for a piece of work, classify it S/M/L, and pick the matching path before starting. Load at the START of any nWave-adjacent task, before dispatch, when the mode/size has not already been declared by the user in this conversation.
user-invocable: true
---

# nw-mode-select — activation and mode UX (K3-A)

This is a decision skill, not a runtime. It does not sequence, gate, or ledger anything — it tells YOU, the LLM, which of three conversational postures to take before you start real work, using only instructions you execute yourself.

## Step 1 — Is a mode already explicit?

If the user already said "human", "auto", "direct", "just do it", "walk me through it", or otherwise pinned a mode in this conversation, do NOT re-ask. **A generic authorization to act autonomously counts as `auto`**: phrases like "work autonomously", "make reasonable choices/decisions", or "use your best judgment" pin the mode exactly as explicitly as the literal word "auto" — proceed as auto without asking again. **Direct mode is always available and must stay explicit**: a single small, unambiguous, already-scoped action is named "direct mode" in your reply and proceeds — never silently promoted into human-on-the-loop or auto, never recorded anywhere; it is a conversational choice, not a state.

**An explicit mode still invokes this skill once, every size included**: a mode pinned in conversation removes only the re-ask question in Step 3 — it never removes the one required `nw-mode-select` invocation before dispatch, S included. Never re-ask a pinned mode.

## Step 2 — Classify size (S/M/L)

Ask yourself, from the request text and repo evidence — not from vibes:

- **S (small)**: one file or one narrow behaviour, no cross-cutting design decision, reversible, testable in one pass.
- **M (medium)**: several files or one feature-shaped unit of work, at least one design decision worth writing down, still reviewable as a single unit.
- **L (large)**: spans an epic/mission, multiple design decisions, or work whose shape is not yet known and needs discovery/discuss/design before any code.

State the classification and the ONE observable reason for it (file count, presence of a design decision, unknown shape) before proceeding.

## Step 3 — Choose the path

| Size | Default mode | What that means operationally |
|---|---|---|
| S | direct | Invoke this skill once, classify S, then exit directly and act, reporting the diff — S never delegates to `nw-auto`. |
| M | ask: human or auto | State the classification and ask ONE question: "human-on-the-loop (I project each stage to HTML and wait for your GO) or auto (I ask once, then run with minimal interaction)?" |
| L | human-on-the-loop by default | Large/uncertain shape defaults to staged human review; auto only if the user explicitly overrides. |

Never infer "auto" for an L-classified request from silence — silence on an L request means ask, not assume. Silence or the absence of a reply channel never manufactures authorization, on M or L: an unattended or headless session with no reply forthcoming still asks and waits. Only an explicit phrase already given by the user (Step 1) pins the mode without asking.

## Human-on-the-loop: what "project to HTML" means here

Human mode is a sequence of LOCAL HTML documents you produce and hand to the Artifact tool (or write to disk if there is no artifact channel), one per stage the work actually needs — stopping at each stage for the user's GO. **Reuse an existing generator instead of inventing a new templating layer**: `scripts/gen_status_dashboard.py` (backlog SSOT → Artifact HTML) covers this shape; if a stage doesn't fit it, write a small self-contained HTML file directly (inline CSS, no build step) — do not build a template engine or a second dashboard generator. If no reusable mechanism applies, fall back to a plain markdown turn instead of manufacturing new infrastructure.

## Auto mode: what "minimal context" means here

Auto mode asks for authorization exactly once — naming what you are about to do and its blast radius — then executes with minimal further interaction: no per-stage HTML, just the working diff and a short end-of-run summary. After classification, delegate explicit Auto M/L to `nw-auto`; that skill is the sole route authority. Do not restate or execute its M/L algorithm here, and do not route Auto through `nw-deliver`, `nw-distill`, or a generic wave command. Direct S and Human routes are unchanged.

## What this skill is explicitly NOT

- Not a sequencer, not a state machine, not a new CLI verb.
- Not a ledger or receipt system — direct-mode and auto-mode choices are conversational, never persisted as a workflow record.
- Not a fork of the wave spine (`/nw-*`). Human-on-the-loop may continue through its existing wave route; direct S remains direct. Auto M/L delegates only to `nw-auto` as stated above.
- Not a new gate — the existing root activation path (the reused `PreToolUse`/`Agent` hook) that surfaces this skill adds no hook code of its own; it may block the first mutation until this one selection is observed, then stays silent.
