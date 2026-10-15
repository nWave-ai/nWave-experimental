"""Real installed response contract and public stdin constructor observation.

@contract-shape: real-io
@walking_skeleton @driving_port

The script captures actual stimuli, schema errors, exits and persisted artifacts.
It proves the selected response/binding journey, not live model adherence to prose.
Existing publication/CAS fault tests remain in the expanded verification recipe.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


REPOSITORY = Path(__file__).resolve().parents[4]
for import_root in (REPOSITORY, REPOSITORY / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import jsonschema
import yaml
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.architect_manifest_binding.semantic_cases import (
    DIAGNOSTICS,
    ManifestCase,
    accepted,
    canonical_manifest,
    finite_manifests,
    product_manifest,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    base_repository,
    block,
)

from des.adapters.driven.task_invocation.model_envelope import (
    _schema_for,
    codex_schema_for,
    decode_model_run,
)
from des.ports.driven_ports.task_invocation_port import MalformedModelEnvelope
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.omp_agents_plugin import OmpAgentsPlugin


ROLE = "nw-solution-architect"
DESTINATION = Path("docs/product/architecture/brief.md")
HANDOVER = Path(".nwave/des/handover.json")


def explanation(what: str, why: str, how: str) -> str:
    return f"WHAT: {what}\nWHY: {why}\nHOW: {how}"


def schema_errors(schema: dict, value: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{list(error.absolute_path)!r}: {error.message}"
        for error in validator.iter_errors(value)
    ]


def schema_nodes(value):
    """Visit schema positions, not property-name maps or annotation values.

    A business field named ``properties`` is not the schema keyword. Traverse
    each Draft 2020-12 applicator in its declared shape, including every branch
    and definition, while yielding only the schemas those positions contain.
    """
    if not isinstance(value, dict):
        return
    yield value
    for keyword in (
        "$defs",
        "properties",
        "patternProperties",
        "dependentSchemas",
    ):
        for child in value.get(keyword, {}).values():
            yield from schema_nodes(child)
    for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
        for child in value.get(keyword, ()):
            yield from schema_nodes(child)
    for keyword in (
        "items",
        "contains",
        "additionalProperties",
        "unevaluatedProperties",
        "unevaluatedItems",
        "propertyNames",
        "not",
        "if",
        "then",
        "else",
        "contentSchema",
    ):
        if keyword in value:
            yield from schema_nodes(value[keyword])


class ArchitectObservation:
    """One real installation; independent constructor namespaces per observation."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        home = workspace / "home"
        home.mkdir()
        # Every branch-affecting host input is explicit; no developer installation
        # or provider credential enters the fixture. No runtime lock/guard wrapper.
        self.environment = {
            "HOME": str(home),
            "NWAVE_AGENTS_HOME": str(home),
            "PI_CONFIG_DIR": ".omp",
            "OMP_PROFILE": "",
            "PI_PROFILE": "",
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "PATH": os.defpath,
            "PYTHONPATH": os.pathsep.join((str(REPOSITORY / "src"), str(REPOSITORY))),
            "PYTHONIOENCODING": "utf-8",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
        logger = logging.getLogger(__name__)
        context = InstallContext(
            claude_dir=home / ".claude",
            scripts_dir=REPOSITORY / "scripts",
            templates_dir=REPOSITORY / "nWave/templates",
            project_root=REPOSITORY,
            user_project_root=workspace,
            framework_source=REPOSITORY / "nWave",
            logger=logger,
            dev_mode=False,
            target_platforms={"omp"},
        )
        self.evidence: list[dict] = []
        with patch.dict(os.environ, self.environment, clear=True):
            installed = OmpAgentsPlugin().install(context)
        self.evidence.append(
            {
                "operation": "OmpAgentsPlugin.install",
                "candidate_root": str(REPOSITORY),
                "home": str(home),
                "success": installed.success,
                "message": installed.message,
                "errors": installed.errors,
                "installed_files": [str(path) for path in installed.installed_files],
            }
        )
        assert installed.success, explanation(
            f"real OMP installation failed: {installed.message}; {installed.errors}",
            "The carrier regression needs an emitted contract, not broken setup.",
            "Restore the declared installer/source prerequisites before measuring RED.",
        )
        agent = home / ".omp/agent/agents/nw-solution-architect.md"
        assert agent.is_file(), explanation(
            f"installation emitted no architect at {agent}",
            "A schema fabricated by a test cannot establish installed admission.",
            "Make the real installer publish the selected architect.",
        )
        contents = agent.read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(contents.split("---", 2)[1])
        self.installed_schema = frontmatter.get("output")
        assert isinstance(self.installed_schema, dict), explanation(
            f"installed architect output is not a schema: {self.installed_schema!r}",
            "The host needs its actual provider-enforced response contract.",
            "Project the canonical architect schema into OMP output frontmatter.",
        )
        self.evidence.append(
            {
                "operation": "read-installed-contract",
                "path": str(agent),
                "sha256": hashlib.sha256(contents.encode()).hexdigest(),
                "output": self.installed_schema,
            }
        )
        self.schemas = {
            "installed-omp": self.installed_schema,
            # Claude and the other canonical-schema hosts consume this same
            # existing published seam; Codex alone has the answer transport.
            "canonical-claude": json.loads(_schema_for(ROLE)),
            "codex": codex_schema_for(ROLE),
        }
        with patch.dict(os.environ, self.environment, clear=True):
            self.template = base_repository(workspace / "template")
        (self.template / ".nwave").mkdir()
        (self.template / ".nwave/config.json").write_text(
            json.dumps({"documents": {"design": {"destination": str(DESTINATION)}}}),
            encoding="utf-8",
        )

    def validate_response(self, response: dict, *, admitted: bool = True) -> None:
        for host, schema in self.schemas.items():
            transported = {"answer": response} if host == "codex" else response
            errors = schema_errors(schema, transported)
            self.evidence.append(
                {
                    "operation": "schema-admission",
                    "host": host,
                    "stimulus": transported,
                    "errors": errors,
                }
            )
            assert (not errors) == admitted, explanation(
                f"{host} {'rejected' if errors else 'admitted'} response "
                f"{response!r}; expected admitted={admitted}; errors={errors!r}",
                "Every projecting host must preserve the one outcome/manifest language.",
                "Generate the envelope from DESIGN forms; preserve optional absence "
                "and refuse contradictory or legacy payloads without translation.",
            )

    def decode_response(self, response: dict, *, admitted: bool = True) -> None:
        try:
            result = decode_model_run(copy.deepcopy(response), role_id=ROLE)
        except MalformedModelEnvelope as error:
            self.evidence.append(
                {
                    "operation": "decode-response",
                    "stimulus": response,
                    "error": str(error),
                }
            )
            assert not admitted, explanation(
                f"decoder refused declared response: {error}",
                "A schema-valid manifest must not require the retired facts carrier.",
                "Validate the new manifest envelope without reconstructing provider facts.",
            )
            return
        self.evidence.append(
            {
                "operation": "decode-response",
                "stimulus": response,
                "outcome": result.outcome.value,
                "diagnostic": result.diagnostic,
            }
        )
        assert admitted, explanation(
            f"decoder accepted malformed response {response!r}",
            "A contradictory or legacy carrier is not an accepted DESIGN input.",
            "Refuse the malformed envelope in the existing shared decoder.",
        )
        assert (result.outcome.value, result.diagnostic) == (
            response["outcome"],
            response["diagnostic"],
        ), explanation(
            f"decoder changed outcome/diagnostic to {(result.outcome.value, result.diagnostic)!r}",
            "Ownership prose is opaque and must survive verbatim.",
            "Return the original outcome and diagnostic; do not parse or rewrite ownership.",
        )

    def new_repository(self, parent: Path) -> Path:
        root = parent / "repository"
        shutil.copytree(self.template, root)
        return root

    def command(
        self,
        root: Path,
        operation: str,
        supplied: dict | None = None,
        *,
        process: bool = False,
    ):
        argv = [operation, "--repo-root", str(root)]
        if operation == "po":
            argv += ["--project", "--input", "-"]
        if operation == "design":
            argv += ["--value", "1", "--input", "-"]
        stdin = "" if supplied is None else json.dumps(supplied, ensure_ascii=False)
        if process:
            result = subprocess.run(
                [sys.executable, "-m", "des", *argv],
                cwd=root,
                env=self.environment,
                input=stdin,
                text=True,
                capture_output=True,
                check=False,
            )
            captured = (result.returncode, result.stdout, result.stderr)
        else:
            captured = run_cli_in_process(
                argv, cwd=root, env=self.environment, stdin_text=stdin, catch_all=True
            )
        self.evidence.append(
            {
                "operation": operation,
                "argv": [sys.executable, "-m", "des", *argv],
                "executor": "subprocess" if process else "in-process-dispatcher",
                "stdin": stdin,
                "exit": captured[0],
                "stdout": captured[1],
                "stderr": captured[2],
            }
        )
        return captured

    def bootstrap(self, root: Path, *, process: bool = False) -> None:
        code, out, err = self.command(root, "po", product_manifest(), process=process)
        assert code == 0 and block(out, err).get("DELIVERY-OUTCOME") == "Success", (
            explanation(
                f"public PO prerequisite failed: exit={code}, stdout={out!r}, stderr={err!r}",
                "A stored selected value is required before the intended carrier assertion.",
                "Restore the existing closed v2 PO stdin fixture/constructor path.",
            )
        )

    def state(self, root: Path) -> dict:
        return {
            "architecture": (root / DESTINATION).read_bytes()
            if (root / DESTINATION).exists()
            else None,
            "handover": (root / HANDOVER).read_bytes(),
            "readme": (root / "README.md").read_bytes(),
        }

    def bind(self, root: Path, case: ManifestCase, *, process: bool = False) -> None:
        before = self.state(root)
        response = accepted(case.manifest)
        # Only the accepted manifest is serialized, without intermediate files,
        # from_json rendering, facts synthesis, optional-null normalization or wrappers.
        code, out, err = self.command(
            root, "design", response["manifest"], process=process
        )
        after = self.state(root)
        self.evidence.append(
            {
                "operation": "binding-state",
                "before": {
                    key: None if value is None else value.decode()
                    for key, value in before.items()
                },
                "after": {
                    key: None if value is None else value.decode()
                    for key, value in after.items()
                },
            }
        )
        assert code == 0 and block(out, err).get("DELIVERY-OUTCOME") == "Success", (
            explanation(
                f"unchanged manifest binding failed: exit={code}, stdout={out!r}, stderr={err!r}",
                "The accepted carrier must already be the public constructor's complete input.",
                "Preserve the schema-2 language and submit only manifest on stdin; never add a bridge.",
            )
        )
        authority = json.loads(after["handover"])["values"][0]["authority"]
        assert authority["public_oracle"] == case.public_observation, explanation(
            f"persisted public oracle {authority.get('public_oracle')!r} differs "
            f"from independently supplied {case.public_observation!r}",
            "Schema/JSON transport must preserve the semantic observation, not only succeed.",
            "Bind the supplied public_oracle unchanged through the existing constructor.",
        )
        supplied = case.manifest
        expected_facts = {
            "targets": supplied["targets"],
            "paradigm": supplied["paradigm"],
            "decisions": supplied["decisions"],
            "constraints": supplied["constraints"],
            "oracle": supplied["oracle"],
            "acceptance_supports": supplied["acceptance_supports"],
            "verification": supplied["verification"],
            "oracle_verification_index": supplied["oracle_verification_index"],
            "facts": supplied["facts"],
            "purpose": supplied["purpose"],
            "inherits": supplied.get("inherits", []),
        }
        for field, expected in expected_facts.items():
            assert authority.get(field) == expected, explanation(
                f"bound {field} is {authority.get(field)!r}, expected {expected!r}",
                "The single manifest carrier preserves the existing internal facts contract.",
                "Derive persisted facts from the unchanged manifest through the constructor.",
            )
        expected_locator = f"{DESTINATION.as_posix()}#Value 1"
        assert authority["authority_locator"] == expected_locator, explanation(
            f"bound locator is {authority.get('authority_locator')!r}, expected {expected_locator!r}",
            "The installed response must publish and bind the requested authority.",
            "Retain the configured destination and compiled scope heading.",
        )
        assert after["architecture"] is not None and (
            b"## Value 1\n" in after["architecture"]
        ), explanation(
            "Success did not publish the requested authority section",
            "A handover designation without an actual document is not direct binding.",
            "Publish the selected manifest through the existing authority producer.",
        )
        assert (
            after["readme"] == before["readme"]
            and after["handover"] != before["handover"]
        ), explanation(
            "binding did not change handover or changed the unrelated README",
            "The declared state transition binds authority while preserving adjacent public state.",
            "Limit constructor publication to its configured authority and handover.",
        )
        self.assert_restored(root)

    def assert_restored(self, root: Path) -> None:
        code, out, err = self.command(root, "state")
        assert code == 0, explanation(
            f"public state could not restore the bound authority: {out!r} {err!r}",
            "Live persisted internal DesignFacts must survive retiring the provider carrier.",
            "Keep constructor-derived facts and their existing handover restoration consumers.",
        )

    def assert_nonaccepting(self, root: Path) -> None:
        before = self.state(root)
        submissions_before = sum(row["operation"] == "design" for row in self.evidence)
        for outcome, diagnostic in DIAGNOSTICS.items():
            for present in (False, True):
                response = {"outcome": outcome, "diagnostic": diagnostic}
                if present:
                    response["manifest"] = None
                # Codex requires explicit null at its envelope boundary; only
                # canonical optional absence is projected here, never a manifest field.
                canonical_errors = {
                    name: schema_errors(schema, response)
                    for name, schema in self.schemas.items()
                    if name != "codex"
                }
                assert not any(canonical_errors.values()), explanation(
                    f"nonaccepting {outcome} manifest-present={present} was refused: {canonical_errors}",
                    "Canonical hosts permit manifest null or absent for nonacceptance.",
                    "Preserve diagnostic-only branches of the architect envelope.",
                )
                codex_response = {**response, "manifest": None}
                errors = schema_errors(
                    self.schemas["codex"], {"answer": codex_response}
                )
                assert not errors, explanation(
                    f"Codex refused diagnostic-only {outcome}: {errors}",
                    "Strict transport must preserve nonaccepting outcome meaning.",
                    "Project the nonaccepting branch with a null manifest.",
                )
                self.decode_response(response)
                self.evidence.append(
                    {
                        "operation": "nonaccepting-host-response",
                        "stimulus": response,
                        "codex_transport": {"answer": codex_response},
                        "design_submitted": False,
                    }
                )
        assert self.state(root) == before and (
            sum(row["operation"] == "design" for row in self.evidence)
            == submissions_before
        ), explanation(
            "diagnostic-only response processing changed DESIGN state or submitted a manifest",
            "Only an accepted response authorizes this host's manifest submission.",
            "Keep nonaccepting processing diagnostic-only with no constructor invocation.",
        )

    def assert_invalid_constructor(self, root: Path, manifest: dict) -> None:
        before = self.state(root)
        code, out, err = self.command(root, "design", manifest)
        rows = block(out, err)
        assert (
            code == 1
            and rows.get("WHAT") == "InvalidDesignDocument"
            and all(rows.get(label) for label in ("WHAT", "WHY", "HOW"))
        ), explanation(
            f"invalid manifest was not self-explaining refusal: exit={code}, {out!r}, {err!r}",
            "A structural provider projection must not broaden semantic constructor admission.",
            "Retain the existing InvalidDesignDocument WHAT/WHY/HOW validation.",
        )
        references = manifest.get("constraints")
        if (
            isinstance(references, list)
            and len(references) > 1
            and references[0] == references[1]
            and isinstance(references[0], dict)
            and set(references[0]) == {"ref"}
        ):
            assert "DesignListEntryRepeated" in out + err
            assert "manifest.constraints" in out + err
            assert references[0]["ref"] in out + err
        assert self.state(root) == before, explanation(
            "invalid manifest mutated authority, handover or unrelated README",
            "Constructor refusal cannot publish an invalid designation.",
            "Retain existing before-write validation and publication semantics.",
        )


def main() -> int:
    observation = None
    try:
        with tempfile.TemporaryDirectory(prefix="architect-manifest-") as directory:
            observation = ArchitectObservation(Path(directory))
            root = observation.new_repository(Path(directory) / "journey")
            observation.bootstrap(root, process=True)
            case = ManifestCase(canonical_manifest())
            # Capture the actual constructor too when the installed schema is
            # stale. This is an independent constructor probe, not an admitted
            # host response or a workaround route.
            observation.bind(root, case, process=True)
            observation.validate_response(accepted(case.manifest))
            observation.decode_response(accepted(case.manifest))
            observation.assert_nonaccepting(root)
            for index, variant in enumerate(finite_manifests()[1:]):
                with tempfile.TemporaryDirectory(
                    dir=directory, prefix=f"variant-{index}-"
                ) as namespace:
                    other = observation.new_repository(Path(namespace))
                    observation.bootstrap(other)
                    observation.validate_response(accepted(variant.manifest))
                    observation.bind(other, variant)
            invalid = canonical_manifest()
            invalid["oracle_verification_index"] = 1
            observation.assert_invalid_constructor(root, invalid)
        print(
            json.dumps(
                {"outcome": "accepted", "observations": observation.evidence},
                ensure_ascii=False,
            )
        )
        return 0
    except (AssertionError, OSError, ValueError, KeyError) as error:
        print(
            json.dumps(
                {
                    "outcome": "rejected"
                    if isinstance(error, AssertionError)
                    else "indeterminate",
                    "diagnostic": str(error),
                    "observations": [] if observation is None else observation.evidence,
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
