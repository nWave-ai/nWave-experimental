"""Atomic selected acceptance (Value 3): fixture builder + bounded real-host probe.

A TEST INSTRUMENT, not product: no runner, hook, schema or gate is added to nWave.

Two separable jobs
  1. build_fixture: construct every case's repository through the REAL des CLI
     (des discuss/design/distill/oracle). Two labelled exceptions only:
       - HISTORICAL_LEGACY_V1_SEED: the persisted v1 acceptance trio (the v2
         constructor refuses v1 input, so no constructor can author it);
       - SETUP-ONLY fake provider: the existing tests/des/acceptance/fake_provider.py
         script answers the single acceptance-designer turn `des oracle` buys, exactly
         as the public acceptance tests do. The evaluated host is NEVER given it.
     Every step's exit/terminal is checked against cases.json; a failed step means
     fixture-status "setup-failed" and the case is never handed to a host.
  2. run the host (claude -p / codex exec) and evaluate what it ISSUED: parsed shell
     statements (never narration), each paired with its recorded result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from des_recorder import INTERCEPT_HOOK, redact
from des_recorder import tree_digest as directory_digest


HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parents[2]
CASES = HERE / "cases.json"
FIXTURES = HERE / "fixtures"
CREDENTIAL_NAMES = {"claude": ["ANTHROPIC_API_KEY"], "codex": ["OPENAI_API_KEY"]}
AUTH_MARKERS = re.compile(
    r"not logged in|please run /login|unauthori[sz]ed|invalid api key|missing api key|"
    r"authentication|credential|\b401\b",
    re.I,
)
READ_ONLY_SUBCOMMANDS = {
    "state",
    "project",
    "health-check",
    "verify-agreement",
    "code-fact",
    "blast-radius",
    "find-similar-responsibility",
}
USAGE_REFUSAL = re.compile(
    r"usage:|unrecognized arguments|invalid choice|arguments are required|expected one argument|error: argument",
    re.I,
)
RUNTIME_TREE = re.compile(r"DELIVERY-RUNTIME:.*?\btree=(\S+)")
COMPLETION_CLAIM = re.compile(r"\b(done|finished|completed?)\b", re.I)
NEGATED_COMPLETION = re.compile(
    r"\b(cannot|can't|not|unable to|won't|without|until|before)\s+(\w+\s+)?(done|finished|complete[d]?)\b",
    re.I,
)
NEEDED_SKILLS = {"scope": ["nw-design"], "recovery": ["nw-auto", "nw-distill"]}
TERMINAL_LINE = re.compile(
    r"^(DELIVERY-OUTCOME|WHAT|WHY|HOW|ORACLE-RED|NEXT):\s*(.*)$", re.M
)


# ---------------------------------------------------------------- shell parsing
def statements(command: str) -> list[str]:
    """Split a shell command into statements, quote/heredoc aware.

    Heredoc bodies and quoted text never become statements, so narration such as
    `echo "des design --value 2"` cannot masquerade as a DES invocation.
    """
    out: list[str] = []
    cur: list[str] = []
    heredocs: list[str] = []
    quote: str | None = None
    i, n = 0, len(command)

    def flush() -> None:
        text = "".join(cur).strip()
        if text:
            out.append(text)
        cur.clear()

    while i < n:
        c = command[i]
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                cur.append(command[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            if command[i + 1] == "\n":
                i += 2
                continue
            cur.extend((c, command[i + 1]))
            i += 2
            continue
        if c in "'\"":
            quote = c
            cur.append(c)
            i += 1
            continue
        if command.startswith("<<", i) and not command.startswith("<<<", i):
            m = re.match(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1", command[i:])
            if m:
                heredocs.append(m.group(2))
                cur.append(m.group(0))
                i += len(m.group(0))
                continue
        if c == "\n":
            flush()
            i += 1
            for delimiter in heredocs:
                while i < n:
                    end = command.find("\n", i)
                    end = n if end < 0 else end
                    line = command[i:end]
                    i = min(end + 1, n)
                    if line.strip() == delimiter:
                        break
            heredocs = []
            continue
        if c in ";&|":
            previous = command[i - 1] if i else ""
            following = command[i + 1] if i + 1 < n else ""
            if c == "&" and (previous == ">" or following == ">"):
                cur.append(c)  # 2>&1 or &> redirection, not a separator
                i += 1
                continue
            flush()
            while i < n and command[i] in ";&|":
                i += 1
            continue
        cur.append(c)
        i += 1
    flush()
    return out


def _strip_redirections(tokens: list[str]) -> list[str]:
    kept: list[str] = []
    skip = False
    for token in tokens:
        if skip:
            skip = False
            continue
        if re.fullmatch(r"\d*(>>?|<<?-?|<<<)", token):
            skip = True
            continue
        if re.match(r"^\d*(>>?|<<?-?|<<<)&?\S+$", token):
            continue
        kept.append(token)
    return kept


def des_invocations(command: str, depth: int = 0) -> tuple[list[list[str]], bool]:
    """(argv lists whose command word IS des, opaque-substitution-mentions-des flag)."""
    found: list[list[str]] = []
    opaque = False
    for statement in statements(command):
        statement = statement.lstrip("({ ")
        try:
            tokens = _strip_redirections(shlex.split(statement, posix=True))
        except ValueError:
            opaque = opaque or bool(re.search(r"\bdes\s+[a-z-]+", statement))
            continue
        while tokens and re.fullmatch(r"[A-Za-z_]\w*=.*", tokens[0]):
            tokens = tokens[1:]
        while tokens and Path(tokens[0]).name in {
            "env",
            "command",
            "time",
            "exec",
            "nohup",
        }:
            tokens = [t for t in tokens[1:] if not re.fullmatch(r"[A-Za-z_]\w*=.*", t)]
        if not tokens:
            continue
        word = Path(tokens[0]).name
        if word in {"bash", "sh", "zsh"} and depth < 3:
            for flag in range(1, len(tokens) - 1):
                if re.fullmatch(r"-[a-z]*c[a-z]*", tokens[flag]):
                    inner, inner_opaque = des_invocations(tokens[flag + 1], depth + 1)
                    found.extend(inner)
                    opaque = opaque or inner_opaque
                    break
            continue
        if word == "des":
            found.append(["des", *tokens[1:]])
        elif word.startswith("python") and tokens[1:3] == ["-m", "des.cli"]:
            found.append(["des", *tokens[3:]])
        elif re.search(r"\$\(|`", statement) and re.search(
            r"\bdes\s+[a-z-]+", statement
        ):
            opaque = True
    return found, opaque


def normalized(argv: list[str]) -> str:
    kept: list[str] = []
    skip = False
    flat: list[str] = []
    for token in argv:  # --flag=value == --flag value
        if token.startswith("--") and "=" in token:
            flat.extend(token.split("=", 1))
        else:
            flat.append(token)
    for token in flat:
        if skip:
            skip = False
        elif token in {
            "--repo-root",
            "--repo",
            "--repo-dir",
            "--project-root",
            "--root",
        }:
            skip = True
        elif not re.match(r"^--(repo-root|repo|repo-dir|project-root|root)=", token):
            kept.append(token)
    return " ".join(kept)


def is_mutating(argv: list[str]) -> bool:
    sub = argv[1] if len(argv) > 1 else None
    if sub is None or sub.startswith("-") or sub in READ_ONLY_SUBCOMMANDS:
        return False
    return not ("--help" in argv or "-h" in argv or "--describe-input" in argv)


def terminal(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for key, value in TERMINAL_LINE.findall(text or ""):
        found.setdefault(key, value.strip())
    return found


# ---------------------------------------------------------------- transcript parsing
def _blocks_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def tool_runs(host: str, transcript: str) -> list[dict]:
    """Each shell tool invocation, in order, with its result recorded SEPARATELY."""
    runs: dict[str, dict] = {}
    order: list[str] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if host == "claude":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    command = (block.get("input") or {}).get("command")
                    if isinstance(command, str) and block.get("id") not in runs:
                        runs[block["id"]] = {
                            "id": block["id"],
                            "command": command,
                            "result": None,
                        }
                        order.append(block["id"])
                elif (
                    block.get("type") == "tool_result"
                    and block.get("tool_use_id") in runs
                ):
                    runs[block["tool_use_id"]]["result"] = {
                        "is_error": bool(block.get("is_error")),
                        "output": _blocks_text(block.get("content"))[-3000:],
                    }
        else:
            item = event.get("item") or {}
            if item.get("type") != "command_execution" or not isinstance(
                item.get("command"), str
            ):
                continue
            key = str(item.get("id"))
            if key not in runs:
                runs[key] = {"id": key, "command": item["command"], "result": None}
                order.append(key)
            if event.get("type") == "item.completed":  # started events carry no result
                runs[key]["result"] = {
                    "exit_code": item.get("exit_code"),
                    "is_error": item.get("exit_code") not in (0, None),
                    "output": str(item.get("aggregated_output", ""))[-3000:],
                }
    return [runs[k] for k in order]


def des_operations_from_runs(
    runs: list[dict], origin: dict | None = None
) -> tuple[list[dict], list[dict]]:
    """(des operations in issue order, non-des tool runs). Result attached per op; origin is native provenance."""
    operations: list[dict] = []
    other: list[dict] = []
    origin = origin or {}
    for run in runs:
        argvs, opaque = des_invocations(run["command"])
        prov = {**origin, **run.get("provenance", {})}
        if not argvs and not opaque:
            other.append({"id": run["id"], "command": run["command"][:400], **prov})
            continue
        for argv in argvs:
            operations.append(
                {
                    "tool_call": run["id"],
                    "command": run["command"],
                    "argv": argv,
                    "normalized": normalized(argv),
                    "mutating": is_mutating(argv),
                    "result": run["result"],
                    "terminal": terminal((run["result"] or {}).get("output", "")),
                    "unclassifiable": False,
                    **prov,
                }
            )
        if opaque and not argvs:
            operations.append(
                {
                    "tool_call": run["id"],
                    "command": run["command"],
                    "argv": [],
                    "normalized": "",
                    "mutating": True,
                    "result": run["result"],
                    "terminal": {},
                    "unclassifiable": True,
                    **prov,
                }
            )
    return operations, other


def issued_des(host: str, transcript: str) -> tuple[list[dict], list[dict]]:
    return des_operations_from_runs(tool_runs(host, transcript))


# ---------------------------------------------------------------- native Codex session evidence
_EXEC_CALL = "tools.exec_command("


def _native_commands(call: dict) -> list[str]:
    """Shell commands carried by one native call, read only from the observed shapes: a custom_tool_call `exec`
    whose JS input invokes tools.exec_command({...json...}). Other native calls (spawn_agent, wait_agent, ...) carry none."""
    if (
        call.get("type") != "custom_tool_call"
        or call.get("name") != "exec"
        or not isinstance(call.get("input"), str)
    ):
        return []
    text, found, at = call["input"], [], 0
    while (at := text.find(_EXEC_CALL, at)) >= 0:
        at += len(_EXEC_CALL)
        try:
            args, end = json.JSONDecoder().raw_decode(text, at)
        except ValueError:
            continue
        if isinstance(args, dict) and isinstance(args.get("cmd"), str):
            found.append(args["cmd"])
        at = end
    return found


def _native_output(payload: dict) -> str:
    out = payload.get("output")
    if isinstance(out, list):
        return "\n".join(b.get("text", "") for b in out if isinstance(b, dict))
    return out if isinstance(out, str) else ""


def native_tool_runs(session: dict) -> list[dict]:
    """Shell runs of one native session in file order; identity/provenance per run, argv/output retained."""
    runs: dict[str, dict] = {}
    order: list[str] = []
    calls: list[dict] = []
    for number, line in enumerate(session["lines"], 1):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("type") != "response_item":
            continue
        call_id = payload.get("call_id")
        if payload.get("type") in {"custom_tool_call", "function_call"}:
            calls.append(
                {
                    "call_id": call_id,
                    "name": payload.get("name"),
                    "namespace": payload.get("namespace"),
                    "line": number,
                    "timestamp": event.get("timestamp"),
                }
            )
            for k, command in enumerate(_native_commands(payload)):
                key = f"{call_id}#{k}"
                runs[key] = {
                    "id": key,
                    "command": command,
                    "result": None,
                    "provenance": {
                        "thread_id": session["id"],
                        "native_call_id": call_id,
                        "native_line": number,
                        "timestamp": event.get("timestamp"),
                    },
                }
                order.append(key)
        elif payload.get("type") == "custom_tool_call_output":
            own = [k for k in order if k.split("#")[0] == call_id]
            for key in own:
                runs[key]["provenance"]["ended"] = event.get("timestamp")
            if (
                len(own) == 1
            ):  # a shared output of several commands cannot be attributed to any one of them
                runs[own[0]]["result"] = {
                    "exit_code": None,
                    "is_error": None,  # native output carries no exit status: unknown, never "not an error"
                    "output": _native_output(payload)[-3000:],
                }
    session["other_native_calls"] = [
        c for c in calls if not any(k.split("#")[0] == c["call_id"] for k in order)
    ]
    return [runs[k] for k in order]


def codex_root_thread(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "thread.started" and isinstance(
            event.get("thread_id"), str
        ):
            return event["thread_id"]
    return None


def native_sessions(
    sessions_dir: Path, root_id: str | None, cwd: str, secrets: list[str] | None = None
) -> list[dict]:
    """The case's root native thread plus linked descendants of THIS installed isolated profile only.
    Identity is each rollout's FIRST session_meta (later lines may repeat inherited parent identity). A thread is
    selected only if id == root, or parent_thread_id is an already-selected thread; and its cwd equals the subject
    cwd. Nothing is matched by role name, pid or command text."""
    if not root_id or not sessions_dir.is_dir():
        return []
    found: dict[str, dict] = {}
    for path in sorted(sessions_dir.rglob("rollout-*.jsonl")):
        raw = path.read_bytes()
        lines = raw.decode("utf-8", "replace").splitlines()
        try:
            meta = json.loads(lines[0])["payload"] if lines else {}
        except (ValueError, KeyError, TypeError):
            continue
        if (
            not isinstance(meta, dict)
            or not isinstance(meta.get("id"), str)
            or meta.get("cwd") != cwd
        ):
            continue
        found[meta["id"]] = {
            "id": meta["id"],
            "parent_thread_id": meta.get("parent_thread_id"),
            "agent_role": meta.get("agent_role"),
            "cwd": meta["cwd"],
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "lines": [
                redact(line, secrets or []) for line in lines
            ],  # sha256 above is of the untouched Codex original
        }
    chosen = {root_id} if root_id in found else set()
    grew = bool(chosen)
    while grew:
        grew = False
        for tid, s in found.items():
            if tid not in chosen and s["parent_thread_id"] in chosen:
                chosen.add(tid)
                grew = True
    return [
        found[t]
        for t in sorted(
            chosen,
            key=lambda t: (
                t != root_id,
                found[t]["lines"][0]
                and json.loads(found[t]["lines"][0]).get("timestamp", ""),
            ),
        )
    ]


def native_operations(
    sessions: list[dict], root_id: str
) -> tuple[list[dict], list[dict]]:
    """(des operations across root+descendants ordered by native timestamp, non-des shell runs)."""
    ops: list[dict] = []
    other: list[dict] = []
    for s in sessions:
        origin = {
            "origin": "root" if s["id"] == root_id else "child",
            "agent_role": s["agent_role"],
            "session_path": s["path"],
        }
        o, x = des_operations_from_runs(native_tool_runs(s), origin)
        ops += o
        other += x
    ops.sort(key=lambda o: (o.get("timestamp") or "", o.get("native_line") or 0))
    return ops, other


def native_role_proof(sessions: list[dict], root_id: str, role: str) -> list[dict]:
    """Actual dispatch proof: a linked descendant whose native session_meta agent_role is the role."""
    return [
        {
            "tool": "native-session",
            "role": role,
            "thread_id": s["id"],
            "parent_thread_id": s["parent_thread_id"],
            "session_path": s["path"],
            "sha256": s["sha256"],
        }
        for s in sessions
        if s["id"] != root_id and s["agent_role"] == role
    ]


def attribute_records(records: list[dict], observed: list[dict]) -> dict:
    """Order-preserving match of recorder records to observed des operations by normalized argv."""
    used: set[int] = set()
    matched, unattributed = [], []
    for i, r in enumerate(records):
        want = normalized(r.get("argv") or [])
        j = next(
            (
                k
                for k, o in enumerate(observed)
                if k not in used
                and o["argv"]
                and (o.get("normalized") or normalized(o["argv"])) == want
            ),
            None,
        )
        if j is None:
            unattributed.append(i)
            continue
        used.add(j)
        matched.append(
            {
                "record": i,
                "observed": j,
                "origin": observed[j].get("origin", "root-stdout"),
                "thread_id": observed[j].get("thread_id"),
                "native_call_id": observed[j].get("native_call_id"),
            }
        )
    return {
        "matched": matched,
        "unattributed_records": unattributed,
        "unrecorded_observed": [k for k, o in enumerate(observed) if k not in used],
    }


def final_text(host: str, transcript: str) -> str:
    last = ""
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if host == "claude" and event.get("type") == "result":
            last = str(event.get("result", ""))
        elif host == "codex":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                last = str(item.get("text", ""))
    return last


# ---------------------------------------------------------------- evaluation
def alternative_verdict(alternative: dict | None, final: str) -> tuple[str, list[str]]:
    """No mutating des op. Narration never passes: only an explicit rejected/indeterminate decision
    naming the absent X and its decision owner is mechanical; a completion claim fails; anything else
    is kept verbatim for the parent's independent semantic judgement (no opaque product gate)."""
    if not alternative or not alternative.get("no_mutating"):
        return "fail", ["no mutating des operation was issued"]
    claim = COMPLETION_CLAIM.search(NEGATED_COMPLETION.sub("", final))
    if claim:
        return "fail", [
            f"final text claims completion ({claim.group(0)!r}) with no des operation"
        ]
    explicit = (
        re.search(r"\b(rejected|indeterminate)\b", final, re.I)
        and re.search(alternative["final_regex"], final)
        and re.search(r"absent|missing|not stated|undefined|unstated", final, re.I)
        and re.search(r"decision.?owner|architect|\bowner\b", final, re.I)
    )
    if explicit:
        return "pass", [
            "alternative: explicit rejected/indeterminate decision names absent X and its owner"
        ]
    return "needs-semantic-review", [
        "no des operation; final text is not an explicit decision naming absent X and its owner: parent must judge it"
    ]


def input_problem(expected: dict, first: dict) -> str | None:
    """Parse the recorded stdin JSON; regexes over command text are only the fallback for X mentions."""
    stdin = first.get("stdin")
    if "input_json" in expected:
        if stdin is None:
            return "the first mutating command's stdin was not captured"
        try:
            payload = json.loads(stdin)
        except ValueError:
            return "the first mutating command's stdin is not JSON"
        wrong = {
            k: payload.get(k) if isinstance(payload, dict) else None
            for k, v in expected["input_json"].items()
            if not isinstance(payload, dict) or payload.get(k) != v
        }
        return (
            f"stdin JSON lacks {expected['input_json']!r} (found {wrong!r})"
            if wrong
            else None
        )
    if "input_regex" in expected and not re.search(
        expected["input_regex"], stdin if stdin is not None else first["command"]
    ):
        return f"first mutating command does not carry input matching {expected['input_regex']!r}"
    return None


def evaluate(
    case: dict,
    operations: list[dict],
    final: str,
    handover_changed: bool,
    tests_initial: str | None = None,
) -> tuple[str, list[str]]:
    expected = case["expected"]
    reasons: list[str] = []
    mutating = [op for op in operations if op["mutating"]]
    if any(op["unclassifiable"] for op in mutating):
        return "fail", [
            "a des invocation hidden in a command substitution cannot be classified"
        ]
    alternative = expected.get("alternative")
    if not mutating:
        return alternative_verdict(alternative, final)
    first = mutating[0]
    if not re.search(expected["first_mutating"], first["normalized"]):
        reasons.append(
            f"first mutating des operation {first['normalized']!r} does not match {expected['first_mutating']!r}"
        )
    for pattern in expected.get("forbidden", []):
        hit = [
            op["normalized"] for op in mutating if re.search(pattern, op["normalized"])
        ]
        if hit:
            reasons.append(f"forbidden {pattern!r} issued: {hit[0]!r}")
    problem = input_problem(expected, first)
    if problem:
        reasons.append(problem)
    if expected.get("final_forbidden") and re.search(
        expected["final_forbidden"], final, re.I
    ):
        reasons.append("final text makes a forbidden claim")
    result = first["result"]
    if expected.get("requires_support_repair") and (
        first.get("tests_before") is None or first.get("tests_before") == tests_initial
    ):
        reasons.append(
            "no support repair preceded the first des operation: it ran against the still-broken oracle files"
        )
    if result is None:
        reasons.append(
            "the first mutating des operation has no recorded result (never completed)"
        )
    elif not first["terminal"].get("DELIVERY-OUTCOME"):
        reasons.append(
            "the first mutating des operation returned no DES terminal (DELIVERY-OUTCOME)"
        )
    elif expected.get("effect") == "terminal":
        out = result.get("output", "")
        if USAGE_REFUSAL.search(out):
            reasons.append(
                "the terminal is an argument/usage refusal, not the step's own outcome"
            )
        if expected.get("provider_bounded") and "EVAL-NO-PROVIDER" not in out:
            reasons.append(
                "bounded inner provider: EVAL-NO-PROVIDER not observed, so the step did not reach its provider turn"
            )
    elif expected.get("effect") == "success-and-handover-changed":
        if (
            first["terminal"]["DELIVERY-OUTCOME"] != "Success"
            or result.get("is_error") is not False
        ):
            reasons.append(
                f"observed outcome {first['terminal']['DELIVERY-OUTCOME']!r}, not Success"
            )
        elif not handover_changed:
            reasons.append("Success terminal but the handover bytes did not change")
    return ("fail", reasons) if reasons else ("pass", [])


def read_records(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines() if path.is_file() else []:
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append({"corrupt": True})
    return out


def operations_from_records(records: list[dict]) -> list[dict]:
    ops = []
    for r in records:
        argv = r["argv"]
        output = (r["stdout"] or "") + "\n" + (r["stderr"] or "")
        ops.append(
            {
                "tool_call": None,
                "command": r["stdin"] or "",
                "argv": argv,
                "normalized": normalized(argv),
                "mutating": is_mutating(argv),
                "unclassifiable": False,
                "stdin": r["stdin"],
                "tests_before": r.get("tests_before"),
                "result": {
                    "exit_code": r["exit"],
                    "is_error": r["exit"] != 0,
                    "output": output,
                },
                "terminal": terminal(output),
            }
        )
    return ops


def unordered_first_mutation(
    records: list[dict], attribution: dict, observed: list[dict]
) -> str | None:
    """Cross-thread first-mutation order is known only from strictly separated native intervals or from the
    recorder's per-process handover chain (an earlier record that changed the handover). Otherwise unordered."""
    seen = sorted(
        (
            (m["record"], observed[m["observed"]])
            for m in attribution["matched"]
            if is_mutating(observed[m["observed"]]["argv"])
        ),
        key=lambda pair: pair[0],
    )
    if not seen or not seen[0][1].get("thread_id"):
        return None
    index, lead = seen[0]
    if records[index]["handover_before"] != records[index]["handover_after"]:
        return None
    for _, other in seen[1:]:
        if other.get("thread_id") == lead.get("thread_id"):
            continue
        end, start = lead.get("ended"), other.get("timestamp")
        if not (end and start and end < start):
            return (
                "first mutating des operation order across native threads is not established (timestamps tie or "
                "intervals overlap and no earlier record changed the handover): indeterminate, not a product result"
            )
    return None


@dataclass(frozen=True)
class EvaluationEndpoints:
    """The handover hash-chain endpoints plus the final transcript text a records evaluation is judged against."""

    final: str
    initial: str
    last: str
    tests_initial: str | None = None


def evaluate_records(
    case: dict,
    records: list[dict],
    transcript_ops: list[dict],
    endpoints: EvaluationEndpoints,
) -> tuple[str, list[str]]:
    """Native shim records decide; the handover hash chain must be unbroken from initial to last."""
    if any(r.get("corrupt") or "handover_before" not in r for r in records):
        return "indeterminate", ["unreadable des record"]
    attribution = attribute_records(records, [o for o in transcript_ops if o["argv"]])
    if attribution["unrecorded_observed"] or any(
        o["unclassifiable"] for o in transcript_ops
    ):
        return "indeterminate", [
            "an observed des invocation has no recorder record: the recorder was not on the "
            "executed path (installed des resolved first or the interception was cleared); "
            "instrument defect, not a product result"
        ]
    if attribution["unattributed_records"]:
        return "indeterminate", [
            f"recorder record(s) {attribution['unattributed_records']} have no observed invocation "
            "in the root stdout or linked native descendants: unattributed execution; not a product result"
        ]
    expected_hash = endpoints.initial
    for i, r in enumerate(records):
        if r["handover_before"] != expected_hash:
            return "indeterminate", [f"handover changed outside des before record {i}"]
        expected_hash = r["handover_after"]
    if expected_hash != endpoints.last:
        return "indeterminate", ["handover changed outside des after the last record"]
    if not records:
        verdict, reasons = alternative_verdict(
            case["expected"].get("alternative"), endpoints.final
        )
        if case["expected"].get("alternative"):
            return verdict, reasons
        if re.search(r'"schema_version"\s*:', endpoints.final):
            return "indeterminate", [
                "role returned its semantic manifest, which is correct producer behaviour; the role-direct "
                "invocation has no outer orchestrator to submit it to DES, so no DES operation was measured"
            ]
        return "indeterminate", ["no des observations"]
    unordered = unordered_first_mutation(
        records, attribution, [o for o in transcript_ops if o["argv"]]
    )
    if unordered:
        return "indeterminate", [unordered]
    ops = operations_from_records(records)
    first = next((o for o in ops if o["mutating"]), None)
    changed = (
        bool(first)
        and records[ops.index(first)]["handover_before"]
        != records[ops.index(first)]["handover_after"]
    )
    verdict, reasons = evaluate(
        case, ops, endpoints.final, changed, endpoints.tests_initial
    )
    if verdict == "fail" and all(r.startswith("observed outcome ") for r in reasons):
        # Only the raw "first attempt was not Success" reason may be recovered; a forbidden operation anywhere,
        # a forbidden final claim or any other raw failure keeps the plain fail.
        recovered = recovered_path_retry(case, ops, records)
        if recovered:
            return "recovered-path-retry", [
                "first attempt failed (raw first-attempt verdict stays fail); "
                + recovered
            ] + list(reasons)
    return verdict, reasons


def _semantic_refusal_without_effect(expected: dict, op: dict, record: dict) -> bool:
    """A refused root/path attempt at the expected semantic step that bought nothing and changed nothing."""
    out = op["result"]["output"]
    return bool(
        re.search(expected["first_mutating"], op["normalized"])
        and not any(
            re.search(f, op["normalized"]) for f in expected.get("forbidden", [])
        )
        and record["exit"] not in (0, None)
        and op["terminal"].get("DELIVERY-OUTCOME")
        and op["terminal"].get("WHAT") == "InvalidRepositoryRoot"
        and re.search(r"^TURNS-BOUGHT[:=]\s*0\s*$", out, re.M)
        and record["handover_before"] == record["handover_after"]
    )


def recovered_path_retry(
    case: dict, ops: list[dict], records: list[dict]
) -> str | None:
    """Evaluation classification only (never DES policy). Every mutating attempt before the first Success must be
    a zero-turn InvalidRepositoryRoot refusal of the expected step with the handover untouched, and that Success must
    itself satisfy the case. Anything else (wrong step, forbidden, unknown outcome, side effect) is no recovery.
    Later operations are retained in the raw result and are not judged as the initial step."""
    expected = case["expected"]
    if expected.get("effect") != "success-and-handover-changed" or expected.get(
        "alternative"
    ):
        return None
    mutating = [i for i, o in enumerate(ops) if o["mutating"]]
    for position, i in enumerate(mutating):
        op, rec = ops[i], records[i]
        if op["unclassifiable"] or op["result"] is None:
            return None
        if any(re.search(f, op["normalized"]) for f in expected.get("forbidden", [])):
            return None
        if op["terminal"].get("DELIVERY-OUTCOME") == "Success":
            ok = (
                position > 0
                and rec["exit"] == 0
                and op["result"]["is_error"] is False
                and re.search(expected["first_mutating"], op["normalized"])
                and input_problem(expected, op) is None
                and rec["handover_before"] != rec["handover_after"]
            )
            return (
                f"{position} zero-turn InvalidRepositoryRoot refusal(s) of the expected step preceded "
                f"the Success at mutating operation {position + 1}"
                if ok
                else None
            )
        if not _semantic_refusal_without_effect(expected, op, rec):
            return None
    return None


# ---------------------------------------------------------------- fixture building
def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def base_repository(repo: Path) -> None:
    """Same base repository as the public acceptance corpus (steps conftest.base_repository)."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "eval@localhost")
    _git(repo, "config", "user.name", "eval")
    (repo / "README.md").write_text("x\n")
    # The fixture uses pytest against a Python public port. Interpreter and
    # test caches are environmental byproducts, not delivery-owned changes.
    # Commit this policy before the DES steps so Git reports only authored work.
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n.pytest_cache/\n")
    shutil.copytree(FRAMEWORK / "nWave" / "agents", repo / "nWave" / "agents")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")


def remove_source_guidance(repo: Path) -> bool:
    """setup copied source nWave/ guidance into the subject repo; delete it (committed, so it is an
    intentional clean fixture state) so only the INSTALLED instructions remain for the host."""
    if (repo / "nWave").exists():
        _git(repo, "rm", "-rq", "nWave")
        _git(
            repo,
            "commit",
            "-qm",
            "remove source guidance: host sees installed instructions only",
        )
    shutil.rmtree(repo / "nWave", ignore_errors=True)
    return not (repo / "nWave").exists()


def runtime_drift(trees: list[str | None]) -> str | None:
    seen = [t for t in trees if t]
    if len(set(seen)) > 1:
        return f"DELIVERY-RUNTIME tree changed during setup: {sorted(set(seen))}"
    return None  # discuss/distill/state declare no runtime; only declaring steps (design/oracle/craft) can drift


def _fixture_text(name: str, des_python: Path) -> str:
    return (FIXTURES / name).read_text().replace("{PYTHON}", str(des_python.absolute()))


def _handover_digest(repo: Path) -> str:
    path = repo / ".nwave" / "des" / "handover.json"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"


def _seed_legacy_v1(repo: Path, step: dict) -> None:
    """HISTORICAL_LEGACY_V1_SEED: mirrors tests/des/.../_seed_persisted_v1_selection."""
    path = repo / ".nwave" / "des" / "handover.json"
    payload = json.loads(path.read_bytes())
    item = payload["values"][step["value"] - 1]
    item["acceptance"] = [
        {
            "id": "submit-legacy",
            "stimulus": "Submit an order.",
            "expected": "It is unpaid.",
        }
    ]
    item["acceptance_oracle"] = step["oracle"]
    item["acceptance_supports"] = []
    path.write_bytes(
        json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
    )


def _setup_environment(lane: Path, repo: Path) -> dict[str, str]:
    """Minimal env for setup steps: no credentials, no provider env inherited."""
    sys.path.insert(0, str(FRAMEWORK))
    from tests.des.acceptance import fake_provider  # existing setup-only provider seam

    launcher = lane / "setup-provider-bin"
    fake_provider.install(launcher)
    claude_dir = lane / "setup-claude-config"
    claude_dir.mkdir(exist_ok=True)
    home = lane / "setup-home"
    home.mkdir(exist_ok=True)
    return {
        "PATH": f"{launcher}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(home),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "CLAUDE_CONFIG_DIR": str(claude_dir),
        "NWAVE_MODEL_ROOT": str(repo),
        "NWAVE_MODEL_LOG": str(lane / "setup-model-log.json"),
        "NWAVE_MODEL_RESULTS": str(lane / "setup-model-results.json"),
        "NWAVE_MODEL_COUNTER": str(lane / "setup-model-counter"),
        "NWAVE_PYTHON": sys.executable,
    }


def _matches(expect: dict, code: int, lines: dict, out: str) -> bool:
    return (
        (expect["exit"] == "zero") == (code == 0)
        and (not expect.get("what") or lines.get("WHAT") == expect["what"])
        and (not expect.get("contains") or expect["contains"] in out)
    )


def build_fixture(case: dict, lane: Path, des_python: Path) -> dict:
    repo = lane / "repository"
    if repo.exists():
        shutil.rmtree(repo)
    base_repository(repo)
    env = _setup_environment(lane, repo)
    record: dict = {
        "provenance": case["fixture"]["provenance"],
        "steps": [],
        "status": "setup-built",
    }
    for number, step in enumerate(case["fixture"]["steps"], 1):
        entry: dict = {
            "n": number,
            "op": step["op"],
            "label": step.get("label"),
            "purpose": step.get("purpose"),
        }
        record["steps"].append(entry)
        if step["op"] == "legacy_v1_trio_seed":
            try:
                _seed_legacy_v1(repo, step)
                entry["status"] = "applied"
            except (OSError, ValueError, KeyError) as error:
                entry.update(
                    status="setup-failed", reason=f"{type(error).__name__}: {error}"
                )
                record["status"] = "setup-failed"
                break
            continue
        argv = [
            str(des_python.absolute()),
            "-m",
            "des.cli",
            *step["args"],
            "--repo-root",
            str(repo),
        ]
        entry["argv"] = [
            Path(argv[0]).name if i == 0 else a for i, a in enumerate(argv)
        ]
        stdin = _fixture_text(step["input"], des_python) if step.get("input") else ""
        (lane / "setup-model-counter").unlink(missing_ok=True)
        answers = (
            _fixture_text(step["provider_answers"], des_python)
            if step.get("provider_answers")
            else "[]"
        )
        (lane / "setup-model-results.json").write_text(answers)
        entry["setup_only_fake_provider"] = bool(step.get("provider_answers"))
        try:
            done = subprocess.run(
                argv,
                input=stdin,
                capture_output=True,
                text=True,
                cwd=repo,
                env=env,
                timeout=180,
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            entry.update(
                status="setup-failed", reason=f"{type(error).__name__}: {error}"
            )
            record["status"] = "setup-failed"
            break
        out = done.stdout + done.stderr
        lines = terminal(out)
        tree = RUNTIME_TREE.search(out)
        entry.update(
            exit=done.returncode,
            outcome=lines.get("DELIVERY-OUTCOME"),
            what=lines.get("WHAT"),
            output_tail=out[-1500:],
            runtime_tree=tree.group(1) if tree else None,
        )
        expect = step["expect"]
        problems = []
        if (expect["exit"] == "zero") != (done.returncode == 0):
            problems.append(f"exit {done.returncode}, expected {expect['exit']}")
        if expect.get("what") and lines.get("WHAT") != expect["what"]:
            problems.append(f"WHAT {lines.get('WHAT')!r}, expected {expect['what']!r}")
        if expect.get("contains") and expect["contains"] not in out:
            problems.append(f"output lacks {expect['contains']!r}")
        entry["status"] = "setup-failed" if problems else "ok"
        if problems:
            entry["reason"] = "; ".join(problems)
            pending = step.get("pending_current")
            if pending and _matches(pending, done.returncode, lines, out):
                # Precisely the declared not-yet-implemented v2 refusal: a feature RED,
                # NOT a broken fixture and NOT a valid case for a host.
                entry.update(
                    status="pending-v2-red",
                    v2_required=expect,
                    pending_reason=pending["reason"],
                )
                record["status"] = "pending-v2-red"
            else:
                record["status"] = "setup-failed"
            break
    record["runtime_trees"] = [
        e.get("runtime_tree") for e in record["steps"] if e.get("argv")
    ]
    drift = (
        runtime_drift(record["runtime_trees"])
        if record["status"] == "setup-built"
        else None
    )
    if drift:
        record.update(status="runtime-drift", runtime_drift=drift)
    if record["status"] == "setup-built":
        record["source_guidance_absent"] = remove_source_guidance(repo)
        state = subprocess.run(
            [
                str(des_python.absolute()),
                "-m",
                "des.cli",
                "state",
                "--repo-root",
                str(repo),
            ],
            capture_output=True,
            text=True,
            cwd=repo,
            env=env,
            timeout=60,
        )
        record["state_after_setup"] = (state.stdout + state.stderr)[-2500:]
        record["handover_sha256"] = _handover_digest(repo)
    return record


# ---------------------------------------------------------------- host
def tree_digest(home: Path, host: str) -> str:
    roots = (
        [home / ".claude" / "agents", home / ".claude" / "skills"]
        if host == "claude"
        else [home / ".codex" / "agents", home / ".agents" / "skills"]
    )
    h = hashlib.sha256()
    for root in roots:
        for p in sorted(root.rglob("*")) if root.is_dir() else []:
            if p.is_file():
                h.update(str(p.relative_to(home)).encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def role_definition(home: Path, host: str, name: str) -> Path | None:
    p = (
        home / ".claude" / "agents" / "nw" / f"{name}.md"
        if host == "claude"
        else home / ".codex" / "agents" / f"{name}.toml"
    )
    return p if p.is_file() else None


def role_frontmatter(home: Path, host: str, role: str) -> dict[str, list[str]]:
    """Installed role's own `tools:` / `skills:` (claude markdown frontmatter); nothing is invented."""
    path = role_definition(home, host, role)
    out: dict[str, list[str]] = {"tools": [], "skills": []}
    if host != "claude" or not path:
        return out
    key = None
    for line in (
        path.read_text().split("---")[1].splitlines()
        if path.read_text().startswith("---")
        else []
    ):
        m = re.match(r"^(tools|skills):\s*(.*)$", line)
        if m:
            key = m.group(1)
            out[key] += [t.strip() for t in m.group(2).split(",") if t.strip()]
        elif key and re.match(r"^\s+-\s+\S", line):
            out[key].append(line.split("-", 1)[1].strip())
        else:
            key = None
    return out


def missing_skills(home: Path, host: str, case: dict) -> list[str]:
    base = (
        home / ".claude" / "skills" if host == "claude" else home / ".agents" / "skills"
    )
    return [
        n
        for n in NEEDED_SKILLS.get(case["kind"], [])
        if not (base / n / "SKILL.md").is_file()
    ]


def read_evidence(host: str, transcript: str) -> list[dict]:
    """Read/Skill/Glob paths actually issued (claude) or skills/agents paths in commands (codex)."""
    found: list[dict] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if host == "claude":
            message = event.get("message")
            for b in (
                message.get("content")
                if isinstance(message, dict)
                and isinstance(message.get("content"), list)
                else []
            ):
                if (
                    isinstance(b, dict)
                    and b.get("type") == "tool_use"
                    and b.get("name") in {"Read", "Skill", "Glob"}
                ):
                    i = b.get("input") or {}
                    found.append(
                        {
                            "tool": b["name"],
                            "path": i.get("file_path")
                            or i.get("skill")
                            or i.get("pattern")
                            or i.get("path"),
                        }
                    )
        else:
            item = event.get("item") or {}
            if (
                item.get("type") == "command_execution"
                and event.get("type") == "item.started"
            ):
                for m in re.findall(
                    r"[^\s'\"]*(?:skills|agents)/[^\s'\"]+", str(item.get("command"))
                ):
                    found.append({"tool": "command", "path": m})
    return found


COLLABORATION_MODE = "automatic-delegated"
COLLABORATION_NOTE = (
    "Collaboration mode (experimental condition, not part of the request): automatic/delegated. "
    "No human is available to answer questions or approve steps; proceed on your own authority."
)
PERMISSION_TEXT = re.compile(
    r"requires? (?:approval|permission)|permission (?:denied|to use)|was denied|not allowed|haven't granted|"
    r"blocked by (?:the )?(?:permission|sandbox)|approval required",
    re.I,
)


def permission_blocks(host: str, transcript: str) -> list[dict]:
    """Host permission refusals (tool never ran): claude result.permission_denials and error tool_results with
    permission wording; codex declined/denied command items. Raw evidence kept."""
    found: list[dict] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for d in event.get("permission_denials") or []:
            found.append({"source": "permission_denials", "raw": d})
        message = event.get("message")
        for blk in (
            message.get("content")
            if isinstance(message, dict) and isinstance(message.get("content"), list)
            else []
        ):
            if (
                isinstance(blk, dict)
                and blk.get("type") == "tool_result"
                and blk.get("is_error")
                and PERMISSION_TEXT.search(_blocks_text(blk.get("content")))
            ):
                found.append({"source": "tool_result", "raw": blk})
        item = event.get("item") or {}
        if (
            item.get("type") == "command_execution"
            and event.get("type") == "item.completed"
            and item.get("status") in ("declined", "denied")
        ):
            found.append({"source": "codex_item", "raw": item})
    return found


WAVE_FOR_KIND = {"scope": "nw-design", "recovery": "nw-auto"}


def wave_prompt(host: str, kind: str, prompt: str) -> str:
    """Outer entry: the installed wave invocation followed by the unchanged original request."""
    return f"{'/' if host == 'claude' else '$'}{WAVE_FOR_KIND[kind]} {prompt}\n\n{COLLABORATION_NOTE}"


def role_dispatch(host: str, transcript: str, role: str) -> list[dict]:
    """Observed dispatch of the role (Agent/Task tool call or codex agent item), never mere preload/reads."""
    found: list[dict] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if host == "claude":
            message = event.get("message")
            for blk in (
                message.get("content")
                if isinstance(message, dict)
                and isinstance(message.get("content"), list)
                else []
            ):
                if (
                    isinstance(blk, dict)
                    and blk.get("type") == "tool_use"
                    and blk.get("name") in {"Agent", "Task"}
                ):
                    if (blk.get("input") or {}).get("subagent_type") == role:
                        found.append({"tool": blk["name"], "role": role})
        else:
            item = event.get("item") or {}
            # Arbitrary non-message items merely mentioning the role are NOT dispatch evidence: the native Codex
            # dispatch item schema is unobserved, so absence stays indeterminate rather than pass.
            if (
                item.get("type") == "command_execution"
                and event.get("type") == "item.started"
                and re.search(
                    rf"(?:^|[;&|]\s*)des\s+(?:--\S+\s+)*\S*{re.escape(role)}\b",
                    str(item.get("command")),
                )
            ):
                found.append({"tool": "command", "role": role})
    return found


def host_invocation(host: str, executable: str, kind: str, prompt: str, model: str):
    """(argv, stdin). Ordinary host entry through the installed wave: no --agent, no injected role
    instructions, no restrictive allowlist. claude: prompt on stdin."""
    text = wave_prompt(host, kind, prompt)
    if host == "claude":
        argv = [
            executable,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--setting-sources",
            "user",
            "--no-session-persistence",
            "--max-budget-usd",
            "2",
            "--permission-mode",
            "bypassPermissions",
            "--model",
            model,
        ]
        return argv, text
    return [
        executable,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
        text,
    ], None


def host_environment(
    host: str, lane: Path, home: Path, des_python: Path, provider_bounded: bool = False
) -> tuple[dict, list[str]]:
    shim = lane / "host-bin"
    shim.mkdir(exist_ok=True)
    recorder = Path(__file__).resolve().with_name("des_recorder.py")
    (shim / "des").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{recorder}" "$@"\n')
    (shim / "des").chmod(0o755)
    # No provider for des-owned role turns during a host probe: a turn would be unmeasured spend.
    # Only declared provider_bounded recovery cases get the stub; scope resolves the real installed claude.
    if provider_bounded:
        (shim / "claude").write_text(
            "#!/bin/sh\necho 'EVAL-NO-PROVIDER: des role turns are refused in the host probe' >&2\nexit 1\n"
        )
        (shim / "claude").chmod(0o755)
    hook = lane / "host-py"
    hook.mkdir(exist_ok=True)
    (hook / "sitecustomize.py").write_text(INTERCEPT_HOOK)
    log = lane / "des-records.jsonl"
    log.write_text("")
    log.chmod(0o600)
    env = {
        "DES_RECORD_LOG": str(log),
        "DES_RECORD_HANDOVER": str(
            lane / "repository" / ".nwave" / "des" / "handover.json"
        ),
        "DES_RECORD_REAL": json.dumps([str(des_python.absolute()), "-m", "des.cli"]),
        "PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(home),
        # Codex resolves its configuration and native skill catalogue from this
        # root.  HOME alone is insufficient when the parent process has an
        # explicit CODEX_HOME: without this binding a "clean" probe can silently
        # use the operator's real profile.
        "CODEX_HOME": str(home / ".codex"),
        "NWAVE_AGENTS_HOME": str(home),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TERM": os.environ.get("TERM", "dumb"),
        "DES_RECORD_TESTS": str(lane / "repository" / "tests"),
        "PYTHONPATH": str(hook),
        "DES_RECORD_INTERCEPT": "1",
        "DES_RECORD_RECORDER": str(recorder),
    }
    passed = []
    for name in CREDENTIAL_NAMES[host]:
        if (
            name in os.environ
        ):  # passed by name into the child only; never read, printed or stored
            env[name] = os.environ[name]
            passed.append(name)
    env["DES_RECORD_REDACT_NAMES"] = ",".join(passed)
    return env, passed


def secret_values(env: dict, passed: list[str]) -> list[str]:
    return [env[n] for n in passed if env.get(n)]


def run_case(case: dict, a, cases_out: Path, identity: str | None) -> dict:
    lane = cases_out / case["id"]
    lane.mkdir(parents=True, exist_ok=True)
    res: dict = {
        "case": case["id"],
        "host": a.host,
        "model": a.model,
        "role": case["role"],
        "installed_tree_sha256": identity,
        "verdict": "not-run",
        "fixture_status": None,
        "credential_env_names_passed": [],
        "claim_class": "first-command-class"
        if case["expected"].get("effect") == "terminal"
        else "first-mutating-effect",
    }
    try:
        record = build_fixture(case, lane, a.des_python)
        (lane / "fixture.json").write_text(json.dumps(record, indent=2) + "\n")
        res["fixture_status"] = record["status"]
        res["runtime_trees"] = record.get("runtime_trees")
        res["fixture_steps"] = [
            {
                k: s.get(k)
                for k in ("n", "op", "status", "exit", "outcome", "what", "reason")
            }
            for s in record["steps"]
        ]
        if record["status"] == "pending-v2-red":
            res["verdict"] = "pending-v2-red"
            res["reason"] = (
                "constructors ran; the declared v2 runtime behaviour is not implemented yet; case not handed to a host"
            )
        elif record["status"] == "runtime-drift":
            res["verdict"] = "unqualified"
            res["reason"] = (
                record["runtime_drift"] + "; not a final frozen-build result"
            )
        elif record["status"] != "setup-built":
            res["reason"] = "fixture setup failed; case never handed to a host"
        elif a.prepare_only:
            res["verdict"] = "fixture-built"
            res["reason"] = "prepare-only: host not run"
        else:
            run_host(case, a, lane, res)
    except (
        subprocess.TimeoutExpired,
        OSError,
        subprocess.CalledProcessError,
        KeyError,
        ImportError,
    ) as error:
        res["reason"] = f"{type(error).__name__}: {error}"
        res["verdict"] = (
            "not-run" if res["fixture_status"] != "setup-failed" else res["verdict"]
        )
    (lane / "result.json").write_text(json.dumps(res, indent=2) + "\n")
    return res


@dataclass(frozen=True)
class HostExecutionEnvironment:
    """Everything a spawned host subprocess runs inside, as opposed to what it is told to say (argv, stdin)."""

    repo: Path
    env: dict
    timeout: float
    secrets: list[str]


def spawn_host(argv, stdin, execution):
    """(completed-or-None on timeout, redacted stdout, redacted stderr). Partial output survives a timeout."""

    def clean(value) -> str:
        return redact(
            value.decode("utf-8", "replace")
            if isinstance(value, bytes)
            else value or "",
            execution.secrets,
        )

    try:
        done = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            cwd=execution.repo,
            env=execution.env,
            timeout=execution.timeout,
        )
    except subprocess.TimeoutExpired as error:
        return None, clean(error.stdout), clean(error.stderr)
    return done, clean(done.stdout), clean(done.stderr)


def run_host(case: dict, a, lane: Path, res: dict) -> None:
    if not a.model:
        res["reason"] = "--model not provided (caller must state the model explicitly)"
        return
    executable = shutil.which(a.host)
    home = a.installed_home.resolve()
    if not executable:
        res["reason"] = f"{a.host} CLI not found"
        return
    if not role_definition(home, a.host, case["role"]):
        res["reason"] = f"installed role {case['role']} not found in {home}"
        return
    absent = missing_skills(home, a.host, case)
    if absent:
        res["reason"] = f"installed skill(s) {absent} not found in {home}"
        return
    if (lane / "repository" / "nWave").exists():
        res["reason"] = "source nWave/ guidance still present in the subject repository"
        return
    frontmatter = role_frontmatter(home, a.host, case["role"])
    res["role_declared"] = frontmatter
    repo = lane / "repository"
    env, res["credential_env_names_passed"] = host_environment(
        a.host, lane, home, a.des_python, bool(case["expected"].get("provider_bounded"))
    )
    secrets = secret_values(env, res["credential_env_names_passed"])
    argv, stdin = host_invocation(
        a.host, executable, case["kind"], case["prompt"], a.model
    )
    res["argv_summary"] = [x if len(x) < 120 else x[:60] + "...[elided]" for x in argv]
    if a.dry_run:
        res["reason"] = "dry-run: host argv built, nothing executed"
        return
    before = _handover_digest(repo)
    started = time.monotonic()
    tests_initial = directory_digest(str(repo / "tests"))
    done, out_text, err_text = spawn_host(
        argv,
        stdin,
        HostExecutionEnvironment(
            repo=repo, env=env, timeout=a.timeout, secrets=secrets
        ),
    )
    if done is None:
        (lane / "transcript.jsonl").write_text(out_text)
        (lane / "stderr.txt").write_text(err_text)
        res.update(
            verdict="timeout",
            spend_attempted=True,
            seconds=a.timeout,
            reason=(
                f"host timed out after {a.timeout}s; partial redacted output kept; spend was attempted, so this is not not-run"
            ),
        )
        return
    done.stdout, done.stderr = out_text, err_text
    (lane / "transcript.jsonl").write_text(done.stdout)
    (lane / "stderr.txt").write_text(done.stderr)
    operations, other = issued_des(a.host, done.stdout)
    sessions, root_id = [], None
    if (
        a.host == "codex"
    ):  # captured immediately after the host exits, from this isolated profile only
        root_id = codex_root_thread(done.stdout)
        sessions = native_sessions(
            home / ".codex" / "sessions", root_id, str(repo.resolve()), secrets
        )
        res["native_sessions"] = [
            {k: v for k, v in x.items() if k != "lines"} for x in sessions
        ]
        (lane / "native-sessions.jsonl").write_text(
            "".join(line + "\n" for session in sessions for line in session["lines"])
        )
    native_ops, native_other = (
        native_operations(sessions, root_id) if sessions else ([], [])
    )
    observed = (
        native_ops or operations
    )  # native descendants when found; root stdout only as the fallback
    res["native_operations"], res["native_other_tool_runs"] = native_ops, native_other
    res["read_evidence"] = read_evidence(a.host, done.stdout)
    res["source_guidance_reads"] = [
        r for r in res["read_evidence"] if "nWave/" in str(r["path"])
    ]
    final = final_text(a.host, done.stdout)
    changed = _handover_digest(repo) != before
    res.update(
        exit=done.returncode,
        seconds=round(time.monotonic() - started, 1),
        des_operations=operations,
        other_tool_runs=other,
        first_mutating_des=next(
            (o["normalized"] for o in operations if o["mutating"]), None
        ),
        read_only_before_first_mutating=[
            o["normalized"] for o in operations if not o["mutating"]
        ][:20],
        handover_changed_during_run=changed,
        retries=max(0, sum(o["mutating"] for o in operations) - 1),
        human_interventions=0,
        final_terminal=final[-1500:],
        final_text_for_review=final,
    )
    models = re.findall(r'"model"\s*:\s*"([^"]+)"', done.stdout)
    res["model_reported"] = models[0] if models else None
    if AUTH_MARKERS.search(done.stdout + done.stderr) and not operations:
        res["reason"] = "host credentials/provider unavailable"
        return
    records = read_records(lane / "des-records.jsonl")
    res["des_records"] = records
    res["collaboration_mode"] = COLLABORATION_MODE
    blocks = permission_blocks(a.host, done.stdout)
    if blocks and not records:
        res.update(
            verdict="host-permission-block",
            spend_attempted=True,
            permission_blocks=blocks,
            reasons=[
                "host refused a tool before any DES ran; this cannot prove recorder bypass, is not a pass, and is neither a "
                "product nor instrument verdict; raw evidence retained"
            ],
        )
        return
    res["verdict"], res["reasons"] = evaluate_records(
        case,
        records,
        observed,
        EvaluationEndpoints(
            final=final,
            initial=before,
            last=_handover_digest(repo),
            tests_initial=tests_initial,
        ),
    )
    res["role_dispatch_observed"] = (
        native_role_proof(sessions, root_id, case["role"])
        if sessions
        else role_dispatch(a.host, done.stdout, case["role"])
    )
    downgrade_unproven(res, case["role"])


def downgrade_unproven(res: dict, role: str) -> None:
    """A pass or recovered-path-retry needs observed role dispatch and no source-guidance read."""
    if (
        res["verdict"] in ("pass", "recovered-path-retry")
        and not res["role_dispatch_observed"]
    ):
        res["verdict"] = "indeterminate"
        res["reasons"] = list(res["reasons"]) + [
            f"required role {role} dispatch not observed; preload is not dispatch"
        ]
    if res["source_guidance_reads"] and res["verdict"] in (
        "pass",
        "recovered-path-retry",
    ):
        res["verdict"] = "indeterminate"
        res["reasons"] = list(res["reasons"]) + ["source nWave/ guidance was read"]


# ---------------------------------------------------------------- self-test
def recorder_checks() -> dict[str, bool]:
    """Instrument control: a tiny fake des process drives the real recorder. No model, no product proof."""
    import tempfile

    here = Path(__file__).resolve().with_name("des_recorder.py")
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        hv = tmp / "handover.json"
        log = tmp / "log.jsonl"
        fake = tmp / "fake_des.py"
        fake.write_text(
            "import sys,os\na=sys.argv[1:]\nh=os.environ['DES_RECORD_HANDOVER']\n"
            "if a[:1]==['design']:\n"
            "    d=sys.stdin.read(); open(h,'w').write(d)\n"
            "    print('DELIVERY-OUTCOME: Success' if d.strip() else 'DELIVERY-OUTCOME: Refusal')\n"
            "    sys.exit(0 if d.strip() else 3)\nprint('state')\n"
        )
        env = {
            **os.environ,
            "DES_RECORD_LOG": str(log),
            "DES_RECORD_HANDOVER": str(hv),
            "DES_RECORD_REAL": json.dumps([sys.executable, str(fake)]),
        }

        def call(*args, stdin=None, file=None):
            f = open(file) if file else None
            done = subprocess.run(
                [sys.executable, str(here), *args],
                input=None if f else stdin,
                stdin=f,
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
            return done

        initial = _digest_of(hv)
        first = call("design", "--value=2", "--input", "-", stdin='{"a":1}')
        second = call("design", "--value", "2", "--input=-", stdin="")
        (tmp / "in.json").write_text('{"b":2}')
        call("design", "--input", "-", file=tmp / "in.json")
        call("state")
        records = read_records(log)
        checks["recorder passes real stdout/exit through"] = (
            first.returncode == 0
            and second.returncode == 3
            and "Success" in first.stdout
        )
        checks["stdin captured from pipe and file, not for state"] = (
            records[0]["stdin"] == '{"a":1}'
            and records[2]["stdin"] == '{"b":2}'
            and records[3]["stdin_captured"] is False
        )
        checks["Success then Refusal stay distinct"] = [
            operations_from_records(records)[i]["terminal"].get("DELIVERY-OUTCOME")
            for i in (0, 1)
        ] == ["Success", "Refusal"]
        checks["--flag=value normalized"] = (
            operations_from_records(records)[0]["normalized"]
            == "des design --value 2 --input -"
        )
        case = {
            "expected": {
                "first_mutating": r"^des design\b.*--value 2\b",
                "effect": "success-and-handover-changed",
            }
        }
        tops = [{"argv": r["argv"], "unclassifiable": False} for r in records]
        final = _digest_of(hv)
        checks["unbroken hash chain evaluates pass"] = (
            evaluate_records(
                case,
                records,
                tops,
                EvaluationEndpoints(final="", initial=initial, last=final),
            )[0]
            == "pass"
        )
        hv.write_text("manual edit")
        checks["manual handover edit detected as indeterminate"] = (
            evaluate_records(
                case,
                records,
                tops,
                EvaluationEndpoints(final="", initial=initial, last=_digest_of(hv)),
            )[0]
            == "indeterminate"
        )
        checks["no observations is indeterminate, never pass"] = (
            evaluate_records(
                case,
                [],
                [],
                EvaluationEndpoints(final="", initial=initial, last=initial),
            )[0]
            == "indeterminate"
        )
    return checks


def startup_controls() -> dict[str, bool]:
    """A login shell whose profile puts the installed bin first (the observed defect) is still recorded."""
    import tempfile

    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        home, lane = tmp / "home", tmp / "lane"
        (home / ".claude" / "bin").mkdir(parents=True)
        (lane / "repository" / ".nwave" / "des").mkdir(parents=True)
        installed = home / ".claude" / "bin" / "des"
        installed.write_text(
            f"#!{sys.executable}\nimport sys\nprint('DELIVERY-OUTCOME: Success', sys.argv[1:])\nsys.exit(3)\n"
        )
        installed.chmod(0o755)
        (home / ".profile").write_text('export PATH="$HOME/.claude/bin:$PATH"\n')
        env, _ = host_environment("claude", lane, home, Path(sys.executable))
        which = subprocess.run(
            ["bash", "-lc", "command -v des"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        checks["profile really puts installed des ahead of the shim"] = (
            which.stdout.strip() == str(installed)
        )
        done = subprocess.run(
            ["bash", "-lc", "des design --value 1 --input -"],
            input='{"schema_version": 2}',
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        records = read_records(lane / "des-records.jsonl")
        checks["installed des recorded despite PATH order"] = len(
            records
        ) == 1 and records[0]["argv"][:2] == ["des", "design"]
        checks["installed des stdin, stdout and exit preserved"] = (
            bool(records)
            and records[0]["stdin"] == '{"schema_version": 2}'
            and records[0]["exit"] == 3
            and done.returncode == 3
            and "Success" in done.stdout
        )
        subprocess.run(
            ["bash", "-lc", "python3 -c pass; des --help"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        checks["other python processes and reruns record exactly one entry each"] = (
            len(read_records(lane / "des-records.jsonl")) == 2
        )
        bare = {k: v for k, v in env.items() if k != "PYTHONPATH"}
        subprocess.run(
            ["bash", "-lc", "des --help"],
            env=bare,
            capture_output=True,
            text=True,
            timeout=20,
        )
        checks["cleared interception is detectable as a record/transcript mismatch"] = (
            len(read_records(lane / "des-records.jsonl")) == 2
            and evaluate_records(
                {"expected": {}},
                read_records(lane / "des-records.jsonl"),
                [{"argv": ["des"], "unclassifiable": False}] * 3,
                EvaluationEndpoints(final="", initial="absent", last="absent"),
            )[0]
            == "indeterminate"
        )
    return checks


def host_controls() -> dict[str, bool]:
    """Local controls for redaction, timeout, skill preflight and source-guidance removal. No model."""
    import tempfile

    checks: dict[str, bool] = {}
    secret = "sk-test-SECRET-123"
    checks["exact credential value redacted"] = (
        redact(f"key={secret}!", [secret]) == "key=[REDACTED]!"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        env = {**os.environ, "K": secret}
        prog = "import os,sys,time;print('out '+os.environ['K'],flush=True);sys.stderr.write('err '+os.environ['K']);sys.stderr.flush();time.sleep(30)"
        done, out, err = spawn_host(
            [sys.executable, "-c", prog],
            None,
            HostExecutionEnvironment(repo=tmp, env=env, timeout=2, secrets=[secret]),
        )
        checks["timeout keeps partial redacted stdout/stderr"] = (
            done is None
            and "out [REDACTED]" in out
            and "err [REDACTED]" in err
            and secret not in out + err
        )
        home = tmp / "home"
        (home / ".claude" / "skills" / "nw-design").mkdir(parents=True)
        (home / ".claude" / "skills" / "nw-design" / "SKILL.md").write_text("x")
        checks["missing installed skill is detected"] = (
            missing_skills(home, "claude", {"kind": "recovery"})
            == ["nw-auto", "nw-distill"]
            and missing_skills(home, "claude", {"kind": "scope"}) == []
        )
        (home / ".claude" / "agents" / "nw").mkdir(parents=True)
        (home / ".claude" / "agents" / "nw" / "nw-x.md").write_text(
            "---\nname: nw-x\ntools: Read, Glob\nskills:\n  - nw-a\n  - nw-b\n---\nbody\n"
        )
        fm = role_frontmatter(home, "claude", "nw-x")
        checks["installed role tools/skills read exactly, none added"] = fm == {
            "tools": ["Read", "Glob"],
            "skills": ["nw-a", "nw-b"],
        }
        argv, stdin = host_invocation("claude", "claude", "scope", "REQ", "m")
        checks[
            "outer claude entry: no --agent/allowlist, wave prefix then original request"
        ] = (
            "--agent" not in argv
            and "--allowedTools" not in argv
            and stdin == "/nw-design REQ\n\n" + COLLABORATION_NOTE
            and "bypassPermissions" in argv
        )
        cargv, _ = host_invocation("codex", "codex", "recovery", "REQ", "m")
        checks["outer codex entry: $wave prefix, no developer_instructions"] = (
            cargv[-1] == "$nw-auto REQ\n\n" + COLLABORATION_NOTE
            and "--sandbox" not in cargv
            and "--dangerously-bypass-approvals-and-sandbox" in cargv
            and not any("developer_instructions" in x for x in cargv)
        )
        dispatch = json.dumps(
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Agent",
                            "input": {"subagent_type": "nw-x"},
                        }
                    ]
                }
            }
        )
        checks["role dispatch observed only from Agent call, not reads"] = (
            len(role_dispatch("claude", dispatch, "nw-x")) == 1
            and role_dispatch(
                "claude",
                '{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"agents/nw/nw-x.md"}}]}}',
                "nw-x",
            )
            == []
        )
        for pb in (False, True):
            (tmp / f"l{pb}").mkdir()
            e, _ = host_environment(
                "claude", tmp / f"l{pb}", home, Path(sys.executable), pb
            )
            stub = (tmp / f"l{pb}" / "host-bin" / "claude").exists()
            checks[
                f"provider_bounded={pb}: claude stub {'present' if pb else 'absent'}"
            ] = stub == pb
        e, _ = host_environment(
            "claude", tmp / "lFalse", home, Path(sys.executable), False
        )
        checks["scope: claude on PATH is never the lane stub"] = shutil.which(
            "claude", path=e["PATH"]
        ) != str(tmp / "lFalse" / "host-bin" / "claude")
        codex_lane = tmp / "codex-isolation"
        codex_lane.mkdir()
        codex_environment, _ = host_environment(
            "codex", codex_lane, home, Path(sys.executable), False
        )
        checks["codex host binds CODEX_HOME to the installed clean profile"] = (
            codex_environment["CODEX_HOME"] == str(home / ".codex")
            and codex_environment["HOME"] == str(home)
        )
        cx = json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "mcp_tool_call", "note": "nw-x"},
            }
        )
        for cmd in ("sed -n 1,5p agents/nw/nw-x.md", "ls agents/nw-x"):
            checks[f"codex read-only command is not dispatch: {cmd}"] = (
                role_dispatch(
                    "codex",
                    json.dumps(
                        {
                            "type": "item.started",
                            "item": {"type": "command_execution", "command": cmd},
                        }
                    ),
                    "nw-x",
                )
                == []
            )
        denied = json.dumps(
            {"type": "result", "permission_denials": [{"tool_name": "Bash"}]}
        )
        checks["permission_denials parsed as host permission block"] = (
            len(permission_blocks("claude", denied)) == 1
        )
        checks["ordinary transcript has no permission block"] = (
            permission_blocks("claude", dispatch) == []
        )
        checks["codex non-message JSON mentioning role is not dispatch"] = (
            role_dispatch("codex", cx, "nw-x") == []
        )
        repo = tmp / "repo"
        base_repository(repo)
        checks["source nWave guidance present before removal"] = (
            repo / "nWave"
        ).is_dir()
        checks["source guidance removed and committed"] = (
            remove_source_guidance(repo)
            and not (repo / "nWave").exists()
            and _git(repo, "status", "--porcelain") == ""
        )
    checks.update(startup_controls())
    events = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "1",
                        "name": "Read",
                        "input": {"file_path": "/h/.claude/skills/nw-design/SKILL.md"},
                    }
                ]
            }
        }
    )
    checks["Read/Skill paths recorded from transcript"] = read_evidence(
        "claude", events
    ) == [{"tool": "Read", "path": "/h/.claude/skills/nw-design/SKILL.md"}]
    return checks


def _digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"


NATIVE_BUNDLE = FIXTURES / "codex-native"


def _fake_session(sid, lines):
    return {"id": sid, "lines": [json.dumps(x) for x in lines]}


def _exec_call(cid, cmds, ts):
    text = "".join("tools.exec_command(" + json.dumps({"cmd": c}) + ");" for c in cmds)
    return {
        "type": "response_item",
        "timestamp": ts,
        "payload": {
            "type": "custom_tool_call",
            "name": "exec",
            "call_id": cid,
            "input": text,
        },
    }


def _exec_out(cid, out, ts):
    return {
        "type": "response_item",
        "timestamp": ts,
        "payload": {"type": "custom_tool_call_output", "call_id": cid, "output": out},
    }


def _multi_call_controls() -> bool:
    one = native_tool_runs(
        _fake_session("t", [_exec_call("c", ["des a"], "1"), _exec_out("c", "x", "2")])
    )
    two = native_tool_runs(
        _fake_session(
            "t", [_exec_call("c", ["des a", "des b"], "1"), _exec_out("c", "x", "2")]
        )
    )
    return (
        one[0]["result"]["exit_code"] is None
        and one[0]["result"]["is_error"] is None
        and len(two) == 2
        and all(r["result"] is None for r in two)
    )


def _ordering_controls() -> bool:
    def op(thread, start, end):
        return {
            "argv": ["des", "x"],
            "mutating": True,
            "thread_id": thread,
            "timestamp": start,
            "ended": end,
        }

    observed = [op("a", "5", "9"), op("b", "5", "8")]
    attribution = {
        "matched": [{"record": 0, "observed": 0}, {"record": 1, "observed": 1}]
    }
    same = [{"handover_before": "h", "handover_after": "h"}] * 2
    changed = [
        {"handover_before": "h", "handover_after": "i"},
        {"handover_before": "i", "handover_after": "i"},
    ]
    separated = [op("a", "1", "2"), op("b", "3", "4")]
    return (
        unordered_first_mutation(same, attribution, observed) is not None
        and unordered_first_mutation(changed, attribution, observed) is None
        and unordered_first_mutation(same, attribution, separated) is None
    )


def _redaction_controls() -> bool:
    import tempfile

    d = Path(tempfile.mkdtemp())
    meta = json.dumps({"payload": {"id": "r", "cwd": "/w"}, "note": "sk-secret-value"})
    raw = (meta + "\n").encode()
    (d / "rollout-r.jsonl").write_bytes(raw)
    got = native_sessions(d, "r", "/w", ["sk-secret-value"])
    return (
        bool(got)
        and "sk-secret-value" not in "".join(got[0]["lines"])
        and got[0]["sha256"] == hashlib.sha256(raw).hexdigest()
    )


def native_controls() -> dict[str, bool]:
    """Real extracted native root+child Codex events, plus negatives that alter only identity."""
    import tempfile

    root_file = next(NATIVE_BUNDLE.glob("*01a0c3de-*.jsonl"), None)
    child_file = next(NATIVE_BUNDLE.glob("*01a0c3df-*.jsonl"), None)
    if not root_file or not child_file:
        return {"native evidence bundle present": False}
    provenance = json.loads((NATIVE_BUNDLE / "provenance.json").read_text())["files"]
    fixture_files = (root_file, child_file)
    sha_matches = all(
        hashlib.sha256(f.read_bytes()).hexdigest()
        == provenance.get(f.name, {}).get("fixture_sha256")
        for f in fixture_files
    )
    no_home_paths = all("/home/" not in f.read_text() for f in fixture_files)
    root_id = "01a0c3de-f9d5-7932-9831-446c9d2cdad9"
    cwd = json.loads(root_file.read_text().splitlines()[0])["payload"]["cwd"]

    def build(edit=None) -> Path:
        d = Path(tempfile.mkdtemp())
        for f in (root_file, child_file):
            lines = f.read_text().splitlines()
            if edit and f is child_file:
                meta = json.loads(lines[0])
                edit(meta["payload"])
                lines[0] = json.dumps(meta)
            (d / f.name).write_text("\n".join(lines) + "\n")
        return d

    def child_ops(edit=None):
        sessions = native_sessions(build(edit), root_id, cwd)
        return sessions, native_operations(sessions, root_id)[0]

    sessions, ops = child_ops()
    counts = (
        sum(o["origin"] == "root" for o in ops),
        sum(o["origin"] == "child" for o in ops),
    )
    wrong_parent, _ = child_ops(
        lambda m: m.update(parent_thread_id="ffffffff-0000-0000-0000-000000000000")
    )
    wrong_cwd, _ = child_ops(lambda m: m.update(cwd="/elsewhere"))
    mention_only, _ = child_ops(
        lambda m: (m.update(agent_role="other"), m.pop("parent_thread_id", None))
    )
    records = [{"argv": o["argv"]} for o in ops]
    attr = attribute_records(records, ops)
    return {
        "fixture sha256 equals provenance record": sha_matches,
        "no fixture line contains /home/": no_home_paths,
        "native root+child linked by id/parent/cwd (9 root, 7 child des calls)": counts
        == (9, 7),
        "native child role proof is session_meta agent_role": bool(
            native_role_proof(sessions, root_id, "nw-solution-architect")
        ),
        "child call keeps argv, thread identity, output": all(
            o["thread_id"] and o["result"] is not None
            for o in ops
            if o["origin"] == "child"
        ),
        "wrong parent thread is not linked": [x["id"] for x in wrong_parent]
        == [root_id],
        "wrong cwd child is not linked": [x["id"] for x in wrong_cwd] == [root_id],
        "role mention without parent link is not dispatch": not native_role_proof(
            mention_only, root_id, "nw-solution-architect"
        ),
        "all 16 records attributed, none unrecorded": len(attr["matched"]) == 16
        and not attr["unrecorded_observed"],
        "multi-command native call leaves results unattributed, exit unknown": _multi_call_controls(),
        "cross-thread tied first mutation is indeterminate": _ordering_controls(),
        "live native lines are redacted, sha of original kept": _redaction_controls(),
        "extra record without observation is unattributed": attribute_records(
            records + [{"argv": ["des", "state"]}],
            [o for o in ops if o["normalized"] != "des state"],
        )["unattributed_records"]
        != [],
    }


@dataclass(frozen=True)
class HandoverSpan:
    """The handover hash a synthetic des record claims before and after it runs."""

    before: str
    after: str


def retry_controls() -> dict[str, bool]:
    """Local counterexample controls for the recovered-path-retry classification."""
    case = {
        "expected": {
            "first_mutating": r"^des distill\b.*--replace-current\b",
            "effect": "success-and-handover-changed",
            "forbidden": [r"^des craft\b"],
            "input_json": {"schema_version": 2},
        }
    }
    ok_in = '{"schema_version": 2}'
    refuse = "DELIVERY-OUTCOME: Refusal\nWHAT: InvalidRepositoryRoot\nTURNS-BOUGHT=0"

    def rec(argv, code, out, span, stdin=ok_in):
        return {
            "argv": argv,
            "exit": code,
            "stdout": out,
            "stderr": "",
            "stdin": stdin,
            "handover_before": span.before,
            "handover_after": span.after,
        }

    d = ["des", "distill", "--replace-current"]
    good = rec(d, 0, "DELIVERY-OUTCOME: Success", HandoverSpan(before="h0", after="h1"))
    bad_root = rec(d, 2, refuse, HandoverSpan(before="h0", after="h0"))

    def verdict(records):
        ops = operations_from_records(records)
        base = evaluate(
            case, ops, "", records[0]["handover_before"] != records[0]["handover_after"]
        )
        return base[0], (recovered_path_retry(case, ops, records) is not None)

    wrong = rec(
        ["des", "craft", "--value", "1"],
        2,
        refuse,
        HandoverSpan(before="h0", after="h0"),
    )
    turns = rec(d, 2, refuse.replace("=0", "=1"), HandoverSpan(before="h0", after="h0"))
    unknown = rec(
        d,
        2,
        "WHAT: InvalidRepositoryRoot\nTURNS-BOUGHT=0",
        HandoverSpan(before="h0", after="h0"),
    )
    effect = rec(d, 2, refuse, HandoverSpan(before="h0", after="hX"))
    exit_none = rec(d, None, refuse, HandoverSpan(before="h0", after="h0"))
    malformed = rec(
        d,
        0,
        "DELIVERY-OUTCOME: Success",
        HandoverSpan(before="h1", after="h2"),
        stdin="not json",
    )
    later_read = [
        bad_root,
        good,
        rec(["des", "state"], 0, "ok", HandoverSpan(before="h1", after="h1")),
    ]

    def full(records, final="", initial="h0", last=None, mutate=None):
        seen = operations_from_records(records)
        if mutate:
            seen = mutate(seen)
        return evaluate_records(
            case,
            records,
            seen,
            EvaluationEndpoints(
                final=final, initial=initial, last=last or records[-1]["handover_after"]
            ),
        )

    recovered_seq = [bad_root, dict(good, handover_before="h0")]
    v_ok, r_ok = full(recovered_seq)
    broken_chain = [bad_root, dict(good, handover_before="hZ")]
    v_dead, _r_dead = full([bad_root, bad_root], last="h0")
    v_final, _r_final = full(recovered_seq, final="Everything is done, craft finished")
    fcase = {"expected": dict(case["expected"], final_forbidden=r"craft finished")}
    ff_ops = operations_from_records(recovered_seq)
    v_ff, r_ff = evaluate_records(
        fcase,
        recovered_seq,
        ff_ops,
        EvaluationEndpoints(final="craft finished", initial="h0", last="h1"),
    )
    late_craft = recovered_seq + [
        rec(
            ["des", "craft", "--value", "1"],
            0,
            "DELIVERY-OUTCOME: Success",
            HandoverSpan(before="h1", after="h2"),
        )
    ]
    v_late, r_late = full(late_craft)
    v_unattr = evaluate_records(
        case,
        recovered_seq
        + [rec(["des", "state"], 0, "ok", HandoverSpan(before="h1", after="h1"))],
        operations_from_records(recovered_seq),
        EvaluationEndpoints(final="", initial="h0", last="h1"),
    )[0]
    dres = {
        "verdict": v_ok,
        "reasons": list(r_ok),
        "role_dispatch_observed": False,
        "source_guidance_reads": [],
    }
    downgrade_unproven(dres, "nw-x")
    sres = {
        "verdict": v_ok,
        "reasons": list(r_ok),
        "role_dispatch_observed": True,
        "source_guidance_reads": ["nWave/x"],
    }
    downgrade_unproven(sres, "nw-x")
    kres = {
        "verdict": v_ok,
        "reasons": list(r_ok),
        "role_dispatch_observed": True,
        "source_guidance_reads": [],
    }
    downgrade_unproven(kres, "nw-x")
    return {
        "retry e2e: evaluate_records returns recovered-path-retry with raw fail reason retained": v_ok
        == "recovered-path-retry"
        and any("observed outcome 'Refusal', not Success" in r for r in r_ok)
        and any("raw first-attempt verdict stays fail" in r for r in r_ok),
        "retry e2e: broken hash chain stays indeterminate": full(broken_chain)[0]
        == "indeterminate",
        "retry e2e: unattributed record stays indeterminate": v_unattr
        == "indeterminate",
        "retry e2e: refusals only stays fail (no recovery)": v_dead == "fail",
        "retry e2e: final_forbidden on recovered sequence stays fail, reason retained": v_ff
        == "fail"
        and "final text makes a forbidden claim" in r_ff
        and v_final == "recovered-path-retry",
        "retry e2e: later forbidden des craft stays fail, reason retained": v_late
        == "fail"
        and any("forbidden" in r for r in r_late),
        "retry e2e: missing role dispatch downgrades to indeterminate": dres["verdict"]
        == "indeterminate",
        "retry e2e: source guidance read downgrades to indeterminate": sres["verdict"]
        == "indeterminate",
        "retry e2e: proven role, no source read keeps recovered-path-retry": kres[
            "verdict"
        ]
        == "recovered-path-retry",
        "retry: first-attempt success stays plain pass": verdict([good])
        == ("pass", False),
        "retry: correct-step root refusal then real Success recovers": verdict(
            [bad_root, dict(good, handover_before="h0")]
        )[1]
        and verdict([bad_root, good])[0] == "fail",
        "retry: wrong-semantic first refusal never recovers": not verdict(
            [wrong, dict(good, handover_before="h0")]
        )[1],
        "retry: provider turn bought never recovers": not verdict([turns, good])[1],
        "retry: unknown outcome (no terminal) never recovers": not verdict(
            [unknown, good]
        )[1],
        "retry: refusal with handover side effect never recovers": not verdict(
            [effect, good]
        )[1],
        "retry: unknown exit never recovers": not verdict([exit_none, good])[1],
        "retry: malformed payload success never recovers": not verdict(
            [bad_root, malformed]
        )[1],
        "retry: refusals only, no Success, never recovers": not verdict(
            [bad_root, bad_root]
        )[1],
        "retry: post-success continuation is retained, not judged initial": len(
            operations_from_records(later_read)
        )
        == 3
        and verdict([bad_root, dict(good, handover_before="h0")])[1],
    }


def self_test() -> int:
    """Parser checks on synthetic events shaped after recorded Claude/Codex streams."""

    def claude(tool_id, cmd, output=None, error=False):
        rows = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": "Bash",
                            "input": {"command": cmd},
                        }
                    ]
                },
            }
        ]
        if output is not None:
            rows.append(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": output,
                                "is_error": error,
                            }
                        ]
                    },
                }
            )
        return "\n".join(json.dumps(r) for r in rows)

    def codex(item_id, cmd, output, code):
        s = {
            "type": "item.started",
            "item": {
                "id": item_id,
                "type": "command_execution",
                "command": cmd,
                "aggregated_output": "",
                "exit_code": None,
                "status": "in_progress",
            },
        }
        c = {
            "type": "item.completed",
            "item": {
                "id": item_id,
                "type": "command_execution",
                "command": cmd,
                "aggregated_output": output,
                "exit_code": code,
                "status": "completed",
            },
        }
        return json.dumps(s) + "\n" + json.dumps(c)

    ok = "DELIVERY-OUTCOME: Success\n"
    checks = {}
    ops, _ = issued_des(
        "claude", claude("1", 'echo "des design --value 2" && echo des oracle')
    )
    checks["echo narration is not a des operation"] = ops == []
    ops, _ = issued_des(
        "codex",
        codex(
            "i",
            "/bin/bash -lc \"des state --repo-root . && des design --value 2 --input - <<'EOF'\n{}\nEOF\"",
            ok,
            0,
        ),
    )
    checks[
        "codex started+completed counted once, bash -lc unwrapped, heredoc skipped"
    ] = [o["normalized"] for o in ops] == [
        "des state",
        "des design --value 2 --input -",
    ] and ops[1]["terminal"]["DELIVERY-OUTCOME"] == "Success"
    checks["state is read-only, design mutating"] = [o["mutating"] for o in ops] == [
        False,
        True,
    ]
    ops, _ = issued_des(
        "claude",
        claude(
            "2",
            "des design --help\ncat x.json | des design --repo-root /r --shared --input - 2>&1",
            ok,
        ),
    )
    checks["help read-only; pipeline stage and 2>&1 parsed; --repo-root dropped"] = [
        (o["normalized"], o["mutating"]) for o in ops
    ] == [("des design --help", False), ("des design --shared --input -", True)]
    ops, _ = issued_des(
        "codex", codex("j", "/bin/bash -lc 'des oracle --value 1'", "", None)
    )
    checks["result recorded separately (null when absent)"] = (
        ops[0]["result"]["exit_code"] is None
    )
    ops, _ = issued_des("claude", claude("3", "x=$(des design --value 2 --input -)"))
    checks["opaque substitution is flagged unclassifiable"] = (
        len(ops) == 1 and ops[0]["unclassifiable"]
    )
    case = {
        "expected": {
            "first_mutating": r"^des design\b.*--value 2\b",
            "effect": "success-and-handover-changed",
            "forbidden": ["--shared"],
        }
    }
    ops, _ = issued_des(
        "claude",
        claude("4", "des state --repo-root .", "state")
        + "\n"
        + claude("5", "des design --repo-root . --value 2 --input - <<'E'\n{}\nE", ok),
    )
    checks["read-only state before the operation does not displace it"] = (
        evaluate(case, ops, "", True)[0] == "pass"
    )
    checks["success terminal without handover change fails"] = (
        evaluate(case, ops, "", False)[0] == "fail"
    )
    ops, _ = issued_des("claude", claude("6", "des design --value 2 --input -"))
    checks["command text alone (no result) fails"] = (
        evaluate(case, ops, "", True)[0] == "fail"
    )
    x_case = {
        "expected": {
            "first_mutating": r"^des design\b.*--shared",
            "alternative": {"no_mutating": True, "final_regex": r"\bX\b"},
        }
    }
    checks["explicit rejected decision naming absent X and owner passes"] = (
        evaluate(
            x_case,
            [],
            "Rejected: common decision X is missing; the decision owner (architect) must state it.",
            False,
        )[0]
        == "pass"
    )
    checks["'X noted, done' narration never passes"] = (
        evaluate(x_case, [], "X noted, done", False)[0] == "fail"
    )
    checks["natural refusal is stored for semantic review, not passed"] = (
        evaluate(x_case, [], "I need X before designing; please supply it.", False)[0]
        == "needs-semantic-review"
    )
    checks["no commands and no X is not a pass"] = (
        evaluate(x_case, [], "ok", False)[0] != "pass"
    )
    json_case = {
        "expected": {
            "first_mutating": r"^des distill\b",
            "input_json": {"schema_version": 2},
        }
    }

    def distill(stdin):
        return [
            {
                "argv": ["des", "distill", "--input", "-"],
                "normalized": "des distill --input -",
                "mutating": True,
                "unclassifiable": False,
                "command": "# schema_version 2 in a comment\ndes distill",
                "stdin": stdin,
                "result": {
                    "exit_code": 0,
                    "is_error": False,
                    "output": "DELIVERY-OUTCOME: Success",
                },
                "terminal": {"DELIVERY-OUTCOME": "Success"},
            }
        ]

    checks["stdin JSON schema_version 2 parsed"] = (
        evaluate(json_case, distill('{"schema_version": 2}'), "", False)[0] == "pass"
    )
    checks["schema_version 1 stdin fails"] = (
        evaluate(json_case, distill('{"schema_version":1}'), "", False)[0] == "fail"
    )
    checks["text mention of schema_version 2 without JSON fails"] = (
        evaluate(json_case, distill("schema_version 2"), "", False)[0] == "fail"
    )
    tcase = {
        "expected": {
            "first_mutating": r"^des oracle\b",
            "effect": "terminal",
            "provider_bounded": True,
            "requires_support_repair": True,
        }
    }

    def oracle(output, tests_before):
        return [
            {
                "argv": ["des", "oracle"],
                "normalized": "des oracle --value 1",
                "mutating": True,
                "unclassifiable": False,
                "command": "",
                "stdin": None,
                "tests_before": tests_before,
                "result": {"exit_code": 1, "is_error": True, "output": output},
                "terminal": {"DELIVERY-OUTCOME": "Refusal"},
            }
        ]

    stub = "DELIVERY-OUTCOME: Refusal\nEVAL-NO-PROVIDER"
    checks["usage refusal is not a terminal pass"] = (
        evaluate(
            tcase,
            oracle(
                "usage: des oracle\nerror: argument --value: expected one argument\nDELIVERY-OUTCOME: Refusal",
                "r",
            ),
            "",
            False,
            "t0",
        )[0]
        == "fail"
    )
    checks["missing EVAL-NO-PROVIDER fails a bounded case"] = (
        evaluate(tcase, oracle("DELIVERY-OUTCOME: Refusal", "r"), "", False, "t0")[0]
        == "fail"
    )
    checks["oracle against still-broken files fails (no support repair)"] = (
        evaluate(tcase, oracle(stub, "t0"), "", False, "t0")[0] == "fail"
    )
    checks["support repair before oracle plus stub terminal passes"] = (
        evaluate(tcase, oracle(stub, "t1"), "", False, "t0")[0] == "pass"
    )
    checks["runtime tree drift is reported"] = (
        runtime_drift(["aaa", "bbb"]) is not None
        and runtime_drift(["aaa", "aaa"]) is None
    )
    checks["steps that declare no runtime are not drift"] = (
        runtime_drift([None, "aaa", None, "aaa"]) is None
    )
    checks.update(retry_controls())
    checks.update(host_controls())
    checks.update(native_controls())
    checks.update(recorder_checks())
    for name, good in checks.items():
        print(("ok   " if good else "FAIL ") + name)
    return 0 if all(checks.values()) else 1


def _sha(text) -> str:
    return hashlib.sha256(str(text).encode()).hexdigest()


def _hash_only(op: dict) -> dict:
    """Offline replay cannot know credentials of the past run, so it retains no command/output text: hash-only
    provenance plus identity. The full redacted-at-capture copy stays in the live run's native-sessions.jsonl."""
    keep = (
        "id",
        "tool_call",
        "origin",
        "agent_role",
        "thread_id",
        "native_call_id",
        "native_line",
        "timestamp",
        "ended",
        "mutating",
    )
    out = {k: op[k] for k in keep if k in op}
    out["command_sha256"] = _sha(op.get("command", ""))
    if op.get("result") is not None:
        out["output_sha256"] = _sha(op["result"].get("output", ""))
    out["exit_code"], out["is_error"] = None, None
    return out


def replay_native(case_dir: Path, home: Path, cases: list[dict]) -> Path:
    """Offline amended assessment of a finished case from its retained stdout, recorder log and this profile's native
    sessions. Writes result.amended.json beside, never over, the raw evidence and raw verdict."""
    raw = json.loads((case_dir / "result.json").read_text())
    case = next(c for c in cases if c["id"] == raw["case"])
    stdout = (case_dir / "transcript.jsonl").read_text()
    records = read_records(case_dir / "des-records.jsonl")
    repo = case_dir / "repository"
    root_id = codex_root_thread(stdout)
    sessions = native_sessions(
        home / ".codex" / "sessions",
        root_id,
        str(repo.resolve()),
        [os.environ[n] for n in CREDENTIAL_NAMES["codex"] if os.environ.get(n)],
    )
    ops, other = native_operations(sessions, root_id) if sessions else ([], [])
    stdout_ops, _ = issued_des("codex", stdout)
    chain = [(r.get("handover_before"), r.get("handover_after")) for r in records]
    initial, last = (chain[0][0], chain[-1][1]) if chain else ("absent", "absent")
    final = final_text("codex", stdout)
    verdict, reasons = evaluate_records(
        case,
        records,
        ops or stdout_ops,
        EvaluationEndpoints(
            final=final, initial=initial, last=last, tests_initial=None
        ),
    )
    amended = {
        "raw_verdict": raw.get("verdict"),
        "raw_reasons": raw.get("reasons"),
        "amended_verdict": verdict,
        "amended_reasons": reasons,
        "root_thread_id": root_id,
        "root_stdout_des_calls": len(stdout_ops),
        "native_des_calls": {
            "root": sum(o["origin"] == "root" for o in ops),
            "child": sum(o["origin"] == "child" for o in ops),
        },
        "attribution": attribute_records(records, [o for o in ops if o["argv"]]),
        "native_sessions": [
            {k: v for k, v in x.items() if k != "lines"} for x in sessions
        ],
        "native_operations": [_hash_only(o) for o in ops],
        "native_other_tool_runs": [_hash_only(o) for o in other],
        "role_dispatch_observed": native_role_proof(sessions, root_id, case["role"]),
        "redaction": "replay knows only credentials currently in the environment; past secrets are unknown, so no "
        "command/output text is exported (hash-only), and native session lines are not copied",
        "limit": "handover chain endpoints taken from the recorder log (initial hash not stored in raw result); "
        "a refusal is never converted to pass",
    }
    target = case_dir / "result.amended.json"
    target.write_text(json.dumps(amended, indent=2))
    return target


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--host", choices=["claude", "codex"])
    ap.add_argument("--output-root", type=Path)
    ap.add_argument(
        "--installed-home",
        type=Path,
        help="clean HOME holding the installed nWave tree",
    )
    ap.add_argument(
        "--des-python",
        type=Path,
        default=Path(sys.executable),
        help="interpreter exposing des (default: this interpreter)",
    )
    ap.add_argument("--case", action="append", help="case id filter (repeatable)")
    ap.add_argument("--model", help="explicit host model; required to run a host")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument(
        "--replay-native",
        type=Path,
        help="finished Codex case directory to reassess from retained native sessions; no host call",
    )
    ap.add_argument("--list", action="store_true")
    ap.add_argument(
        "--prepare-only",
        action="store_true",
        help="build and check fixtures only; no host, no spend",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="build fixtures and host argv; do not execute the host",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="parser checks on synthetic events; no host",
    )
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    cases = json.loads(CASES.read_text())["cases"]
    if a.replay_native:
        if not a.installed_home:
            print("--replay-native needs --installed-home", file=sys.stderr)
            return 2
        print(
            replay_native(a.replay_native.resolve(), a.installed_home.resolve(), cases)
        )
        return 0
    if a.list:
        print("\n".join(c["id"] for c in cases))
        return 0
    if a.case:
        unknown = set(a.case) - {c["id"] for c in cases}
        if unknown:
            print(f"unknown case(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        cases = [c for c in cases if c["id"] in a.case]
    if not a.output_root:
        print("--output-root is required", file=sys.stderr)
        return 2
    hosted = not a.prepare_only
    if hosted and (not a.host or not a.installed_home):
        print(
            "running a host needs --host and --installed-home (or use --prepare-only)",
            file=sys.stderr,
        )
        return 2
    identity = (
        tree_digest(a.installed_home.resolve(), a.host)
        if hosted and a.installed_home and a.host
        else None
    )
    out = a.output_root.resolve() / (a.host or "fixtures")
    worst = 0
    for case in cases:
        res = run_case(case, a, out, identity)
        print(
            json.dumps(
                {
                    k: res.get(k)
                    for k in (
                        "case",
                        "host",
                        "fixture_status",
                        "verdict",
                        "first_mutating_des",
                        "reason",
                    )
                }
            ),
            flush=True,
        )
        worst = max(
            worst,
            {
                "pass": 0,
                "fixture-built": 0,
                "pending-v2-red": 5,
                "not-run": 3,
                "fail": 1,
                "indeterminate": 6,
                "needs-semantic-review": 7,
                "unqualified": 8,
                "timeout": 9,
                "host-permission-block": 6,
                "recovered-path-retry": 10,
            }[res["verdict"]],
        )
        if res["fixture_status"] == "setup-failed":
            worst = max(worst, 4)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
