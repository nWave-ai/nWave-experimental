#!/usr/bin/env python3
"""An INERT, deterministic stand-in for the `claude` binary -- zero model spend.

Every stage of the K4 chain that a paid campaign reaches through `claude` reaches
this instead: `paired_campaign._AUTH_PROBE`'s liveness ping, its per-arm headroom
probe, `preflight.probe_delivery_permissions`'s Edit/Write canary, and the timed
delivery itself. Nothing here talks to a provider; every number it emits is a
function of the workspace it was invoked in.

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
2. **The permission canary is obeyed, not enforced.** This shim performs the
   three canary file operations itself. It therefore proves the harness's
   canary plumbing (argv, cwd, env, verdict reading) and proves NOTHING about
   Claude's real sandbox policy -- the very thing the canary exists to observe.
3. **No subagents, no tools, no hooks.** The transcript is synthetic: the
   timestamps are computed, not observed, so the wall axis measures this file's
   arithmetic, not a real run's duration.

Stdlib only, no repo imports: it must run under whatever interpreter is first
on the arm's PATH.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


#: `preflight._PERMISSION_CANARY_RESULT`, verbatim. Duplicated rather than
#: imported: this file must stay importable-free of the repo, and the probe
#: (`offline_chain_probe.py`) asserts the two strings are equal so a drift
#: fails loud instead of turning the canary into a silent mismatch.
PERMISSION_CANARY_RESULT = "EDIT=OK WRITE=OK CONFIG_WRITE=DENIED"

#: The one fixed instant every synthetic transcript is anchored to, so two
#: runs of this probe produce byte-identical wall measurements.
_EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

#: Per-arm multipliers against the pair's own base figures. Chosen so ONE
#: campaign exercises BOTH verdict branches: cost and tokens land INSIDE their
#: 1.5x bounds while wall breaches its 2.0x bound. A profile where every axis
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


# --- the canary -------------------------------------------------------------


def _run_canary(cwd: Path) -> str:
    """Perform the three operations `probe_delivery_permissions` asserts.

    SIMPLER THAN REAL, and it matters: the real canary observes whether the
    Claude sandbox ALLOWS the two in-workspace writes and DENIES the config
    write. Here the writes are simply performed and the denied one is simply
    not performed, so this proves the harness's plumbing and nothing about the
    sandbox policy.
    """
    (cwd / "k4-permission-edit.txt").write_text("CANARY_AFTER\n", encoding="utf-8")
    (cwd / "k4-permission-write.txt").write_text("CANARY_WRITE_OK\n", encoding="utf-8")
    return PERMISSION_CANARY_RESULT


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


# --- entry point ------------------------------------------------------------


def main(argv: list[str]) -> int:
    cwd = Path.cwd()
    task = _flag(argv, "-p") or ""
    arm, pair = _identity(cwd)
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", cwd / ".claude-k4"))

    if task.strip() == "Reply with exactly: OK":
        kind, result, error = "ping", "OK", False
    elif "Permission canary only." in task:
        kind, result, error = "canary", _run_canary(cwd), False
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
    elif kind == "canary":
        cost, tokens, span, turns = 0.0184, 22000, 31.0, 3
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
