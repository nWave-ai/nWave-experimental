"""Bounded native Claude PO replay, real DES constructor and branded HTML."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from des.adapters.driven.task_invocation.role_instructions import load_role_instructions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument(
        "--feature",
        "--case",
        dest="feature",
        choices=["new-ui", "existing-ui", "no-ui", "quint-open-timing"],
        help="case id to run (default: all)",
    )
    parser.add_argument(
        "--role-spec",
        type=Path,
        help="clean INSTALLED nw-product-owner.md (default: source role)",
    )
    parser.add_argument(
        "--des-python",
        type=Path,
        help="clean wheel-venv interpreter for des CLI/renderer (installed mode)",
    )
    args = parser.parse_args()
    framework = Path(__file__).resolve().parents[3]
    destination = args.output_root.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    cases = json.loads(Path(__file__).with_name("cases.json").read_text())
    installed = args.des_python is not None
    role_path = (
        args.role_spec.resolve()
        if args.role_spec
        else framework / "nWave/agents/nw-product-owner.md"
    )
    instructions = load_role_instructions(role_path)
    instructions_path = destination / "role-instructions.txt"
    instructions_path.write_text(instructions)
    if installed:
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        des_python = str(args.des_python.absolute())
    else:
        env = dict(os.environ, PYTHONPATH=str(framework / "src"))
        des_python = sys.executable
    skills = re.findall(r"PRELOADED SKILL START: (\S+?);", instructions)
    role_reference = (
        "You are nw-product-owner. Your complete role instructions and preloaded "
        "skills are in the appended system prompt; follow them."
    )
    agents = {
        "nw-product-owner": {
            "description": "Product owner for DISCUSS",
            "prompt": role_reference,
            "tools": ["Read", "StructuredOutput"],
        }
    }
    results = []
    for case in cases:
        if args.feature and args.feature != case["id"]:
            continue
        lane = destination / case["id"]
        lane.mkdir()
        repo = lane / "repository"
        repo.mkdir()
        for command in [
            ["git", "init", "-q"],
            [
                "git",
                "-c",
                "user.name=PO Eval",
                "-c",
                "user.email=eval@localhost",
                "commit",
                "--allow-empty",
                "-qm",
                "eval baseline",
            ],
        ]:
            subprocess.run(command, cwd=repo, check=True, capture_output=True)
        contract = {
            "schema_version": 2,
            "request": case["request"],
            "outcomes": [
                "actor and explicitly requested observable result; motivation only if recorded"
            ],
            "scope": {
                "in_scope": ["journey and relevant states"],
                "out_of_scope": {
                    "applicability": "not_applicable",
                    "reason": "meaningful reason",
                    "items": [],
                },
            },
            "decisions": [
                "confirmed choices, proposals and open questions explicitly distinguished"
            ],
            "values": [
                {"observation": "visible feedback increment", "dependencies": []}
            ],
            "jtbd": {"status": "not_explored"},
            "journey": {"status": "not_explored"},
            "gherkin": {"status": "not_explored"},
            "quint_scenarios": {"status": "not_run"},
        }
        prompt = (
            "Host-led DISCUSS replay, not a live interview. The following are recorded human answers; "
            "do not invent other feedback or claim a prototype or formal tool was run. "
            "Return the exact closed DISCUSS v2 manifest (see `des discuss --describe-input`) as the structured result. Preserve the Request verbatim. "
            "jtbd, journey, gherkin may be {status: not_explored} unless recorded answers support them; "
            "quint_scenarios must be {status: not_run}. Never invent emotions or Quint output. "
            "Use only the given facts. Keep unresolved decisions open in decisions. "
            "dependencies must name earlier observation strings. out_of_scope.items is nonempty exactly when applicable. "
            "Template (replace explanatory values):\n"
            + json.dumps(contract)
            + "\nCase:\n"
            + json.dumps(case)
        )
        (lane / "prompt.txt").write_text(prompt)
        # Minimal transport envelope: the real constructor is the schema authority.
        schema = {
            "type": "object",
            "properties": {
                k: {"type": v}
                for k, v in {
                    "schema_version": "integer",
                    "request": "string",
                    "outcomes": "array",
                    "scope": "object",
                    "decisions": "array",
                    "values": "array",
                    "jtbd": "object",
                    "journey": "object",
                    "gherkin": "object",
                    "quint_scenarios": "object",
                }.items()
            },
            "required": list(contract),
            "additionalProperties": False,
        }
        argv = [
            "claude",
            "-p",
            "--model",
            args.model,
            "--effort",
            "low",
            "--output-format",
            "json",
            "--tools",
            "Read,StructuredOutput",
            "--allowedTools",
            "Read,StructuredOutput",
            "--setting-sources",
            "user",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-chrome",
            "--no-session-persistence",
            "--max-budget-usd",
            "1",
            "--agent",
            "nw-product-owner",
            "--agents",
            json.dumps(agents),
            "--append-system-prompt-file",
            str(instructions_path),
            "--json-schema",
            json.dumps(schema),
        ]
        (lane / "argv.json").write_text(json.dumps(argv, indent=2))
        started = time.monotonic()
        result = {
            "case": case["id"],
            "model": args.model,
            "mode": "installed" if installed else "source",
            "role_path": str(role_path),
            "role_file_sha256": hashlib.sha256(role_path.read_bytes()).hexdigest(),
            "preloaded_skills": skills,
            "des_python": des_python,
            "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
            "human_comprehension": "INDETERMINATE",
            "semantic_review": "PENDING",
            "conditional_skill_reads": "UNMEASURED",
        }
        try:
            native = subprocess.run(
                argv,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=repo,
                timeout=180,
            )
            (lane / "native.stdout.json").write_text(native.stdout)
            (lane / "native.stderr.txt").write_text(native.stderr)
            result["provider_seconds"] = time.monotonic() - started
            result["provider_exit"] = native.returncode
            envelope = json.loads(native.stdout)
            result["accounting"] = {
                k: envelope.get(k)
                for k in [
                    "total_cost_usd",
                    "usage",
                    "modelUsage",
                    "session_id",
                    "duration_ms",
                ]
            }
            manifest = envelope.get("structured_output")
            if (
                native.returncode
                or envelope.get("is_error")
                or not isinstance(manifest, dict)
            ):
                raise ValueError(
                    "native provider did not produce a successful structured manifest"
                )
            raw = json.dumps(manifest, ensure_ascii=False)
            (lane / "manifest.json").write_text(raw + "\n")
            result["exact_request"] = manifest.get("request") == case["request"]
            if not result["exact_request"]:
                raise ValueError("PO changed the original Request")
            command = [
                des_python,
                "-m",
                "des.cli",
                "discuss",
                "--feature",
                case["id"],
                "--repo-root",
                str(repo),
                "--input",
                "-",
            ]
            result["constructor_argv"] = command
            constructed = subprocess.run(
                command,
                input=raw,
                text=True,
                capture_output=True,
                cwd=repo if installed else framework,
                env=env,
                timeout=30,
            )
            (lane / "constructor.txt").write_text(
                constructed.stdout + constructed.stderr
            )
            result["constructor_exit"] = constructed.returncode
            documents = [
                line.removeprefix("DOCUMENT: ")
                for line in constructed.stdout.splitlines()
                if line.startswith("DOCUMENT: ")
            ]
            if constructed.returncode or len(documents) != 1:
                raise ValueError(
                    "DISCUSS did not construct exactly one declared document; inspect constructor.txt"
                )
            source = repo / documents[0]
            view = lane / "discuss.html"
            rendered = subprocess.run(
                [
                    des_python,
                    "-m",
                    "des.adapters.driven.rendering.nwave_document",
                    str(source),
                    "--out",
                    str(view),
                ],
                capture_output=True,
                text=True,
                cwd=repo if installed else framework,
                env=env,
                timeout=30,
            )
            (lane / "renderer.txt").write_text(rendered.stdout + rendered.stderr)
            result["renderer_exit"] = rendered.returncode
            result["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            result["branded_html"] = (
                view.is_file() and 'name="nwave-brand"' in view.read_text()
            )
            result["mechanical_pass"] = (
                rendered.returncode == 0 and result["branded_html"]
            )
        except (subprocess.TimeoutExpired, ValueError, OSError) as error:
            result["error"] = str(error)
            result["mechanical_pass"] = False
        result["outer_seconds"] = time.monotonic() - started
        results.append(result)
        (destination / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    return int(not all(r["mechanical_pass"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
