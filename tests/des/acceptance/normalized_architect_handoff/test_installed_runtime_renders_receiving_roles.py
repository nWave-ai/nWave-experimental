"""Installed users receive architect, acceptance and reviewer knowledge.

@contract-shape: real-io
The installed-layout integration obligation needs independent host runtimes;
it extends the existing feature journey, not a second walking skeleton.
No provider is invoked. No asset-directory override or checkout asset fallback
is admitted. Host owns execution and the recorded RED/GREEN observations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from tests.des.acceptance.normalized_architect_handoff.test_handoff_states_each_fact_once import (
    FIXTURE,
    executable_body,
    frozen_bytes,
    load,
    message,
)

from scripts.shared.agent_catalog import (
    build_ownership_map,
    detect_command_skills,
    is_public_agent,
    load_private_agents,
    load_private_skills,
    load_public_agents,
)
from scripts.shared.skill_distribution import enumerate_skills, filter_public_skills


CHECKOUT = Path(__file__).resolve().parents[4]
HOSTS = ("claude-code", "codex", "omp", "all")
HOST_CASES = tuple((host, dev) for host in HOSTS for dev in (False, True))
ROLE_MARKER = "=== [C] orchestrator ===\nnative_input: "


@dataclass(frozen=True)
class KnowledgeSource:
    kind: str
    raw: str


def declared_knowledge_sources(text: str) -> tuple[KnowledgeSource, ...]:
    """Enumerate concrete source declarations, not an extension allowlist."""
    sources = []
    unsupported = []
    for marker in re.finditer(r"<!--\s*(?:PRELOADED|TASK) SKILL START:[^\n]*", text):
        declaration = marker.group(0)
        match = re.search(r";\s*source:\s*(.*?)\s*-->\s*$", declaration)
        if match is None or not match.group(1):
            unsupported.append(declaration)
        else:
            sources.append(KnowledgeSource("preloaded", match.group(1)))

    operands = r'`[^`\n]*`|"[^"\n]*"|\'[^\'\n]*\'|[^\s]+'
    for match in re.finditer(r"\bRead\s+(" + operands + r")", text):
        operand = match.group(1)
        quoted = operand[:1] in ("`", '"', "'")
        if quoted and (len(operand) < 2 or operand[-1] != operand[0]):
            unsupported.append(operand)
            continue
        raw = operand[1:-1] if quoted else operand
        line_end = text.find("\n", match.end())
        line = text[
            text.rfind("\n", 0, match.start()) + 1 : line_end
            if line_end >= 0
            else len(text)
        ]
        standalone = (
            re.fullmatch(
                r"\s*(?:[-*]\s+|\d+[.)]\s+)?Read\s+(" + operands + r")\s*"
                r"(?:ON-TRIGGER\b[^\n]*)?",
                line,
            )
            is not None
        )
        # Concrete syntax, not the authority category's vocabulary, declares
        # a source. An unanchored slash-containing noun in a multiword prose
        # sentence is not a file operand. Relative extensionless file operands
        # are explicit when quoted, ./ or ../ anchored, or standalone.
        path_like = (
            quoted
            or raw.startswith(("/", "~", ".", "$", "{", "<", "\\"))
            or "://" in raw
            or (standalone and ("/" in raw or "\\" in raw))
            or bool(re.search(r"\.[A-Za-z0-9]{1,12}$", raw))
        )
        if not path_like:
            if standalone:
                unsupported.append(operand)
            continue
        if not raw or raw.startswith(("$", "{", "<", "\\")) or "://" in raw:
            unsupported.append(operand)
        else:
            sources.append(KnowledgeSource("read", raw))
    # The architect's compiled "Read these installed skills" list uses bare
    # file bullets. Include every concrete bullet path, not just SKILL.md.
    for match in re.finditer(r"(?m)^\s*-\s+(" + operands + r")\s*$", text):
        operand = match.group(1)
        raw = operand[1:-1] if operand[:1] in ("`", '"', "'") else operand
        if raw.startswith(("/", "~", "./", "../")):
            sources.append(KnowledgeSource("read-list", raw))
    # Tool-call-like declarations are not this emitted instruction grammar;
    # do not silently accept a declaration whose target was never enumerated.
    unsupported.extend(
        match.group(0) for match in re.finditer(r"\bRead\s*[(=]\s*[^\n]+", text)
    )
    assert not unsupported, message(
        "a declared knowledge source uses an unsupported or unresolved form",
        "silently dropping a source would make the containment population incomplete",
        "emit a concrete quoted or unquoted file path for every Read and a "
        "complete source path in every PRELOADED marker",
    )
    return tuple(dict.fromkeys(sources))


def tree_identity(root: Path) -> dict[str, str]:
    """Digest-only observations keep private source bytes out of diagnostics."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def candidate_digest(python_root: Path, asset_root: Path) -> str:
    inventory = {
        "python": tree_identity(python_root),
        "assets": tree_identity(asset_root),
    }
    return hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def isolated_environment(home: Path, cwd: Path) -> dict[str, str]:
    # Do not inherit host selectors, user-site imports, provider credentials,
    # editable PYTHONPATH, or a sibling test's Git/config environment.
    return {
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "NWAVE_PROJECT_ROOT": str(cwd),
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), "/usr/bin", "/bin")),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUTF8": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "TMPDIR": str(home / "tmp"),
        "NO_COLOR": "1",
    }


@dataclass(frozen=True)
class InstalledCandidate:
    python_root: Path
    asset_root: Path
    sha256: str


class InstalledRoleJourney:
    def __init__(self, root: Path, host: str, dev_mode: bool):
        self.root = root
        self.home = root / "home"
        self.consumer = root / "consumer"
        self.home.mkdir()
        self.consumer.mkdir()
        (self.home / "tmp").mkdir()
        self.host = host
        self.dev_mode = dev_mode
        self.environment = isolated_environment(self.home, self.consumer)
        self.source_before = tree_identity(CHECKOUT / "nWave")
        self.public_agents = load_public_agents(CHECKOUT / "nWave")
        self.private_agents = load_private_agents(CHECKOUT / "nWave")
        self.skill_entries = enumerate_skills(CHECKOUT / "nWave" / "skills")
        self.public_skills = (
            {
                entry.name
                for entry in filter_public_skills(
                    self.skill_entries,
                    self.public_agents,
                    build_ownership_map(CHECKOUT / "nWave" / "agents"),
                    detect_command_skills(CHECKOUT / "nWave" / "skills"),
                    load_private_skills(CHECKOUT / "nWave"),
                )
            }
            if self.public_agents
            else set()
        )
        self.private_skills = {
            entry.name for entry in self.skill_entries
        } - self.public_skills
        self.candidates: tuple[InstalledCandidate, ...] = ()

    def admitted(self, result: subprocess.CompletedProcess[str], action: str):
        # Installer logs can name source-private members under --dev. Never
        # echo those logs or real private names into a review/model packet.
        output_digest = hashlib.sha256(
            (result.stdout + result.stderr).encode()
        ).hexdigest()
        assert result.returncode == 0, message(
            f"{self.host} dev_mode={self.dev_mode}: {action} exited "
            f"{result.returncode}; captured output sha256={output_digest}",
            "the installed public journey must work without source-tree assets "
            "or asset-directory overrides",
            "repair the real installer/resolver at this named step; retain the "
            "isolated HOME and native input when diagnosing, never preseed "
            "agents/skills or pass template/skill overrides",
        )
        return result

    def install(self):
        assert not any(
            (parent / ".git").exists() for parent in (self.root, *self.root.parents)
        ), message(
            "consumer environment is inside a Git checkout",
            "a checkout could mask missing installed runtime assets",
            "place the isolated installed consumer outside every .git ancestor",
        )
        # The only upgrade residue staged by the observer is the actual
        # hooks-only shape. Missing agents/skills remain missing until shipped.
        residue = self.home / ".nwave" / "runtime" / "nWave" / "hooks"
        residue.mkdir(parents=True)
        (residue / "old-hook.py").write_text("# existing upgrade residue\n")
        install_env = {**self.environment, "PYTHONPATH": str(CHECKOUT / "src")}
        result = subprocess.run(
            [
                sys.executable,
                str(CHECKOUT / "scripts" / "install" / "install_nwave.py"),
                "--platform",
                self.host,
                *(["--dev"] if self.dev_mode else []),
            ],
            cwd=self.consumer,
            env=install_env,
            input="",
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
        self.admitted(result, "real installation")
        python_roots = (
            (self.home / ".claude" / "lib" / "python",)
            if self.host == "claude-code"
            else (
                self.home / ".claude" / "lib" / "python",
                self.home / ".nwave" / "runtime",
            )
            if self.host == "all"
            else (self.home / ".nwave" / "runtime",)
        )
        for python_root in python_roots:
            assert (python_root / "des" / "__main__.py").is_file(), message(
                f"the installer did not ship the DES entry at {python_root}",
                "a producer success is not an installed executable capability",
                "ship the selected host's actual DES runtime through the installer",
            )
        self.candidates = tuple(
            InstalledCandidate(
                python_root=python_root,
                asset_root=python_root.parent / "nWave",
                sha256=candidate_digest(python_root, python_root.parent / "nWave"),
            )
            for python_root in python_roots
        )
        return self

    def invoke(self, candidate: InstalledCandidate, directory: Path, *args, body=None):
        # -S prevents editable .pth/sitecustomize from importing the source
        # checkout; ordinary dependencies remain available from the declared
        # test interpreter's purelib, not from developer HOME.
        environment = {
            **self.environment,
            "PYTHONPATH": os.pathsep.join(
                (str(candidate.python_root), sysconfig.get_path("purelib"))
            ),
        }
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "des",
                args[0],
                "--repo-root",
                str(directory),
                *args[1:],
            ],
            cwd=directory,
            env=environment,
            input=(
                ""
                if body is None
                else json.dumps(executable_body(body), ensure_ascii=False)
            ),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )

    def assert_prompt_knowledge(
        self, text: str, candidate: InstalledCandidate, role: str
    ):
        sources = declared_knowledge_sources(text)
        assert sources, message(
            f"{role} prompt has no observable Read/PRELOADED source paths",
            "an empty path population cannot prove installed knowledge reachability",
            "render the role's real canonical instructions and installed skill references",
        )
        installed_root = candidate.asset_root.resolve(strict=True)
        for source in sources:
            path = Path(source.raw)
            try:
                target = path.resolve(strict=True) if path.is_absolute() else None
                valid = (
                    target is not None
                    and target.is_relative_to(installed_root)
                    and target.is_file()
                    and target.name == "SKILL.md"
                )
            except (OSError, RuntimeError):
                valid = False
            assert valid, message(
                f"{role} declared {source.kind} source is not a readable installed asset",
                "traversal, symlinks and unresolved sources must not borrow "
                "checkout or host-private knowledge",
                "resolve the actual file target and installed root before "
                "checking containment; require a readable SKILL.md and retain "
                "every declared source",
            )
        forbidden = self.private_skills | {f"nw-{name}" for name in self.private_agents}
        leaked = any(name in text for name in forbidden)
        assert not leaked, message(
            f"{role} public prompt contains a catalog-private name",
            "runtime public knowledge must not depend on private catalog members",
            "filter the runtime role/skill families and scrub removed frontmatter "
            "references in the runtime destination only",
        )

    def assert_source_discriminator(
        self, actual_prompt: str, candidate: InstalledCandidate, role: str
    ):
        """Challenge the observer, without replacing any SUT response."""
        self.assert_prompt_knowledge(actual_prompt, candidate, role)
        outside = self.root / "observer-external-source"
        outside.mkdir(exist_ok=True)
        external_skill = outside / "SKILL.md"
        external_note = outside / "reference.txt"
        external_skill.write_text("Synthetic external skill source.\n")
        external_note.write_text("Synthetic external non-skill source.\n")
        traversal = candidate.asset_root / os.path.relpath(
            external_skill, candidate.asset_root
        )
        # Mutated copies are observer counterexamples, not asserted product
        # outputs. No supplied prompt, runtime file or SUT response is replaced.
        for source in (traversal, external_note):
            derived = actual_prompt + f"\nRead `{source}`\n"
            with pytest.raises(
                AssertionError, match="source is not a readable installed asset"
            ):
                self.assert_prompt_knowledge(derived, candidate, role)
        with tempfile.TemporaryDirectory(
            prefix="observer-link-", dir=candidate.asset_root
        ) as directory:
            contained_note = Path(directory) / "reference.txt"
            contained_note.write_text("Synthetic contained non-skill source.\n")
            derived = actual_prompt + f"\nRead `{contained_note}`\n"
            with pytest.raises(
                AssertionError, match="source is not a readable installed asset"
            ):
                self.assert_prompt_knowledge(derived, candidate, role)
            link = Path(directory) / "linked-source.md"
            link.symlink_to(external_skill)
            derived = actual_prompt + f"\nRead `{link}`\n"
            with pytest.raises(
                AssertionError, match="source is not a readable installed asset"
            ):
                self.assert_prompt_knowledge(derived, candidate, role)
            preloaded = actual_prompt + (
                f"\n<!-- PRELOADED SKILL START: observer-control; source: {link} -->\n"
            )
            with pytest.raises(
                AssertionError, match="source is not a readable installed asset"
            ):
                self.assert_prompt_knowledge(preloaded, candidate, role)
        for raw, declaration in (
            ("missing-source", "Read `missing-source` before proceeding."),
            ("missing source", 'Read "missing source" before proceeding.'),
        ):
            derived = actual_prompt + "\n" + declaration + "\n"
            assert KnowledgeSource("read", raw) in declared_knowledge_sources(
                derived
            ), message(
                "an explicit quoted Read source vanished from the population",
                "absence of an extension or slash cannot erase a declaration",
                "enumerate quoted operands before resolving or refusing them",
            )
            with pytest.raises(
                AssertionError, match="source is not a readable installed asset"
            ):
                self.assert_prompt_knowledge(derived, candidate, role)
        unresolved = actual_prompt + "\nRead ${UNRESOLVED_KNOWLEDGE_FILE}\n"
        with pytest.raises(
            AssertionError, match="source uses an unsupported or unresolved form"
        ):
            self.assert_prompt_knowledge(unresolved, candidate, role)
        self.assert_candidate_and_source_preserved()

    def stage_external_models(self, directory: Path, manifests):
        mapping = load("run11-fact-map.json")
        frozen_models = {}
        for name in mapping["source_revision"]["current_normative_sources"]:
            original = json.loads(frozen_bytes(mapping, name))
            for section in original.get("architect_handoff", {}).get("sections", []):
                if section["kind"] == "model":
                    for model in section["status"].get("payload", {}).get("models", []):
                        frozen_models[model["path"]] = model["text"].encode()
        for manifest in manifests:
            for section in manifest.get("architect_handoff", {}).get("sections", []):
                if section["kind"] != "model":
                    continue
                for model in section["status"].get("payload", {}).get("models", []):
                    source = model["source"]
                    raw = frozen_models[source["path"]]
                    assert hashlib.sha256(raw).hexdigest() == source["sha256"], message(
                        "portable doctor model source differs from its declared digest",
                        "model bytes are an external fixture prerequisite, not "
                        "an observer-authored imitation",
                        "stage the immutable doctor fixture's exact frozen source",
                    )
                    path = directory / source["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)

    def receiving_roles_complete_the_journey(self):
        for index, candidate in enumerate(self.candidates):
            directory = self.consumer / f"runtime-{index}"
            directory.mkdir()
            context = directory / "root-context.md"
            context.write_bytes((FIXTURE / "root-context.md").read_bytes())
            self.admitted(
                self.invoke(
                    candidate,
                    directory,
                    "po",
                    "--feature",
                    "doctor-version-sync",
                    "--input",
                    "-",
                    body=load("po.json"),
                ),
                "installed PO construction",
            )
            architect = self.admitted(
                self.invoke(
                    candidate,
                    directory,
                    "handoff",
                    "prompt",
                    "--role",
                    "nw-solution-architect",
                    "--root-context",
                    "root-context.md",
                ),
                "architect prompt before normalized DESIGN",
            )
            self.assert_prompt_knowledge(
                architect.stdout, candidate, "nw-solution-architect"
            )
            if index == 0:
                self.assert_source_discriminator(
                    architect.stdout, candidate, "nw-solution-architect"
                )
            shared = load("shared.json")
            values = [load(f"value-{position}.json") for position in range(1, 4)]
            self.stage_external_models(directory, [shared, *values])
            self.admitted(
                self.invoke(
                    candidate,
                    directory,
                    "design",
                    "--shared",
                    "--input",
                    "-",
                    body=shared,
                ),
                "installed shared doctor DESIGN",
            )
            for position, manifest in enumerate(values, 1):
                self.admitted(
                    self.invoke(
                        candidate,
                        directory,
                        "design",
                        "--value",
                        str(position),
                        "--input",
                        "-",
                        body=manifest,
                    ),
                    f"installed doctor value {position} DESIGN",
                )
            for position in range(1, 4):
                for role in (
                    "nw-acceptance-designer",
                    "nw-acceptance-designer-reviewer",
                ):
                    rendered = self.admitted(
                        self.invoke(
                            candidate,
                            directory,
                            "handoff",
                            "prompt",
                            "--role",
                            role,
                            "--value",
                            str(position),
                            "--root-context",
                            "root-context.md",
                        ),
                        f"installed {role} prompt for value {position}",
                    )
                    self.assert_prompt_knowledge(rendered.stdout, candidate, role)
                    assert ROLE_MARKER in rendered.stdout, message(
                        f"{role} received instructions without the native input",
                        "knowledge alone does not deliver the selected operational facts",
                        "retain the real receiving-role packet in the installed prompt",
                    )
                    packet, _ = json.JSONDecoder().raw_decode(
                        rendered.stdout.split(ROLE_MARKER, 1)[1]
                    )
                    assert packet.get("facts"), message(
                        f"{role} received an empty current doctor catalog",
                        "an installed prompt must preserve current value meaning",
                        "use the production normalized packet producer, not a "
                        "knowledge-only success response",
                    )
        self.assert_candidate_and_source_preserved()

    def public_runtime_matches_catalog(self):
        expected_agents = {
            path.name
            for path in (CHECKOUT / "nWave" / "agents").glob("*.md")
            if self.public_agents and is_public_agent(path.name, self.public_agents)
        }
        assert expected_agents and self.public_skills, message(
            "the observed source catalog has no capable public role/skill population",
            "this installed journey needs real public receiving roles",
            "restore the current public source catalog; do not treat an "
            "unavailable catalog as an empty successful install",
        )
        snapshots = []
        for candidate in self.candidates:
            agents = candidate.asset_root / "agents"
            skills = candidate.asset_root / "skills"
            assert agents.is_dir() and skills.is_dir(), message(
                f"{self.host} lacks canonical runtime agents/ or skills/",
                "installed role_instructions maps nWave/agents to sibling nWave/skills",
                "ship public raw role families separately from the existing runtime "
                "asset-directory tuple",
            )
            actual_agents = {path.name for path in agents.glob("*.md")}
            actual_skills = {path.name for path in skills.iterdir() if path.is_dir()}
            matches = (
                actual_agents == expected_agents and actual_skills == self.public_skills
            )
            assert matches, message(
                f"{self.host} runtime agent/skill population differs from "
                "the catalog-derived public population",
                "no private or uncatalogued member may ship, and public "
                "capability cannot be obtained by omitting selected members",
                "use the existing explicit public-agent allowlist, ownership "
                "map and public skill filter regardless of dev_mode",
            )
            for path in agents.glob("*.md"):
                text = path.read_text()
                frontmatter = yaml.safe_load(text.split("---", 2)[1])
                declared = frontmatter.get("skills", [])
                private_reference = any(
                    name in self.private_skills for name in declared
                )
                assert not private_reference, message(
                    "a shipped public agent frontmatter names a removed private skill",
                    "a public installed prompt would otherwise need private knowledge",
                    "apply the moved scrub to destination copies, never source roles",
                )
            snapshots.append(tree_identity(candidate.asset_root))
        if len(snapshots) > 1:
            identical = all(snapshot == snapshots[0] for snapshot in snapshots[1:])
            assert identical, message(
                "the mixed target's canonical runtime mirrors differ",
                "each host consumes the same public installed candidate",
                "mirror the already-filtered runtime asset root",
            )
        self.assert_candidate_and_source_preserved()

    def assert_candidate_and_source_preserved(self):
        source_unchanged = tree_identity(CHECKOUT / "nWave") == self.source_before
        assert source_unchanged, message(
            "the real installer or role consumer changed the source nWave tier",
            "runtime filtering/scrubbing is destination-only",
            "keep every source byte unchanged when shipping and consuming role assets",
        )
        for candidate in self.candidates:
            assert (
                candidate_digest(candidate.python_root, candidate.asset_root)
                == candidate.sha256
            ), message(
                f"installed candidate at {candidate.python_root} changed "
                "during the receiving-role probes",
                "all public consumers must observe the same immutable installer output",
                "do not patch missing assets between role invocations or "
                "rewrite the installed artifact during inspection",
            )


@pytest.fixture(
    scope="module",
    params=HOST_CASES,
    ids=[f"{host}-{'dev' if dev else 'public'}" for host, dev in HOST_CASES],
)
def installed_role_journey(request):
    host, dev_mode = request.param
    with tempfile.TemporaryDirectory(prefix="nwave-installed-role-") as directory:
        yield InstalledRoleJourney(Path(directory), host, dev_mode).install()


def test_installed_users_receive_the_real_architect_acceptance_and_reviewer_flow(
    installed_role_journey,
):
    installed_role_journey.receiving_roles_complete_the_journey()


def test_installed_runtime_is_public_only_and_keeps_its_source_unchanged(
    installed_role_journey,
):
    installed_role_journey.public_runtime_matches_catalog()
