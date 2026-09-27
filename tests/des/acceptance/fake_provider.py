"""The ONE fake provider the acceptance suites drive the DES with.

Two copies of this script used to exist -- one inside the composed-run corpus
and one in the step corpus -- and they were two spellings of the same contract:
what a provider envelope looks like, which roles owe `defect_owner` or
`blocked_by`, how a transport failure is reported. A review found them, and the
drift they invite is not hypothetical: the step corpus was written with a
Product Owner envelope that omitted `values`, which the real boundary refuses,
and the scenario measured the schema instead of the law it was written for.

WHAT IT ANSWERS, and why every branch is here rather than in a caller. The
script is executed as `claude` on `PATH`, so it must speak the whole provider
protocol the adapter enforces: the structured envelope, the two roles whose
payload carries a closed word, and the error document a retry-safe transport
failure produces. A caller that had to add one of those back would be a second
copy again.

HOW ANSWERS ARE INDEXED, and why there are two modes rather than one. A composed
run walks every role inside ONE process, so its scenarios declare one list of
answers for the whole Request and the turn ordinal is the log length. A step is
invoked many times, and each invocation declares only the answers ITS turns
consume, so the ordinal has to restart. `NWAVE_MODEL_COUNTER` selects the second
mode by naming a file the caller truncates before each invocation; without it
the ordinal is the log length, which is exactly what the composed corpus had.
The LOG stays cumulative in both modes, because a scenario asserting how many
turns were bought must see every one of them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


#: The provider stand-in, as source. It runs under the interpreter that wrote
#: it, so a suite driving it needs no interpreter on `PATH` of its own.
SCRIPT = f"""#!{sys.executable}
import json, os, pathlib, re, sys

argv = sys.argv[1:]
if "--agent" in argv:
    agent = argv[argv.index("--agent") + 1]
else:
    # The charter task drops discovery-based `--agent` for `--bare --restricted
    # --system-prompt <preloaded role bytes>`. The role identity then travels
    # inside that preloaded text's own frontmatter `name:` line -- the same
    # bytes the real adapter loaded from the installed role definition -- so
    # the fake reads it from there instead of inventing a role.
    if "--system-prompt" not in argv:
        raise SystemExit(
            "fake provider: neither --agent nor --system-prompt is present in argv; "
            "cannot determine the role identity"
        )
    system_prompt = argv[argv.index("--system-prompt") + 1]
    match = re.search(r"^name:\\s*(\\S+)", system_prompt, re.MULTILINE)
    if match is None:
        raise SystemExit(
            "fake provider: --system-prompt carries no `name:` frontmatter line; "
            "cannot determine the role identity"
        )
    agent = match.group(1)
log = pathlib.Path(os.environ["NWAVE_MODEL_LOG"])
rows = json.loads(log.read_text()) if log.exists() else []
# Recorded at invocation time, inside the execution cwd, before any caller
# cleanup (checkout removal, tempdir rmdir) can run -- the only moment a
# scenario can observe what the role actually had to read, since a correct
# isolated checkout may legitimately be gone by the time the caller returns.
check_paths = [p for p in os.environ.get("NWAVE_MODEL_CHECK_PATHS", "").split(os.pathsep) if p]
readable_paths = [p for p in check_paths if os.path.isfile(p)]
# The full argv the adapter spawned this launcher with -- the only place a
# scenario can observe the projected `--tools`/`--allowedTools` (Claude) or
# `--sandbox` (Codex) ceiling the adapter itself computed, rather than
# re-deriving it from a copy of the projection rule.
rows.append({{"agent": agent, "prompt": sys.stdin.read(), "cwd": os.getcwd(),
             "readable_paths": readable_paths, "argv": argv}})
log.write_text(json.dumps(rows))

# The ordinal: per invocation when a counter file is named, cumulative otherwise.
counter = os.environ.get("NWAVE_MODEL_COUNTER")
if counter:
    path = pathlib.Path(counter)
    seen = int(path.read_text()) if path.exists() else 0
    path.write_text(str(seen + 1))
else:
    seen = len(rows) - 1

answers = json.loads(pathlib.Path(os.environ["NWAVE_MODEL_RESULTS"]).read_text())
if seen >= len(answers):
    print(json.dumps({{"structured_output": {{
        "outcome": "indeterminate",
        "diagnostic": "the fake provider was invoked more times than the scenario declared",
    }}}}))
    sys.exit(0)
answer = answers[seen]

root = pathlib.Path(os.environ["NWAVE_MODEL_ROOT"])
for name, body in answer.get("writes", {{}}).items():
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
for name in answer.get("deletes", []):
    (root / name).unlink(missing_ok=True)

default = {{"outcome": "accepted", "diagnostic": ""}}
if agent == "nw-product-owner":
    default = {{**default, "values": [
        {{"observation": json.loads(rows[-1]["prompt"].splitlines()[0].split(": ", 1)[1])}}
    ]}}

if answer.get("retry_safe"):
    print(json.dumps({{
        "is_error": True, "terminal_reason": "api_error", "duration_api_ms": 0,
        "total_cost_usd": 0, "modelUsage": {{}},
        "usage": {{"iterations": [], "input_tokens": 0, "output_tokens": 0,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}},
    }}))
    sys.exit(answer.get("exit", 1))

payload = answer.get("structured_output", default)
# The full DesignFacts schema travels through every provider response.  A
# model-authored design has no configured DESIGN document section; the closed
# constructor assigns that identity later, so its explicit provider value is
# the empty string rather than a guessed heading-derived locator.
if agent == "nw-solution-architect" and isinstance(payload.get("design_facts"), dict):
    payload = {{**payload, "design_facts": {{
        **payload["design_facts"],
        "authority_locator": payload["design_facts"].get("authority_locator", ""),
    }}}}
# Three roles owe a closed word on a non-accepting envelope, and the real
# boundary refuses one that omits it: the two reviewers name whose defect they
# found, the crafters name who can unblock them. Filling the default here is
# what keeps a fake from measuring the schema instead of the law a scenario was
# written for.
if agent.endswith("-reviewer") and "defect_owner" not in payload:
    payload = {{**payload,
               "defect_owner": None if payload["outcome"] == "accepted" else "oracle",
               "defect_value": None}}
if agent.endswith("software-crafter") and "blocked_by" not in payload:
    payload = {{**payload,
               "blocked_by": None if payload["outcome"] == "accepted" else "product"}}
print(json.dumps({{"structured_output": payload}}))
sys.exit(answer.get("exit", 0))
"""


#: The Codex provider stand-in. Codex speaks a different transport than
#: Claude's `--agent`/stdout-JSON protocol: the role identity travels inside
#: `-c developer_instructions=...`, and the answer is a provider-enforced
#: terminal file named by `--output-last-message`, never stdout. Everything
#: else (log shape, answer indexing, writes/deletes, defect_owner/blocked_by
#: defaulting) stays byte-identical to `SCRIPT` so one scenario can assert the
#: same law against either provider's recorded row.
CODEX_SCRIPT = f"""#!{sys.executable}
import json, os, pathlib, re, sys

argv = sys.argv[1:]

def _opt(name):
    return argv[argv.index(name) + 1]

developer_instructions = None
for i, token in enumerate(argv):
    if token == "-c" and argv[i + 1].startswith("developer_instructions="):
        developer_instructions = json.loads(argv[i + 1][len("developer_instructions="):])
        break
match = re.search(r"role=(\\S+)", developer_instructions or "")
agent = match.group(1) if match else "unknown"

log = pathlib.Path(os.environ["NWAVE_MODEL_LOG"])
rows = json.loads(log.read_text()) if log.exists() else []
# Recorded at invocation time, inside the execution cwd, before any caller
# cleanup can run -- same discipline as the Claude launcher above.
check_paths = [p for p in os.environ.get("NWAVE_MODEL_CHECK_PATHS", "").split(os.pathsep) if p]
readable_paths = [p for p in check_paths if os.path.isfile(p)]
rows.append({{"agent": agent, "prompt": sys.stdin.read(), "cwd": os.getcwd(),
             "readable_paths": readable_paths, "argv": argv}})
log.write_text(json.dumps(rows))

counter = os.environ.get("NWAVE_MODEL_COUNTER")
if counter:
    path = pathlib.Path(counter)
    seen = int(path.read_text()) if path.exists() else 0
    path.write_text(str(seen + 1))
else:
    seen = len(rows) - 1

terminal_path = pathlib.Path(_opt("--output-last-message"))
answers = json.loads(pathlib.Path(os.environ["NWAVE_MODEL_RESULTS"]).read_text())
if seen >= len(answers):
    terminal_path.write_text(json.dumps({{"answer": {{
        "outcome": "indeterminate",
        "diagnostic": "the fake provider was invoked more times than the scenario declared",
    }}}}))
    sys.exit(0)
answer = answers[seen]

root = pathlib.Path(os.environ["NWAVE_MODEL_ROOT"])
for name, body in answer.get("writes", {{}}).items():
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
for name in answer.get("deletes", []):
    (root / name).unlink(missing_ok=True)

default = {{"outcome": "accepted", "diagnostic": ""}}
payload = answer.get("structured_output", default)
if agent.endswith("-reviewer") and "defect_owner" not in payload:
    payload = {{**payload,
               "defect_owner": None if payload["outcome"] == "accepted" else "oracle",
               "defect_value": None}}
if agent.endswith("software-crafter") and "blocked_by" not in payload:
    payload = {{**payload,
               "blocked_by": None if payload["outcome"] == "accepted" else "product"}}
terminal_path.write_text(json.dumps({{"answer": payload}}))
sys.exit(answer.get("exit", 0))
"""


def install(directory: Path) -> Path:
    """Put the provider stand-in in `directory` as `claude`, executable."""
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory / "claude"
    launcher.write_text(SCRIPT)
    launcher.chmod(0o755)
    # The Codex stand-in lives beside the Claude one so a caller that needs
    # `--provider codex` finds it on the same PATH entry without a second
    # environment wire.
    codex_launcher = directory / "codex"
    codex_launcher.write_text(CODEX_SCRIPT)
    codex_launcher.chmod(0o755)
    return launcher


def environment(
    root: Path,
    *,
    launcher_dir: Path,
    results: Path,
    log: Path,
    counter: Path | None = None,
    package_parent: Path | None = None,
    check_paths: list[str] | None = None,
) -> dict[str, str]:
    """The whole environment a suite runs a DES command under.

    `check_paths`, when given, names relative paths the launcher tests for
    readability, relative to its own execution cwd, at invocation time --
    before the caller can clean up an isolated checkout. The result is
    recorded per turn in the log's `readable_paths` key.
    """
    install(launcher_dir)
    variables = {
        **os.environ,
        "PATH": str(launcher_dir) + os.pathsep + os.environ["PATH"],
        "NWAVE_MODEL_ROOT": str(root),
        "NWAVE_MODEL_LOG": str(log),
        "NWAVE_MODEL_RESULTS": str(results),
        "NWAVE_PYTHON": sys.executable,
    }
    if counter is not None:
        variables["NWAVE_MODEL_COUNTER"] = str(counter)
    if package_parent is not None:
        variables["PYTHONPATH"] = str(package_parent)
    if check_paths is not None:
        variables["NWAVE_MODEL_CHECK_PATHS"] = os.pathsep.join(check_paths)
    return variables
