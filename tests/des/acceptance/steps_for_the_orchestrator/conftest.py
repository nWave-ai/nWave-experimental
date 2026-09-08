"""One real repository and one fake provider, shared by every step scenario.

The provider stand-in is `tests.des.acceptance.fake_provider`, the SAME one the
composed-run corpus drives: a real executable named `claude` first on `PATH`,
answering one recorded turn per invocation.  It is shared rather than copied
because two fakes are two spellings of one provider contract, and this corpus
was once written with a Product Owner envelope that omitted `values` -- which
the real boundary refuses -- so the scenario measured the schema instead of the
law it was written for.  Nothing in production is changed to make a step
testable: the step resolves its launcher exactly as it does in a real delivery.

The turn LOG is what makes «no step executes what its own NEXT names» a
measurable property rather than a claim: a step that ran a second role would
leave a second row in it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider


PACKAGE_PARENT = Path(__file__).parents[4] / "src"

#: The role specs a step resolves its turn from. A step reads them out of the
#: checkout it was POINTED AT, so the fixture repository has to carry them: a
#: repository without them resolves nothing there and falls through to whatever
#: the host developer installed, which is why this corpus passed on a developer
#: machine and answered `ProductOwnerIndeterminate` on a clean CI runner.
CHECKOUT_AGENT_SPECS = Path(__file__).parents[4] / "nWave" / "agents"


#: The measured placeholder floor refuses an observation shorter than this, so
#: every fixture value is a real-length sentence the way a real turn's is.
def observation(label: str) -> str:
    return f"the installed command observably reports the value named {label}"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def base_repository(repository: Path) -> Path:
    """One real repository with one commit -- the orchestrator's live checkout.

    Every scenario in this corpus builds its checkout HERE, the fixture below
    and the property's own harness alike, because a checkout that carries the
    role specs and one that does not are two different provider surfaces and
    only one of them is the delivery being measured.
    """
    repository.mkdir(parents=True, exist_ok=True)
    git(repository, "init", "-q")
    git(repository, "config", "user.email", "a@b")
    git(repository, "config", "user.name", "a")
    (repository / "README.md").write_text("x\n")
    # Committed with the base, so the specs are part of the checkout every step
    # reads and never part of the radius a later scenario measures.
    shutil.copytree(CHECKOUT_AGENT_SPECS, repository / "nWave" / "agents")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "base")
    return repository


def hermetic_environment(
    environment: dict[str, str], claude_dir: Path
) -> dict[str, str]:
    """Point the INSTALLED spec candidate at an empty directory.

    The second candidate a role's spec is resolved from is the installed
    deployment under the Claude configuration directory. Pointing it at an empty
    directory is what makes a scenario measure the checkout it built and nothing
    the host developer happens to have installed -- the difference between a
    corpus that passes on a developer machine and one that also passes on a
    clean runner, where the installed candidate answers nothing.
    """
    claude_dir.mkdir(parents=True, exist_ok=True)
    return environment | {"CLAUDE_CONFIG_DIR": str(claude_dir)}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """One real repository with one commit -- the orchestrator's live checkout."""
    return base_repository(tmp_path / "root")


@pytest.fixture
def turns(tmp_path: Path) -> Path:
    """Every turn the fake provider was actually asked for, in order."""
    return tmp_path / "model-log.json"


@pytest.fixture
def step(root: Path, tmp_path: Path, turns: Path):
    """Invoke one real `des` step against `root`, with the provider faked."""
    launcher_dir = tmp_path / "bin"
    results = tmp_path / "results.json"
    counter = tmp_path / "results-consumed"
    claude_dir = tmp_path / "claude-config"

    def invoke(*argv: str, answers: list[dict] | None = None, stdin: str = ""):
        results.write_text(json.dumps(answers if answers is not None else []))
        counter.unlink(missing_ok=True)
        environment = hermetic_environment(
            fake_provider.environment(
                root,
                launcher_dir=launcher_dir,
                results=results,
                log=turns,
                # A step is invoked many times and each invocation declares only
                # the answers ITS turns consume, so the ordinal restarts here
                # while the log stays cumulative for the counts a scenario reads.
                counter=counter,
                package_parent=PACKAGE_PARENT,
            ),
            claude_dir,
        )
        return run_cli_in_process(
            list(argv),
            cwd=root,
            env=environment,
            stdin_text=stdin,
            catch_all=True,
        )

    return invoke


def asked(turns: Path) -> list[str]:
    """The roles the step actually bought a turn from, in order."""
    if not turns.exists():
        return []
    return [row["agent"] for row in json.loads(turns.read_text())]


def block(stdout: str, stderr: str = "") -> dict[str, str]:
    """The terminal as labelled lines, which is a step's whole machine surface."""
    found: dict[str, str] = {}
    for line in (stdout + "\n" + stderr).splitlines():
        label, separator, rest = line.partition(": ")
        if separator:
            found.setdefault(label, rest)
    return found


def nexts(stdout: str) -> list[str]:
    """Every canonical next step the terminal named, as DATA, in order."""
    return [
        line[len("NEXT: ") :]
        for line in stdout.splitlines()
        if line.startswith("NEXT: ")
    ]


def accepted_values(*labels: str) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "decomposed into its ordered observable values",
            "values": [{"observation": observation(label)} for label in labels],
        }
    }
