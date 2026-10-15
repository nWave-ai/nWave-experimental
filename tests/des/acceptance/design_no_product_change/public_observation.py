"""Public constructor-to-crafter observations; @contract-shape: real-io."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

from tests.common.in_process_cli import run_cli_in_process
from tests.des._helpers.host_facts import design_manifest, product_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    base_repository,
    block,
    git,
)


VALUE = "Authors declare no product change without granting consultation paths mutation authority."
ORACLE = "tests/test_preserved_product.py"
SUPPORT = "tests/product_support.txt"
DESTINATION = "docs/product/architecture/brief.md"


def require(condition, what, how):
    assert condition, f"WHAT: {what}; WHY: {VALUE}; HOW: {how}"


@dataclass(frozen=True)
class Declaration:
    name: str
    product_change: str | None
    decisions: tuple[str, ...]
    consultations: tuple[str, ...] = ("README.md", "consulted.txt")
    accepted: bool = True


CASES = (
    Declaration("no_change_without_consultation", "none", (), ()),
    Declaration("no_change_with_one_consultation", "none", (), ("README.md",)),
    Declaration("no_change_with_consultation", "none", ()),
    Declaration("legacy_extend", None, ("EXTEND",)),
    Declaration("required_extend", "required", ("EXTEND",)),
    Declaration("legacy_create", None, ("CREATE_NEW",)),
    Declaration("required_create", "required", ("CREATE_NEW",)),
    Declaration("required_mixed_mutation", "required", ("EXTEND", "CREATE_NEW")),
    Declaration("required_excludes_oracle", "required", ("EXTEND", "ORACLE")),
    Declaration("contradictory_no_change", "none", ("EXTEND",), accepted=False),
    Declaration(
        "contradictory_no_change_create_new",
        "none",
        ("CREATE_NEW",),
        accepted=False,
    ),
    Declaration("missing_legacy_targets", None, (), accepted=False),
    Declaration("missing_required_targets", "required", (), accepted=False),
    Declaration("unknown_change", "maybe", (), accepted=False),
    Declaration("consultation_is_not_a_target", "required", ("REUSE",), accepted=False),
    Declaration("consult_target_is_invalid", "required", ("CONSULT",), accepted=False),
    Declaration("oracle_is_not_mutable", "required", ("ORACLE",), accepted=False),
)


class PublicJourney:
    def __init__(self, workspace):
        self.workspace = workspace
        home = workspace / "home"
        home.mkdir(parents=True)
        self.env = {
            "HOME": str(home),
            "NWAVE_AGENTS_HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "PI_CONFIG_DIR": ".omp",
            "OMP_PROFILE": "",
            "PI_PROFILE": "",
            "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
            "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT))),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
        with patch.dict(os.environ, self.env, clear=True):
            self.template = base_repository(workspace / "template")
        shutil.copytree(ROOT / "nWave/templates", self.template / "nWave/templates")
        (self.template / "consulted.txt").write_text("consultation only\n")
        (self.template / "context.txt").write_text(
            "Preserve the recorded oracle and consult evidence without inventing edits.\n"
        )
        (self.template / "tests").mkdir()
        (self.template / SUPPORT).write_text("immutable support\n")
        (self.template / ORACLE).write_text(
            "from pathlib import Path\n"
            "def test_product_is_preserved():\n"
            "    assert Path('README.md').read_text() == 'x\\n', 'WHAT: product changed; WHY: no change is needed; HOW: preserve README'\n"
        )
        (self.template / ".nwave").mkdir()
        (self.template / ".nwave/config.json").write_text(
            json.dumps({"documents": {"design": {"destination": DESTINATION}}})
        )
        with patch.dict(os.environ, self.env, clear=True):
            git(self.template, "add", ".")
            git(self.template, "commit", "-qm", "declared subject inputs")

    def command(self, root, label, argv, payload=None):
        stdin = "" if payload is None else json.dumps(payload)
        code, out, err = run_cli_in_process(
            argv, cwd=root, env=self.env, stdin_text=stdin, catch_all=True
        )
        print(
            json.dumps(
                {
                    "label": label,
                    "argv": [sys.executable, "-m", "des", *argv],
                    "executor": "source-tree-in-process-dispatcher",
                    "input": payload,
                    "exit": code,
                    "stdout": out,
                    "stderr": err,
                }
            ),
            flush=True,
        )
        return code, out, err

    def snapshot(self, root):
        names = (
            "README.md",
            "consulted.txt",
            "new_product.txt",
            ORACLE,
            SUPPORT,
            DESTINATION,
            ".nwave/des/handover.json",
        )
        return {
            name: (root / name).read_text() if (root / name).is_file() else None
            for name in names
        }

    def manifest(self, case):
        targets = [
            {
                "path": ORACLE
                if decision == "ORACLE"
                else "new_product.txt"
                if decision == "CREATE_NEW"
                else "README.md",
                "decision": "EXTEND" if decision == "ORACLE" else decision,
            }
            for decision in case.decisions
        ]
        na = {
            "applicability": "not_applicable",
            "reason": "No independent boundary changes in this subject.",
        }
        facts = {
            "targets": targets,
            "paradigm": "object_oriented",
            "decisions": ["Consultation is evidence, not mutation permission."],
            "architectural_tests": na,
            "contract_tests": na,
            "prefactoring": na,
            "agreement_analysis": na,
            "oracle": ORACLE,
            "acceptance_supports": [SUPPORT],
            "verification": [[sys.executable, "-m", "pytest", "-q", ORACLE]],
            "reuse_analysis": {
                "candidates": [
                    {
                        "symbol": name,
                        "locator": name + ":1",
                        "decision": "REUSE",
                        "reason": "Consult existing evidence without authorizing changes.",
                    }
                    for name in case.consultations
                ]
            },
        }
        manifest = design_manifest(facts, VALUE, 1)
        if case.product_change is not None:
            manifest["product_change"] = case.product_change
        return manifest

    def observe(self, case):
        root = self.workspace / case.name
        shutil.copytree(self.template, root)
        code, out, err = self.command(
            root,
            "selected-product",
            ["po", "--repo-root", str(root), "--project", "--input", "-"],
            product_manifest(VALUE, [VALUE]),
        )
        require(
            code == 0,
            f"public PO prerequisite failed: {out}{err}",
            "Restore the existing PO fixture before measuring DESIGN behavior.",
        )
        before = self.snapshot(root)
        manifest = self.manifest(case)
        code, out, err = self.command(
            root,
            case.name,
            ["design", "--repo-root", str(root), "--value", "1", "--input", "-"],
            manifest,
        )
        after = self.snapshot(root)
        print(
            json.dumps(
                {
                    "label": "constructor-state",
                    "case": case.name,
                    "before": before,
                    "after": after,
                }
            ),
            flush=True,
        )
        require(
            (code == 0) == case.accepted,
            f"{case.name}: exit={code}; expected accepted={case.accepted}; {out}{err}",
            "Admit explicit none only with empty targets; retain required mutation declarations.",
        )
        preserved = (
            set(before) - {DESTINATION, ".nwave/des/handover.json"}
            if case.accepted
            else set(before)
        )
        require(
            all(before[name] == after[name] for name in preserved),
            f"{case.name} changed preserved population {sorted(preserved)}",
            "Do not mutate product/oracle/support bytes; refuse before publication.",
        )
        if not case.accepted:
            self.refusal(out, err)
            require(
                "des design" in out + err,
                "refusal omitted constructor correction",
                "Route correction through des design --input -.",
            )
            return
        value_envelope = json.loads(after[".nwave/des/handover.json"])["values"][0]
        authority = value_envelope["authority"]
        print(
            json.dumps(
                {"label": "persisted-authority", "case": case.name, "facts": authority}
            ),
            flush=True,
        )
        require(
            authority.get("product_change", "required")
            == (case.product_change or "required"),
            f"lost product_change in {authority}",
            "Persist and restore the closed alternative.",
        )
        if case.product_change != "none":
            require(
                authority.get("product_change") == "required",
                f"default declaration lost its normalized alternative: {authority}",
                "Persist the explicit schema-2 required alternative.",
            )
            persisted_before = value_envelope.get("design_semantic_sha256")
            emitted_before = block(out, err).get("SEMANTIC-SHA256")
            equivalent = dict(manifest)
            if "product_change" in equivalent:
                equivalent.pop("product_change")
            else:
                equivalent["product_change"] = "required"
            code, out, err = self.command(
                root,
                "default-canonical-identity",
                [
                    "design",
                    "--repo-root",
                    str(root),
                    "--value",
                    "1",
                    "--replace-current",
                    "--input",
                    "-",
                ],
                equivalent,
            )
            replacement = json.loads((root / ".nwave/des/handover.json").read_text())[
                "values"
            ][0]
            canonical = replacement["authority"]
            persisted_after = replacement.get("design_semantic_sha256")
            emitted_after = block(out, err).get("SEMANTIC-SHA256")
            print(
                json.dumps(
                    {
                        "label": "default-canonical-identities",
                        "case": case.name,
                        "persisted_before": persisted_before,
                        "emitted_before": emitted_before,
                        "persisted_after": persisted_after,
                        "emitted_after": emitted_after,
                        "authority_before": authority,
                        "authority_after": canonical,
                    }
                ),
                flush=True,
            )
            require(
                code == 0,
                f"equivalent required declaration refused: {out}{err}",
                "Preserve omitted/explicit-required constructor equivalence.",
            )
            require(
                isinstance(persisted_before, str)
                and re.fullmatch(r"[0-9a-f]{64}", persisted_before) is not None
                and persisted_before == emitted_before,
                f"default-initial-persisted-emitted-agreement: persisted={persisted_before!r}; emitted={emitted_before!r}",
                "Bind and emit the same canonical semantic identity on the initial des design submission.",
            )
            require(
                isinstance(persisted_after, str)
                and re.fullmatch(r"[0-9a-f]{64}", persisted_after) is not None
                and persisted_after == emitted_after,
                f"default-replacement-persisted-emitted-agreement: persisted={persisted_after!r}; emitted={emitted_after!r}",
                "Bind and emit the same canonical semantic identity on des design --replace-current.",
            )
            require(
                persisted_before == persisted_after,
                f"default-persisted-identity-conservation: expected={persisted_before!r}; actual={persisted_after!r}",
                "Normalize omitted and explicit required before hashing, preserving persisted design_semantic_sha256.",
            )
            require(
                emitted_before == emitted_after,
                f"default-emitted-identity-conservation: expected={emitted_before!r}; actual={emitted_after!r}",
                "Normalize omitted and explicit required before hashing, preserving emitted SEMANTIC-SHA256.",
            )
            require(
                canonical == authority,
                f"default canonical facts or identity changed: {authority!r} -> {canonical!r}",
                "Normalize required before hashing and wire projection, preserving the historical omitted form.",
            )
        require(
            authority["targets"] == manifest["targets"],
            f"mutation population changed: {authority['targets']}",
            "Preserve target authority without promoting reuse candidates.",
        )
        code, out, err = self.command(
            root, "restored-state", ["state", "--repo-root", str(root)]
        )
        require(
            code == 0,
            f"stored authority cannot restore: {out}{err}",
            "Carry explicit none through stored authority restoration.",
        )
        code, out, err = self.command(
            root,
            "record-preserved-oracle",
            [
                "oracle",
                "--repo-root",
                str(root),
                "--value",
                "1",
                "--baseline",
                git(root, "rev-parse", "HEAD"),
                "--input",
                "-",
            ],
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "Measure the existing product preservation observation.",
                }
            },
        )
        require(
            code == 0,
            f"existing GREEN oracle cannot be recorded: {out}{err}",
            "Preserve native GREEN measurement for an already satisfied no-change value.",
        )
        prompt = [
            "handoff",
            "prompt",
            "--repo-root",
            str(root),
            "--role",
            "nw-software-crafter",
            "--value",
            "1",
            "--root-context",
            "context.txt",
        ]
        code, out, err = self.command(root, "crafter-authority", prompt)
        require(
            code == 0,
            f"crafter cannot consume bound declaration: {out}{err}",
            "Project the explicit empty authority without manufacturing a target.",
        )
        marker = "=== [C] orchestrator ===\nnative_input: "
        require(
            out.count(marker) == 1,
            f"canonical fact carrier is missing or ambiguous: {out}",
            "Emit one lossless native_input carrier in the orchestrator block.",
        )
        instructions, _, native_input = out.partition(marker)
        try:
            packet, _ = json.JSONDecoder().raw_decode(native_input.lstrip())
        except ValueError as error:
            require(
                False,
                f"canonical mutation facts cannot be decoded: {error}",
                "Emit valid JSON in the public native_input carrier.",
            )
        require(
            isinstance(packet, dict),
            f"canonical mutation facts are not an object: {packet!r}",
            "Preserve the path-addressed selected_authority and invocation facts.",
        )
        selected = packet.get("selected_authority")
        invocation = packet.get("invocation")
        require(
            isinstance(selected, dict) and isinstance(invocation, dict),
            f"selected authority or invocation is missing: {selected!r}, {invocation!r}",
            "Emit both the complete declaration and actual invocation restriction.",
        )
        declared_population = selected.get("targets")
        invoked_paths = invocation.get("targets")
        require(
            isinstance(declared_population, list)
            and all(
                isinstance(row, dict)
                and set(row) == {"path", "decision", "reason"}
                and isinstance(row["path"], str)
                and isinstance(row["decision"], str)
                and isinstance(row["reason"], dict)
                and set(row["reason"]) == {"ref"}
                for row in declared_population
            )
            and isinstance(invoked_paths, list)
            and all(isinstance(path, str) for path in invoked_paths),
            f"mutation population or invocation restriction is malformed: {declared_population!r}, {invoked_paths!r}",
            "Emit declared path/decision pairs and a concrete list of authorized invocation paths.",
        )
        expected_declared = [
            (row["path"], row["decision"]) for row in manifest["targets"]
        ]
        require(
            sorted((row["path"], row["decision"]) for row in declared_population)
            == sorted(expected_declared),
            f"complete canonical declaration {declared_population!r} differs from independently submitted {expected_declared!r}",
            "Preserve every declared target and decision without adding arbitrary or consultation-only targets.",
        )
        require(
            declared_population == manifest["targets"],
            f"target reasons changed: {declared_population!r}",
            "Retain every target's explicit catalog reference.",
        )
        expected_population = [
            (row["path"], row["decision"])
            for row in manifest["targets"]
            if row["path"] != ORACLE
        ]
        expected = {path for path, _ in expected_population}
        require(
            sorted(invoked_paths) == sorted(path for path, _ in expected_population),
            f"actual invocation mutation population {invoked_paths!r} differs from expected {sorted(expected)!r}",
            "Authorize exactly the declared production paths, excluding the immutable oracle and supports.",
        )
        emitted_population = [
            (row["path"], row["decision"])
            for row in declared_population
            if row["path"] in invoked_paths
        ]
        require(
            sorted(emitted_population) == sorted(expected_population),
            f"complete effective mutation population {emitted_population!r} differs from expected {expected_population!r}",
            "Resolve selected_authority.targets through invocation.targets without adding, dropping or changing mutation permissions.",
        )
        target_lines = [
            line
            for line in instructions.splitlines()
            if "production targets you may change" in line
        ]
        require(
            len(target_lines) == 1
            and re.search(
                r"native_input\.selected_authority\.targets\s*,?\s*restricted\s+by\s+native_input\.invocation\.targets",
                target_lines[0],
            ),
            f"human target advertisement does not resolve the canonical restriction: {target_lines!r}",
            "Point the crafter to selected_authority.targets restricted by invocation.targets.",
        )
        if case.product_change == "none":
            require(
                selected.get("product_change") == "none"
                and "No product changes authorized" in instructions
                and "recorded and RED" not in instructions,
                f"no-change mode or typed declaration is missing or demands fabricated RED: {selected!r}",
                "Preserve explicit none and explain that the recorded observation requires no product edits.",
            )
        print(
            json.dumps(
                {
                    "label": "effective-crafter-mutation-population",
                    "case": case.name,
                    "selected_authority": selected,
                    "invocation": invocation,
                    "effective_population": emitted_population,
                }
            ),
            flush=True,
        )
        for consulted in set(case.consultations) - expected:
            code, out, err = self.command(
                root, "consultation-override", [*prompt, "--targets", consulted]
            )
            require(
                code != 0,
                f"consulted override {consulted} granted authority",
                "Reject --targets outside the bound mutable population.",
            )
            self.refusal(out, err)
        final = self.snapshot(root)
        require(
            all(final[name] == before[name] for name in preserved),
            "public consumers changed product/oracle/support bytes",
            "Keep measurement and handoff read-only on the declared preservation population.",
        )
        print(
            json.dumps(
                {
                    "label": "preserved-product-state",
                    "case": case.name,
                    "population": sorted(preserved),
                    "before": {k: before[k] for k in preserved},
                    "after": {k: final[k] for k in preserved},
                }
            ),
            flush=True,
        )
        if case.name == "no_change_with_one_consultation":
            handover = root / ".nwave/des/handover.json"
            malformed = json.loads(handover.read_text())
            malformed["values"][0]["authority"]["product_change"] = (
                "unreadable-alternative"
            )
            handover.write_text(json.dumps(malformed))
            broken_before = self.snapshot(root)
            code, out, err = self.command(
                root, "malformed-authority-discriminator", prompt
            )
            broken_after = self.snapshot(root)
            print(
                json.dumps(
                    {
                        "label": "malformed-authority-preservation",
                        "case": case.name,
                        "supplied_persisted_authority": malformed["values"][0][
                            "authority"
                        ],
                        "population": sorted(broken_before),
                        "before": broken_before,
                        "after": broken_after,
                        "argv": [sys.executable, "-m", "des", *prompt],
                        "exit": code,
                        "stdout": out,
                        "stderr": err,
                    }
                ),
                flush=True,
            )
            require(
                code != 0,
                f"malformed authority became a valid empty population: {out}{err}",
                "Refuse unknown persisted alternatives instead of treating inability to restore as no change.",
            )
            self.refusal(out, err)
            require(
                broken_after == broken_before,
                "malformed authority refusal changed subject state",
                "Keep refusal read-only and preserve the malformed-input evidence.",
            )

    def refusal(self, out, err):
        fields = block(out, err)
        require(
            all(fields.get(key) for key in ("WHAT", "WHY", "HOW")),
            f"refusal lacks WHAT/WHY/HOW: {out}{err}",
            "Explain the conflicting declaration and concrete producing-tool correction.",
        )


def main():
    result = unittest.TestResult()
    with tempfile.TemporaryDirectory(prefix="design-authority-") as directory:
        try:
            journey = PublicJourney(Path(directory))
        except Exception as error:
            print(
                json.dumps(
                    {
                        "label": "public-observation-setup-failure",
                        "diagnostic": repr(error),
                    }
                ),
                flush=True,
            )
            print(
                'DES-ORACLE-OBSERVATION: {"version":1,"observed":0,"assertions_failed":0,"setup_failed":1}',
                flush=True,
            )
            return 1
        suite = unittest.TestSuite(
            unittest.FunctionTestCase(
                lambda case=case: journey.observe(case),
                description=case.name,
            )
            for case in CASES
        )
        suite.run(result)
        for test, diagnostic in (*result.failures, *result.errors):
            print(
                json.dumps(
                    {
                        "label": "failed-public-observation",
                        "case": test.shortDescription(),
                        "diagnostic": diagnostic,
                    }
                ),
                flush=True,
            )
    print(
        "DES-ORACLE-OBSERVATION: "
        + json.dumps(
            {
                "version": 1,
                "observed": result.testsRun - len(result.errors),
                "assertions_failed": len(result.failures),
                "setup_failed": len(result.errors),
            }
        ),
        flush=True,
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
