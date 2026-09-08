# Replay case: `graphify-callers-of`, runs 17 and 20 (2026-09-05)

Recorded evidence. Nothing in this directory was authored by hand, with the
declared exception of the backfills below: turn `04` carries a
`provider_stdout_provenance` and a `prompt_provenance` field, and turn `05`
carries a `provider_stdout_provenance` of its own, each naming exactly which
bytes were replaced, why the recorded judgment still stands, and which change
could NOT have been repaired that way. A backfill that is not declared in the
record it touches is a fabrication; read those fields before quoting turn `04`
or turn `05`.

## What each file is

`NN-<role>.json` is a turn record copied out of
`.nwave/des/logs/turns/<run-id>/`, written by
`des.adapters.driven.task_invocation.turn_recorder.TurnRecorder` during a real,
paid delivery. `inert_claude.replay` returns that record's `provider_stdout`
verbatim when the runner asks for that role, so `extract_model_run` reads in the
replay exactly the document it read in the run.

The `NN` prefix is the ORDER the roles were called in, and nothing else. It is
not the `sequence` field inside the record, and under the step surface it cannot
be: each DES step runs in its own process with its own recorder, so every step's
turns are numbered from `01` in a run directory of their own. The prefixes here
are the orchestrated order across those directories; the `run_id` and `sequence`
inside each record are untouched, so any file can still be traced back to the
run that produced it through the provenance table below.

The ONE modification is a trailing newline, which this repository's file-quality
rule requires and the recorder does not write. It changes no parsed field, so
the replayed envelope is still the recorded bytes.

`NN-<role>.patch.json` is the workspace effect of the same turn. A turn record
carries what a role **said**, never what it **wrote**: the oracle and the
implementation exist only in the candidate commit the run produced. Both diffs
are that commit's own output, split by owning role and otherwise unmodified.

The diff travels as a JSON string rather than as a bare `.patch` file for one
reason. A unified diff writes a blank context line as a single space, and this
repository refuses trailing whitespace in a text file: stripping those spaces
would corrupt a recorded diff into one that no longer applies. Escaping them
keeps every byte, and `inert_claude` writes the diff back out before handing it
to `git apply`.

## Provenance, per file

| file | source |
|---|---|
| `01-nw-product-owner.json` | run `20260905T041548Z-4149687`, turn 01 |
| `02-nw-solution-architect.json` | run `20260905T041548Z-4149687`, turn 02 |
| `03-nw-acceptance-designer.json` | run `20260905T041548Z-4149687`, turn 03 |
| `04-nw-acceptance-designer-reviewer.json` | run `20260905T041548Z-4149687`, turn 04 |
| `05-nw-software-crafter.json` | run `20260905T041548Z-4149687`, turn 05 |
| `06-nw-software-crafter-reviewer.json` | run `20260905T061618Z-36389`, turn 04 |
| `07-nw-user-examiner.json` | run `20260905T061618Z-36389`, turn 05 |
| `03-nw-acceptance-designer.patch.json` | candidate `96f98e267`, the two paths that run's oracle owned |
| `05-nw-software-crafter.patch.json` | candidate `96f98e267`, the two paths that run's implementation owned |

## What the recorded prompts do NOT carry, and must never be backfilled with

Turn `04`'s recorded prompt predates `oracle_red`, the runner's own execution of
the oracle delivered to the reviewer since 2026-09-06. Do not backfill it. The
recorded turn approved that oracle WITHOUT reading any execution, so a prompt
carrying one would claim a judgment nobody gave; and the field's failure text
names the pytest tmp root and a live object address of the run that produced it,
so any recorded value diverges again on the next replay. `inert_claude` excludes
it from the question digest for that reason, alongside the two location facts.
That the field is delivered, and what it contains, is asserted in
`tests/des/unit/application/test_authored_oracle_is_executed_red.py`.

## What ADR-SSOT-002 Section 4b changed here, and what it did not

Section 4b retires `des dispatch` as an orchestrator: the delivery shape is the
invocable steps, called one at a time by an orchestrating model. This case was
recorded through the composed run, so the question is whether it still records
the right turns.

**The retirement of the composition took no role out of this corpus.** It
removed aggregate methods only the composer could reach; `des verify` still buys
the whole-diff reviewer AND the source-blind examiner, and no file here was
re-recorded, renumbered or changed a byte for it.

**A separate change DID cost one turn, and it is the software's, not this
bundle's.** ADR-DES-003 Section 2.4 rules the pre-craft judgement of the oracle
out -- `OracleUnadmitted` becomes `OracleUnrecorded`, "the record is written on
RED, no judge". That has landed: `oracle_value` authors the set, measures it RED
and records the turn without buying a judge, so `des oracle` buys the acceptance
author alone and a stepped run buys SIX roles for one value.
`04-nw-acceptance-designer-reviewer.json` therefore records a turn no step buys
any more. It is kept here, unrequested: `inert_claude` selects a record by ROLE,
so an unasked file answers nothing and costs nothing, and keeping it preserves
the recorded evidence of the boundary that existed when runs 17 and 20 were
paid. Read the six roles a replay actually walks off
`tests/scripts/analysis/test_k4_inert_replay_drives_the_real_runner.py`, never
off the numbering below.

**What a replay of a stepped run costs.** Nothing changes: the orchestrator
invokes each step, each step spawns `claude --agent <role>`, and this same
corpus answers each one. The occurrence counter lives beside the arm's
`CLAUDE_CONFIG_DIR` precisely so it survives from one step process to the next.

## The case is COMPOSED, and that is a declared limit

No single recorded run reached the examiner: the run that carried the Product
Owner and the architect stopped at candidate construction, and the run that
reached the examiner started from an already-designed batch. So the seven roles
come from two runs of the SAME Request against the SAME repository, ordered as
the runner calls them. That is enough to drive the deterministic layer end to
end; it is not a transcript of one continuous run, and no reader should quote it
as one.

## What the recorded verdicts actually are

The examiner turn (`07`) recorded **rejected**, with the diagnostic naming a
`confidence: noisy` answer where binding-resolved was promised. A replay is
faithful or it is nothing, so this case replays that rejection. **No real run
has yet recorded an accepted examiner turn**, so no replay built from today's
records can close a delivery on the examine step. Replacing the record with an
accepted one that no model produced would make every downstream green vacuous.

## Subject

Both runs delivered against **nwave-dev**: the design facts name
`src/des/adapters/driven/codefact/graphify_code_fact_adapter.py` and the oracle
lives under `tests/bugs/des/`. Replaying this case over a workspace that is not
an nwave-dev checkout replays the software, never the judgment, and the patches
will not apply there.
