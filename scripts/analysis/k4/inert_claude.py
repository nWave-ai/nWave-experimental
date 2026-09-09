#!/usr/bin/env python3
"""An INERT, deterministic stand-in for the `claude` binary -- zero model spend.

Every stage of the K4 chain that a paid campaign reaches through `claude` reaches
this instead: `paired_campaign._AUTH_PROBE`'s liveness ping, its per-arm headroom
probe, and the timed delivery itself. Nothing here talks to a provider; every
number it emits is a function of the workspace it was invoked in.

## Two shapes, because the two arms ask for two different things

The CONTROL arm asks for one delivery: `claude -p --model ... --output-format
json`, and the answer is the synthetic result payload the rest of this file
builds.

The nWAVE arm does not. Its turns arrive one per DECLARED ROLE --
`claude -p --agent nw-product-owner --json-schema <schema> ...` -- and
`ClaudeCodeTaskAdapter.extract_model_run` reads a `structured_output` object
back out of stdout. A delivery payload has none, so answering a role turn with
one refused the whole arm with `ModelEnvelopeUnavailable` (measured 2026-09-05:
the offline chain stopped at the `campaign` stage for exactly that reason).

So a turn carrying `--agent` is answered by REPLAY instead: the shim returns,
verbatim, the `provider_stdout` a REAL recorded turn of that role produced, read
out of a replay case built from `.nwave/des/logs/turns/`. No prose is parsed and
nothing is synthesised -- a role with no recorded turn is refused LOUD. The
deterministic layer (paths, argv, handoffs, candidate construction, native
verification, integration, scorers, verdict) then runs for real against frozen
model output, which is the whole point: it is provable offline at zero spend,
while the judgment layer stays the model's.

## What SPAWNS those role turns, since ADR-SSOT-002 Section 4b

The STEPS do, one invocation at a time, and no longer one composed run. Section
4b retires `des dispatch` as an orchestrator: «No executor in the software
composes the steps. No code path calls one step and then calls the next.» The
orchestrating model invokes `des po`, then `des design --value N`, then
`des oracle --value N`, `des craft --value N`, `des verify` and
`des integrate --candidate SHA`, reading each terminal's `NEXT` line as data.

Three consequences this file is written to, each measured at `steps@6d817bc91`
rather than assumed:

1. **The retirement itself took no role away.** `des verify` runs the whole-diff
   reviewer and the source-blind examiner exactly as the composed run did, and
   no bundled record is retired by the retirement. What DID drop a turn is
   ADR-DES-003 Section 2.4: `des oracle` runs the acceptance author alone, with
   the record written on RED and no pre-craft judge, so the corpus's
   `nw-acceptance-designer-reviewer` record is simply never asked for -- records
   are selected by ROLE, so an unasked one answers nothing.
2. **One process per turn is no longer incidental, it is the shape.** Each step
   is its own `des` process, so the occurrence counter CANNOT live in memory --
   see `_next_occurrence`, which persists it beside the arm's own
   `CLAUDE_CONFIG_DIR`, the one thing every step of one Request shares.
3. **A role may be asked more times than the corpus records, lawfully.** The
   orchestrator decides the sequence, so it may re-invoke a step. Where the step
   is idempotent (ADR-DES-003 Section 2, law L1) the re-invocation buys no turn
   and the counter does not move; where it is not -- `des design` over a bound
   value re-buys the architect today -- the second call reaches this shim and is
   refused LOUD against a one-record corpus. That refusal is the replay showing
   an L1 defect at zero spend, and it must stay loud rather than answer twice
   from one record.

## Recording a NEW case under the step model

A composed run wrote every turn into one `.nwave/des/logs/turns/<run-id>/`
directory, numbered `01..NN` in call order. Steps do not: `DeliverySteps._locked`
builds a fresh `DeliveryContinuationRunner` per invocation, so each step gets its
OWN run id and its own sequence starting at `01`. Collecting a case therefore
means reading several run directories -- one per step that bought a turn -- and
renumbering the files into the order the orchestrator called them in.

The renumbering changes no parsed field: `_recorded_turns` reads the file NAME
only for order and role, and the `run_id`/`sequence` INSIDE each record stay the
recorded values, so the provenance of every byte remains checkable. The bundled
case already carries a rename of that kind and declares it in its README table.

## The fidelity rule this file is written to

A substrate SIMPLER than production produces a VACUOUS green. The instance that
earned the rule: a probe stayed green five days because its fixture built a
one-commit repo while production does a full clone with a detached HEAD -- the
probe never exercised the code path that reads a base commit. So this shim
reproduces the real SHAPE everywhere a downstream reader keys off shape:

* the delivery COMMITS a real product diff (`hc/api/models.py` + a real
  numbered migration + a new test module) on top of the arm's detached pin, so
  `run_acceptance.delivery_present`, `_base_commit_sha` and
  `blind_review.write_delivery_packet` all see what they see in production --
  a committed delta against a recorded baseline, not an empty tree;
* it writes a REAL session transcript at the exact production path
  (`$CLAUDE_CONFIG_DIR/projects/<slug>/<session>.jsonl` plus that session's own
  `subagents/*.jsonl`), because `paired_spread.resolve_transcript_wall` fails
  CLOSED on a missing one and the wall axis then silently leaves the verdict;
* the result payload carries `modelUsage`, not only top-level `usage`: the
  token axis is EXCLUDED when the scope is top-level-only
  (`admission_verdict._axis_values`), so a payload without it would produce a
  verdict that looks computed with one axis quietly missing.

## Where it is deliberately simpler than the real thing

Stated here rather than in a report nobody reads next time:

1. **No judgment.** The delivery diff is FIXED. It exercises the plumbing that
   carries a delivery; it does not implement the feature, so the hidden
   acceptance oracle is expected to reject it. `accepted=false` here is a
   correct measurement of an inert arm, never evidence about nWave.
2. **No subagents, no tools, no hooks.** The transcript is synthetic: the
   timestamps are computed, not observed, so the wall axis measures this file's
   arithmetic, not a real run's duration.
3. **A replayed turn answers the question it was RECORDED against**, not the
   question it is asked now. The recorded case is a real delivery, so its roles
   speak about the repository that run was pointed at; replaying it over a
   different subject replays the software, never the judgment. The ledger
   records both prompt digests -- the replayed turn's and the recorded one's --
   so a reader can see when the two questions differ instead of inferring it.
4. **The workspace bytes come from the candidate commit**, not from the turn
   record: a record carries what a role SAID, never what it WROTE. The sibling
   `NN-<role>.patch.json` carries that run's own candidate diff, split by owning
   role -- recovered evidence, not authored fixture content.

Stdlib only, no repo imports: it must run under whatever interpreter is first
on the arm's PATH.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


#: The one fixed instant every synthetic transcript is anchored to, so two
#: runs of this probe produce byte-identical wall measurements.
_EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

#: Per-arm multipliers against the pair's own base figures. Chosen so ONE
#: campaign exercises BOTH verdict branches: cost and tokens land INSIDE their
#: 1.5x bounds while wall breaches its 1.5x bound. A profile where every axis
#: passes would prove only that the comparator can say yes.
_ARM_FACTORS = {
    "control": {"cost": 1.0, "tokens": 1.0, "wall": 1.0},
    "nwave": {"cost": 1.2, "tokens": 1.3, "wall": 2.6},
}

#: Base figures for pair 1; later pairs scale by `_PAIR_DRIFT` on BOTH arms so
#: the per-pair ratio stays exactly the factor above while the raw numbers
#: differ pair to pair, as a real campaign's do.
_BASE = {"cost": 2.50, "tokens": 4_000_000, "wall": 900.0}
_PAIR_DRIFT = 0.08


def _ledger(record: dict) -> None:
    path = os.environ.get("K4_INERT_CLAUDE_LEDGER")
    if not path:
        return
    record = {"utc": datetime.now(timezone.utc).isoformat(), **record}
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _flag(argv: list[str], name: str) -> str | None:
    for index, token in enumerate(argv):
        if token == name and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith(name + "="):
            return token.split("=", 1)[1]
    return None


def _identity(cwd: Path) -> tuple[str, int]:
    """(arm, pair index) read from the campaign's own directory layout.

    `paired_campaign` runs each delivery with cwd `<out>/pair-N/<arm>`, so the
    layout IS the identity. Anything else -- a preflight probe workspace, a
    headroom probe -- is not a campaign arm and gets ("probe", 0).
    """
    parent = cwd.parent.name
    if parent.startswith("pair-"):
        try:
            return cwd.name, int(parent.split("-", 1)[1])
        except ValueError:
            return cwd.name, 0
    return "probe", 0


def _figures(arm: str, pair: int) -> dict[str, float]:
    factors = _ARM_FACTORS.get(arm, {"cost": 1.0, "tokens": 1.0, "wall": 1.0})
    drift = 1.0 + _PAIR_DRIFT * max(pair - 1, 0)
    return {
        axis: _BASE[axis] * drift * factors[axis] for axis in ("cost", "tokens", "wall")
    }


def _session_id(cwd: Path, kind: str) -> str:
    digest = hashlib.sha256(f"{cwd}|{kind}".encode()).hexdigest()
    return "-".join(
        (digest[0:8], digest[8:12], digest[12:16], digest[16:20], digest[20:32])
    )


def _model_usage(total_tokens: int) -> dict:
    """Two models, the shape `paired_spread._aggregate_model_usage` sums.

    Split across two entries deliberately: a single-model payload would not
    exercise the aggregation the token axis depends on.
    """
    cache_read = int(total_tokens * 0.90)
    cache_creation = int(total_tokens * 0.06)
    output = int(total_tokens * 0.03)
    inputs = total_tokens - cache_read - cache_creation - output
    return {
        "claude-sonnet-5": {
            "inputTokens": inputs,
            "outputTokens": output,
            "cacheReadInputTokens": cache_read,
            "cacheCreationInputTokens": cache_creation - 1,
            "webSearchRequests": 0,
            "costUSD": 0.0,
            "contextWindow": 200000,
            "canonicalModel": "claude-sonnet-5",
            "provider": "firstParty",
        },
        "claude-haiku-4-5": {
            "inputTokens": 0,
            "outputTokens": 0,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 1,
            "webSearchRequests": 0,
            "costUSD": 0.0,
            "contextWindow": 200000,
            "canonicalModel": "claude-haiku-4-5",
            "provider": "firstParty",
        },
    }


def _payload(
    session_id: str,
    result: str,
    *,
    cost: float,
    tokens: int,
    duration_s: float,
    turns: int,
    is_error: bool = False,
) -> dict:
    usage = _model_usage(tokens)
    totals = {
        "input_tokens": sum(m["inputTokens"] for m in usage.values()),
        "output_tokens": sum(m["outputTokens"] for m in usage.values()),
        "cache_creation_input_tokens": sum(
            m["cacheCreationInputTokens"] for m in usage.values()
        ),
        "cache_read_input_tokens": sum(
            m["cacheReadInputTokens"] for m in usage.values()
        ),
    }
    return {
        "type": "result",
        "subtype": "error" if is_error else "success",
        "is_error": is_error,
        "session_id": session_id,
        "num_turns": turns,
        # Deliberately SHORTER than the transcript span this run writes: the
        # root payload stops when the root process returns, which is the exact
        # gap `resolve_transcript_wall` exists to correct.
        "duration_ms": int(duration_s * 1000 * 0.4),
        "duration_api_ms": int(duration_s * 1000 * 0.35),
        "total_cost_usd": cost,
        "usage": totals,
        "modelUsage": usage,
        "permission_denials": [],
        "stop_reason": "end_turn",
        "terminal_reason": "completed",
        "result": result,
        "uuid": _session_id(Path(session_id), "uuid"),
    }


def _write_transcript(config_dir: Path, session_id: str, span_s: float) -> None:
    """The production transcript layout, at the production path.

    `resolve_transcript_wall` globs `<workspace>/.claude-k4/projects/**/*.jsonl`
    for the stem matching the session, then adds that transcript's OWN
    `<session>/subagents/*.jsonl`. Both are written here; the span between the
    earliest and latest timestamp across them IS the wall the verdict reads.
    """
    projects = config_dir / "projects" / "-k4-offline-probe-workspace"
    projects.mkdir(parents=True, exist_ok=True)
    root = projects / f"{session_id}.jsonl"
    start = _EPOCH
    end = start + timedelta(seconds=span_s)
    lines = [
        {
            "type": "user",
            "sessionId": session_id,
            "timestamp": start.isoformat(),
            "message": {"role": "user", "content": "<inert task>"},
        },
        # A line with NO timestamp: real transcripts carry them, and
        # `_read_transcript_timestamps` must skip rather than fail on one.
        {"type": "summary", "summary": "inert run"},
        {
            "type": "assistant",
            "sessionId": session_id,
            "timestamp": (start + timedelta(seconds=span_s * 0.5)).isoformat(),
            "message": {"role": "assistant", "content": "<inert>"},
        },
        {
            "type": "assistant",
            "sessionId": session_id,
            "timestamp": end.isoformat(),
            "message": {"role": "assistant", "content": "<inert done>"},
        },
    ]
    root.write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8"
    )
    subagents = projects / session_id / "subagents"
    subagents.mkdir(parents=True, exist_ok=True)
    (subagents / "inert-subagent.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "type": "assistant",
                    "sessionId": session_id,
                    "timestamp": (
                        start + timedelta(seconds=span_s * ratio)
                    ).isoformat(),
                    "message": {"role": "assistant", "content": "<inert subagent>"},
                }
            )
            + "\n"
            for ratio in (0.2, 0.8)
        ),
        encoding="utf-8",
    )


# --- the delivery -----------------------------------------------------------


_MODEL_ANCHOR = "class Check(models.Model):\n    name = models.CharField(max_length=100, blank=True)\n"

_MODEL_FIELD = (
    "class Check(models.Model):\n"
    "    name = models.CharField(max_length=100, blank=True)\n"
    "    maintenance_windows = models.JSONField(default=list, blank=True)\n"
)

_MIGRATION_TEMPLATE = """from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("api", "{previous}")]

    operations = [
        migrations.AddField(
            model_name="check",
            name="maintenance_windows",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
"""

_DELIVERED_TEST = """from django.test import TestCase

from hc.api.models import Check


class MaintenanceWindowsFieldTestCase(TestCase):
    def test_default_is_empty(self) -> None:
        check = Check()
        self.assertEqual(check.maintenance_windows, [])
"""


class DeliveryRefused(RuntimeError):
    """The inert delivery could not reproduce the production SHAPE.

    Raised, never swallowed: an inert arm that silently produced no diff would
    hand every downstream stage an empty workspace and let the chain report a
    green that measured nothing.
    """


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _apply_product_diff(cwd: Path, arm: str) -> list[str]:
    models_py = cwd / "hc" / "api" / "models.py"
    if not models_py.is_file():
        raise DeliveryRefused(f"no {models_py}: this is not a healthchecks checkout")
    text = models_py.read_text(encoding="utf-8")
    if _MODEL_ANCHOR not in text:
        raise DeliveryRefused(
            "the Check model anchor moved; the inert delivery would have been a "
            "no-op and the chain would have scored an empty workspace"
        )
    models_py.write_text(text.replace(_MODEL_ANCHOR, _MODEL_FIELD, 1), encoding="utf-8")
    touched = ["hc/api/models.py"]

    migrations = cwd / "hc" / "api" / "migrations"
    numbered = sorted(p for p in migrations.glob("0*.py") if p.stem[:4].isdigit())
    if not numbered:
        raise DeliveryRefused(f"no numbered migrations under {migrations}")
    previous = numbered[-1].stem
    nxt = f"{int(previous[:4]) + 1:04d}_check_maintenance_windows"
    (migrations / f"{nxt}.py").write_text(
        _MIGRATION_TEMPLATE.format(previous=previous), encoding="utf-8"
    )
    touched.append(f"hc/api/migrations/{nxt}.py")

    test_path = cwd / "hc" / "api" / "tests" / "test_maintenance_windows.py"
    test_path.write_text(_DELIVERED_TEST, encoding="utf-8")
    touched.append("hc/api/tests/test_maintenance_windows.py")

    if arm == "nwave":
        # Only one arm adds a test-only dependency, so `run_acceptance.
        # _dev_requirements_delta` -- the delta installer, not the whole-file
        # installer -- is exercised on a real delta rather than on an empty one.
        dev = cwd / "requirements-dev.txt"
        if dev.is_file():
            dev.write_text(
                dev.read_text(encoding="utf-8").rstrip("\n") + "\ntime-machine\n",
                encoding="utf-8",
            )
            touched.append("requirements-dev.txt")
    return touched


def _deliver(cwd: Path, arm: str) -> str:
    touched = _apply_product_diff(cwd, arm)
    add = _git(cwd, "add", "-A")
    if add.returncode != 0:
        raise DeliveryRefused(f"`git add -A` exited {add.returncode}: {add.stderr}")
    # Plain `git commit`: the arm's own repo-local identity must carry it. A
    # `-c user.name=...` override here would hide exactly the `fatal: empty
    # ident name` class row 10 of the K4 matrix exists to catch.
    commit = _git(cwd, "commit", "-m", "feat(api): maintenance windows field (inert)")
    if commit.returncode != 0:
        raise DeliveryRefused(
            f"`git commit` exited {commit.returncode}: {commit.stderr.strip()}"
        )
    return "Inert delivery committed: " + ", ".join(touched)


# --- the replay -------------------------------------------------------------


#: The bundled case: one directory of REAL turn records copied verbatim out of
#: `.nwave/des/logs/turns/`, plus the workspace patches recovered from the
#: candidate those turns produced.  `K4_INERT_REPLAY_DIR` points the shim at a
#: different one without touching this file.
_DEFAULT_REPLAY_CASE = "graphify-callers-of-run17-run20"

#: Written beside the arm's own `CLAUDE_CONFIG_DIR`, which `preflight._arm_env`
#: renders per workspace: two concurrent arms, or two pairs, therefore count
#: their turns independently BY CONSTRUCTION, without this file inventing a
#: session key the runner never gave it.
_REPLAY_STATE_NAME = "inert-replay-state.json"


class ReplayRefused(RuntimeError):
    """The recorded turn a role asked for does not exist, or could not be replayed.

    Raised and reported LOUD on stderr with a non-zero exit.  The alternative --
    answering with something plausible -- would hand the runner a model outcome
    no model ever produced, which is the one failure a replay must not have.
    """


def _replay_dir() -> Path:
    declared = os.environ.get("K4_INERT_REPLAY_DIR")
    if declared:
        return Path(declared)
    return Path(__file__).resolve().parent / "replay" / _DEFAULT_REPLAY_CASE


#: The sibling that carries a turn's WORKSPACE effect, next to its envelope.
_PATCH_SUFFIX = ".patch.json"


def _recorded_turns(directory: Path) -> dict[str, list[Path]]:
    """`NN-<role>.json` grouped by role, in recorded order.

    The file NAME carries the ordering, so a role called twice in one run is
    replayed twice in the order it was recorded -- no index file to drift. The
    `.patch.json` siblings are effects, not turns, and are excluded here rather
    than left to be mistaken for a role called `<role>.patch`.
    """
    by_role: dict[str, list[Path]] = {}
    for path in sorted(directory.glob("[0-9][0-9]-*.json")):
        if path.name.endswith(_PATCH_SUFFIX):
            continue
        role = path.stem.split("-", 1)[1]
        by_role.setdefault(role, []).append(path)
    return by_role


def _replay_state_path(config_dir: Path) -> Path:
    return config_dir / _REPLAY_STATE_NAME


def _next_occurrence(config_dir: Path, role: str) -> int:
    """The 0-based occurrence index for this role, advanced by one, persisted.

    A separate process per turn is the production shape, so the counter cannot
    live in memory.  Under ADR-SSOT-002 Section 4b that is doubly true: each
    DES step is its own process too, so `config_dir` -- the arm's own
    `CLAUDE_CONFIG_DIR`, the one thing every step of one Request shares -- is
    the only place a count of "how many times has this role been asked" can
    survive from `des design` to `des verify`.

    A state file that cannot be read is treated as absent rather than fatal,
    but a state file that cannot be WRITTEN is fatal: the next turn would
    silently replay the same record twice.
    """
    path = _replay_state_path(config_dir)
    counts: dict[str, int] = {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            counts = {k: int(v) for k, v in loaded.items() if isinstance(v, int)}
    except (OSError, ValueError):
        counts = {}
    occurrence = counts.get(role, 0)
    counts[role] = occurrence + 1
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(counts, sort_keys=True), encoding="utf-8")
    except OSError as error:
        raise ReplayRefused(
            f"cannot persist the replay counter at {path}: {error}"
        ) from None
    return occurrence


def _select_record(directory: Path, role: str, occurrence: int) -> Path:
    if not directory.is_dir():
        raise ReplayRefused(f"no replay directory at {directory}")
    by_role = _recorded_turns(directory)
    records = by_role.get(role)
    if not records:
        raise ReplayRefused(
            f"the replay case {directory} has no recorded turn for role {role!r}; "
            f"it records {sorted(by_role) or 'no role at all'}"
        )
    if occurrence >= len(records):
        raise ReplayRefused(
            f"role {role!r} was called {occurrence + 1} times but the replay case "
            f"{directory} records {len(records)} turn(s) for it. Under "
            "ADR-SSOT-002 Section 4b the orchestrator chooses the sequence, so a "
            "step it re-invoked may lawfully ask a role again -- and where that "
            "step is not idempotent (ADR-DES-003 Section 2, law L1) the extra "
            "turn is real. Answering it twice from one record would hand the "
            "runner a judgment no model gave, so it is refused instead"
        )
    return records[occurrence]


def _recorded_envelope(record: Path) -> str:
    """The provider's raw stdout for that turn, verbatim -- never re-encoded.

    Returned as the bytes the recorder saw, so `extract_model_run` reads in the
    replay exactly the document it read in the run.  A record whose turn ended
    by RAISING carries no envelope and is refused here rather than answered
    with an empty string.
    """
    try:
        document = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ReplayRefused(f"cannot read the turn record {record}: {error}") from None
    stdout = document.get("provider_stdout")
    if not isinstance(stdout, str) or not stdout:
        raise ReplayRefused(
            f"the turn record {record} carries no provider_stdout "
            f"(raised={document.get('raised')!r}): there is no envelope to replay"
        )
    return stdout


def _apply_recorded_patch(record: Path, cwd: Path) -> str | None:
    """Reproduce the workspace bytes that turn wrote, from RECORDED evidence.

    A turn record carries what the model SAID, never what it WROTE: the
    acceptance designer's oracle and the crafter's implementation exist only in
    the candidate commit the run produced.  So the sibling
    `NN-<role>.patch.json` carries that commit's own diff, split by owning role
    -- recovered evidence, not generated content, and not a hand-written
    fixture.  A role with no patch wrote nothing and gets none.

    The diff travels as a JSON string, not as a bare `.patch` file, and the
    reason is the evidence itself: a unified diff represents a blank context
    line as a single space, and this repository refuses trailing whitespace in a
    text file.  Stripping it would corrupt a recorded diff into one that no
    longer applies; escaping it preserves every byte.  It is written back out
    verbatim and handed to `git apply` in the cwd the runner gave this process
    -- the runner's own workspace -- so the effect lands where the real turn's
    effect landed.
    """
    carrier = record.with_name(record.stem + _PATCH_SUFFIX)
    if not carrier.is_file():
        return None
    try:
        diff = json.loads(carrier.read_text(encoding="utf-8"))["diff"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ReplayRefused(
            f"the recorded effect {carrier} carries no readable diff: {error}"
        ) from None
    written = Path(tempfile.mkdtemp(prefix="k4-inert-replay-")) / f"{record.stem}.patch"
    written.write_text(diff, encoding="utf-8")
    applied = _git(cwd, "apply", "--whitespace=nowarn", str(written))
    if applied.returncode != 0:
        raise ReplayRefused(
            f"`git apply` of the effect recorded in {carrier} exited "
            f"{applied.returncode} in {cwd}: "
            f"{applied.stderr.strip() or applied.stdout.strip()}"
        )
    return str(carrier)


#: The case's own claim about the tree its recorded effects were produced on.
_BASE_COMMIT_NAME = "base-commit.txt"


def _admit_the_workspace(directory: Path, cwd: Path) -> None:
    """Refuse a case recorded against a DIFFERENT repository, at the FIRST turn.

    A replay case carries diffs, and a diff belongs to the tree it was cut from.
    Nothing stops the first four role turns from answering happily in a foreign
    workspace -- the envelopes are just documents, and a create-only diff applies
    in any tree at all -- so the mismatch surfaces only when the first modifying
    diff is applied, several turns in, as an opaque failed turn. Measured
    2026-09-05: the K4 offline campaign replayed four roles into its healthchecks
    workspace and stopped at the fifth with `IssuedUncertain`.

    So the case's declared base commit is checked HERE, before the first envelope
    is emitted (GDP-1). Its presence in the workspace's own object store is the
    property: a repository that has never heard of that commit is not the
    repository the case was recorded on. A case that declares no base FILE makes
    no claim and is admitted unchecked -- but a file that is present and says
    nothing readable is a claim that FAILED, not an absent one, and it degrades
    LOUD rather than silently reopening the hole this function closes.
    """
    declared = directory / _BASE_COMMIT_NAME
    if not declared.is_file():
        return
    try:
        words = declared.read_text(encoding="utf-8").split()
    except (OSError, UnicodeDecodeError) as error:
        raise ReplayRefused(
            f"the replay case {directory} declares a base commit in {declared} "
            f"that cannot be read: {error}"
        ) from None
    if not words:
        raise ReplayRefused(
            f"the replay case {directory} carries {_BASE_COMMIT_NAME} but it names "
            "no commit, so the case's claim about its own subject cannot be checked"
        )
    base = words[0]
    known = _git(cwd, "cat-file", "-t", base)
    if known.stdout.strip() == "commit":
        return
    raise ReplayRefused(
        f"the replay case {directory} was recorded against commit {base}, which "
        f"the repository at {cwd} does not carry: its recorded diffs belong to a "
        "different tree and would fail, several turns in, as a failed turn"
    )


def _refuse(reason: str) -> int:
    """One LOUD refusal on stderr; the shim never answers with an invention."""
    sys.stderr.write(
        f"WHAT: the inert shim cannot replay this turn.\n"
        f"WHY:  {reason}\n"
        f"HOW:  record the steps for real against THIS repository -- `des po`,\n"
        f"      `des design --value N`, `des oracle --value N`, `des craft\n"
        f"      --value N`, `des verify` -- then collect the turn records they\n"
        f"      wrote. Each step gets its OWN .nwave/des/logs/turns/<run-id>/\n"
        f"      directory numbered from 01, so copy the NN-<role>.json files out\n"
        f"      of every one of them, renumber into the order you invoked the\n"
        f"      steps in, add the candidate diff, put it in a new directory under\n"
        f"      scripts/analysis/k4/replay/ and point K4_INERT_REPLAY_DIR at it.\n"
        f"      Never author a record: an envelope no model produced makes every\n"
        f"      green downstream of it vacuous.\n"
    )
    return 3


# --- entry point ------------------------------------------------------------


def replay(argv: list[str], cwd: Path, config_dir: Path, role: str) -> int:
    """Answer ONE role turn with the envelope a real run recorded for it.

    The prompt arrives on stdin and is DRAINED, never parsed: draining it is the
    contract half this process owes its parent (`spawn` writes the prompt and
    closes the pipe, and a child that never reads a large prompt makes the
    parent's write fail), and parsing it would make a recording into an
    authority.  Only its size and digest reach the ledger, so a reader can tell
    whether the replayed turn was asked what the recorded turn was asked.
    """
    prompt = ""
    try:
        prompt = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        prompt = ""
    arm, pair = _identity(cwd)
    directory = _replay_dir()
    try:
        _admit_the_workspace(directory, cwd)
        occurrence = _next_occurrence(config_dir, role)
        record = _select_record(directory, role, occurrence)
        envelope = _recorded_envelope(record)
        # The bytes FIRST, the envelope second: a turn whose recorded effect
        # cannot be reproduced must not answer `accepted` over a workspace that
        # never received it.
        patch = _apply_recorded_patch(record, cwd)
    except ReplayRefused as refused:
        _ledger(
            {
                "kind": "replay",
                "arm": arm,
                "pair": pair,
                "cwd": str(cwd),
                "role": role,
                "replay_dir": str(directory),
                "refused": str(refused),
                "prompt_bytes": len(prompt),
                "is_error": True,
                "argv": argv,
                "spend_usd": 0.0,
            }
        )
        return _refuse(str(refused))
    _ledger(
        {
            "kind": "replay",
            "arm": arm,
            "pair": pair,
            "cwd": str(cwd),
            "role": role,
            "occurrence": occurrence,
            "record": str(record),
            "patch": patch,
            "prompt_bytes": len(prompt),
            "question_sha256": _question_digest(prompt),
            "recorded_question_sha256": _recorded_question_digest(record),
            "expected_historical_question_sha256": (
                _expected_historical_question_digest(record)
            ),
            "is_error": False,
            "argv": argv,
            "spend_usd": 0.0,
        }
    )
    sys.stdout.write(envelope)
    sys.stdout.flush()
    return 0


#: Facts the runner builds from WHERE and WHEN the turn runs, not from what it
#: asks.  A recording made in one directory and a replay made in another
#: disagree on these by construction, so a digest that included them could never
#: again say anything about the question -- it would only ever restate that the
#: two runs ran in different places.
#:
#: `repository_root` and `path_convention` state the turn's own absolute root.
#: `oracle_red` is the runner's own execution of the oracle, performed fresh in
#: every replay: MEASURED 2026-09-06 on this bundled case, its failure text
#: carries the pytest tmp root of the run that produced it
#: (`/tmp/pytest-of-<user>/pytest-<counter>/...`) and a live object address, so
#: two replays five minutes apart disagree on those bytes while asking the same
#: question.  Re-recording the turn would not repair that -- the next replay
#: would diverge again -- and backfilling the recorded prompt with one replay's
#: measurement would claim the recorded approval was given while reading
#: evidence that turn never saw, which is the fabrication this bundle's README
#: refuses.  That the field is delivered at all, and what it contains, is
#: asserted by `tests/des/unit/application/test_authored_oracle_is_executed_red.py`
#: against a controlled execution; this digest owns only "the recorded question
#: is still asked".
_RUN_LOCAL_FACTS = ("repository_root: ", "path_convention: ", "oracle_red: ")

#: Commit e1d6278c8 repaired the typed-design handoff: ``decisions`` and
#: ``obligations`` became distinct AuthorityFacts.  The named frozen records
#: pre-date that schema: their legacy ``obligations`` array is the decisions
#: payload, while their new obligations value is the empty array.  This is a
#: migration of exactly those historical questions, never a projection of a
#: newly asked question.
_LEGACY_DECISIONS_RECORDS = frozenset(
    {
        "03-nw-acceptance-designer.json",
        "05-nw-software-crafter.json",
    }
)
_LEGACY_DECISIONS_CASE = "graphify-callers-of-run17-run20"
_AUTHORITY_FACT_PREFIXES = (
    "authority: ",
    "targets: ",
    "paradigm: ",
    "decisions: ",
    "oracle: ",
    "acceptance_supports: ",
    "obligations: ",
)


def _question(prompt: str) -> str:
    """The part of a prompt that is the QUESTION, free of where it was asked."""
    return "\n".join(
        line for line in prompt.splitlines() if not line.startswith(_RUN_LOCAL_FACTS)
    )


def _question_digest(prompt: str) -> str:
    return hashlib.sha256(_question(prompt).encode("utf-8")).hexdigest()


def _recorded_question_digest(record: Path) -> str | None:
    """The digest of the question the RECORDED turn was given -- diagnostic only.

    Beside the replayed turn's own digest in the ledger, it says whether the
    runner asked the same question this time.  Nothing branches on it: a replay
    that only worked when the prompt matched byte for byte would be a fixture,
    not a replay of the software.
    """
    prompt = _recorded_question(record)
    if prompt is None:
        return None
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _expected_historical_question(record: Path) -> str | None:
    """Return this record's exact expected question under known schema history.

    Only the two frozen value-role records in the bundled case are migrated.
    Their legacy shape is checked before relocating the old ``obligations``
    JSON array to ``decisions`` and installing ``obligations: []``.  Any other
    record remains its own question; a malformed named legacy record returns
    ``None`` so the replay assertion fails rather than broadening equivalence.
    """
    question = _recorded_question(record)
    if question is None:
        return None
    frozen_case = Path(__file__).resolve().parent / "replay" / _LEGACY_DECISIONS_CASE
    if (
        record.name not in _LEGACY_DECISIONS_RECORDS
        or record.resolve() != (frozen_case / record.name).resolve()
    ):
        return question

    lines = question.splitlines()
    positions = {
        prefix: [i for i, line in enumerate(lines) if line.startswith(prefix)]
        for prefix in _AUTHORITY_FACT_PREFIXES
    }
    required = (
        "authority: ",
        "targets: ",
        "paradigm: ",
        "oracle: ",
        "acceptance_supports: ",
        "obligations: ",
    )
    if (
        any(len(positions[prefix]) != 1 for prefix in required)
        or positions["decisions: "]
    ):
        return None
    authority, targets, paradigm, oracle, supports, obligations = (
        positions[prefix][0] for prefix in required
    )
    if (authority, targets, paradigm, oracle, supports) != (1, 2, 3, 4, 5):
        return None
    legacy_payload = lines[obligations][len("obligations: ") :]
    try:
        if not isinstance(json.loads(legacy_payload), list):
            return None
    except json.JSONDecodeError:
        return None
    return "\n".join(
        (
            *lines[:oracle],
            f"decisions: {legacy_payload}",
            *lines[oracle:obligations],
            "obligations: []",
            *lines[obligations + 1 :],
        )
    )


def _expected_historical_question_digest(record: Path) -> str | None:
    """Digest the full expected historical question, if its shape is admissible."""
    question = _expected_historical_question(record)
    if question is None:
        return None
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def _recorded_question(record: Path) -> str | None:
    """Return the frozen envelope's question without mutating the envelope."""
    try:
        document = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    prompt = document.get("prompt")
    return _question(prompt) if isinstance(prompt, str) else None


def main(argv: list[str]) -> int:
    cwd = Path.cwd()
    task = _flag(argv, "-p") or ""
    arm, pair = _identity(cwd)
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", cwd / ".claude-k4"))

    # A turn addressed to a declared ROLE is the DES protocol, not the single
    # delivery the rest of this file answers: the runner spawns one `claude
    # --agent <role> --json-schema <schema>` per role and reads a
    # `structured_output` back.  Checked FIRST, because the delivery branch
    # below keys off the workspace and would answer a role turn with a payload
    # that carries no structured output at all -- measured 2026-09-05, that is
    # exactly the `ModelEnvelopeUnavailable` that stopped the offline campaign.
    role = _flag(argv, "--agent")
    if role is not None:
        return replay(argv, cwd, config_dir, role)

    if task.strip() == "Reply with exactly: OK":
        kind, result, error = "ping", "OK", False
    elif (cwd / "manage.py").is_file():
        kind = "delivery"
        try:
            result, error = _deliver(cwd, arm), False
        except DeliveryRefused as exc:
            result, error = f"INERT DELIVERY REFUSED: {exc}", True
    else:
        kind, result, error = "generic", "inert: nothing to do", False

    figures = _figures(arm, pair)
    if kind in ("ping", "generic"):
        cost, tokens, span, turns = 0.0021, 1500, 4.0, 1
    else:
        cost = round(figures["cost"], 6)
        tokens = int(figures["tokens"])
        span = figures["wall"]
        turns = 60 if arm == "control" else 91

    session_id = _session_id(cwd, kind)
    _write_transcript(config_dir, session_id, span)
    payload = _payload(
        session_id,
        result,
        cost=cost,
        tokens=tokens,
        duration_s=span,
        turns=turns,
        is_error=error,
    )
    _ledger(
        {
            "kind": kind,
            "arm": arm,
            "pair": pair,
            "cwd": str(cwd),
            "session_id": session_id,
            "is_error": error,
            "argv": argv,
            "spend_usd": 0.0,
        }
    )
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    # A real `claude -p` exits 0 even on `is_error`; the campaign's own
    # `_delivery_is_valid` is what refuses the record. Mirroring that keeps the
    # refusal on the harness's side, where production puts it.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
