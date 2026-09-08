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
import json, os, pathlib, sys

argv = sys.argv[1:]
agent = argv[argv.index("--agent") + 1]
log = pathlib.Path(os.environ["NWAVE_MODEL_LOG"])
rows = json.loads(log.read_text()) if log.exists() else []
rows.append({{"agent": agent, "prompt": sys.stdin.read(), "cwd": os.getcwd()}})
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


def install(directory: Path) -> Path:
    """Put the provider stand-in in `directory` as `claude`, executable."""
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory / "claude"
    launcher.write_text(SCRIPT)
    launcher.chmod(0o755)
    return launcher


def environment(
    root: Path,
    *,
    launcher_dir: Path,
    results: Path,
    log: Path,
    counter: Path | None = None,
    package_parent: Path | None = None,
) -> dict[str, str]:
    """The whole environment a suite runs a DES command under."""
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
    return variables
