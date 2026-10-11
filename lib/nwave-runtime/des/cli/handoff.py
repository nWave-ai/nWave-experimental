"""Construct architect role prompts and observe explicit handoff commands."""

from __future__ import annotations

import json
import shlex
import sys
from dataclasses import asdict
from pathlib import Path

from des.adapters.driven.task_invocation.role_instructions import load_role_instructions
from des.application import architect_prompt
from des.application.architect_handoff import (
    HandoverReceiptStore,
    accumulated,
    compose,
    projection,
)
from des.application.architect_handoff import g10 as operations
from des.application.architect_handoff.g10_defect import report
from des.application.architect_handoff.g10_project import ProjectionError
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
)
from des.application.delivery_state import read_state
from des.application.handover import Blocked, stored_handover
from des.cli.role_artifacts import load_prepared_at
from des.cli.step_terminal import StepRefusal, resolved_root
from des.domain.design_document import DesignDocument
from des.runtime.packaged_asset import resolve_packaged_asset


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _facts(stored, role, value, targets, directory):
    # Preserve every existing semantic carrier, not just the six new sections.
    payload = json.loads(stored.raw)
    payload.pop("architect_receipts", None)
    for item in payload["values"]:
        if isinstance(item["authority"], dict):
            item["authority"].pop("architect_handoff", None)
    if "shared_design" in payload:
        payload["shared_design"]["design"].pop("architect_handoff", None)
    if value is not None:
        payload["values"] = [payload["values"][value - 1]]
    payload["architect_projection"] = projection(
        role,
        accumulated(stored),
        value=value,
        targets=targets,
        base_dir=directory,
    )
    return payload


# Native snapshot, scoped facts and caller context independently supply the
# template producer; preserve their explicit invocation-bound relationship.
def _template(root, args, stored, facts, context, design, *, targets=None):  # noqa: PLR0913, PLR0917
    if args.template:
        path = Path(args.template)
        path = path if path.is_absolute() else root / path
        return (
            load_role_instructions(path)
            if path.stem == args.role
            else path.read_bytes().decode("utf-8")
        )
    if args.role in (
        "nw-product-owner",
        "nw-software-crafter-reviewer",
        "nw-user-examiner",
        "nw-acceptance-designer-reviewer",
    ):
        asset = resolve_packaged_asset(f"nWave/agents/{args.role}.md", start=root)
        if not asset.is_usable:
            raise ValueError(
                f"role instructions unavailable: {asset.detail}; pass --template"
            )
        return load_role_instructions(asset.path)
    if args.role == "nw-solution-architect":
        name = args.template_name or "design.architect-v9"
        fixture = {
            "des_facts": _json(facts),
            "grammar": DesignDocument.input_description(),
            "submit_steps": [
                shlex.join(
                    [
                        "des",
                        "design",
                        "--repo-root",
                        str(root),
                        "--shared",
                        "--input",
                        "-",
                    ]
                ),
                *[
                    shlex.join(
                        [
                            "des",
                            "design",
                            "--repo-root",
                            str(root),
                            "--value",
                            str(n),
                            "--input",
                            "-",
                        ]
                    )
                    for n in range(1, len(stored.values) + 1)
                ],
            ],
            "root_input": context,
        }
    else:
        value = stored.values[args.value - 1]
        authority = [design.locator]
        if stored.product_authority is not None:
            authority.insert(
                0,
                stored.product_authority.locator
                + " sha256="
                + stored.product_authority.sha256,
            )
        if stored.shared_design is not None:
            authority.append(
                stored.shared_design.authority_locator
                + " sha256="
                + stored.shared_design.section_sha256
            )
        fixture = {
            "feature": stored.feature_id or "project scope",
            "request": stored.request,
            "value": str(args.value),
            "observation": value.observation,
            "authority": authority,
            "targets": [
                f"{path} ({decision})"
                for path, decision in design.target_decisions
                if targets is None or path in targets
            ],
            "paradigm": design.paradigm,
            "verification": [
                shlex.join(argv) for argv in design.native_verification_argvs
            ],
            "state_lines": [_json(facts)],
            "repo_root": str(root),
            "root_input": context,
        }
        if args.role == "nw-acceptance-designer":
            name = args.template_name or "oracle.atd-v3"
            fixture.update(
                {
                    "oracle_path": design.acceptance_oracle_locator,
                    "supports": list(design.acceptance_paths[1:])
                    or ["(none declared)"],
                    "public_oracle": _json(asdict(design.public_oracle))
                    if design.public_oracle is not None
                    else "UNASSESSED: no public oracle supplied",
                    "obligations": list(design.obligations) or ["(none declared)"],
                    "arch_tests": _json(
                        DeliveryContinuationRunner._typed_facts(design)[
                            "architectural_tests"
                        ]
                    ),
                    "contract_tests": _json(
                        DeliveryContinuationRunner._typed_facts(design)[
                            "contract_tests"
                        ]
                    ),
                }
            )
        else:
            fixture["operations"] = (
                "UNASSESSED: no operational authority supplied to this prompt; root must supply any applicable operational input"
            )
            if args.phase is not None:
                name = args.template_name or "craft.prefactor-v3"
                pf = design.prefactoring
                if pf is None or pf.applicability != "applicable":
                    raise ValueError(
                        "prefactoring is not applicable; choose an explicitly bound phase"
                    )
                fixture.update(
                    {
                        "phase": args.phase,
                        "move": pf.move,
                        "preserved": pf.preserved_observation,
                        "existing_oracle": pf.existing_oracle,
                        "verification": [shlex.join(argv) for argv in pf.verification],
                    }
                )
            else:
                name = args.template_name or "craft.impl-v3"
                fixture.update(
                    {
                        "oracle_line": design.acceptance_oracle_locator,
                        "supports": list(design.acceptance_paths[1:])
                        or ["(none declared)"],
                        "obligations": list(design.obligations) or ["(none declared)"],
                    }
                )
    text, _ = architect_prompt.render(
        name,
        fixture,
        directory=args.template_dir,
        root=root,
        role_id=args.role,
        skills_directory=args.skills_dir,
    )
    return text


def _prompt(root, args, stored):
    if args.files:
        raise ValueError(
            "native prompts consume accumulated handover, not detached FILE input"
        )
    context_path = Path(args.root_context)
    context = (
        (context_path if context_path.is_absolute() else root / context_path)
        .read_bytes()
        .decode("utf-8")
    )
    if not context.strip():
        raise ValueError("root context is blank; provide the actual caller context")
    directory = args.dir
    targets = tuple(operations._targets(args)) if args.targets is not None else None
    design = None
    prepared_projection = None
    if args.value is not None and not 1 <= args.value <= len(stored.values):
        raise ValueError(
            "--value must be a one-based position within the accumulated Request"
        )
    if args.role in ("nw-software-crafter-reviewer", "nw-user-examiner"):
        if not args.candidate or not args.role_input:
            raise ValueError(
                "reviewer/examiner prompts require --candidate and --role-input from des prepare-role"
            )
        if args.value is not None:
            raise ValueError(
                "candidate review and examination consume the whole sealed input, not a value subset"
            )
        role = "examiner" if args.role == "nw-user-examiner" else "reviewer"
        _, facts, _ = load_prepared_at(
            root, role, args.candidate, Path(args.role_input)
        )
        handoff = {}
        prepared_projection = (
            []
            if role == "examiner"
            else facts.get("architect_projection", projection(args.role, {}))
        )
    else:
        if args.role not in ("nw-solution-architect", "nw-product-owner"):
            if args.value is None or not 1 <= args.value <= len(stored.values):
                raise ValueError(
                    "this role requires --value within the accumulated Request"
                )
            if stored.values[args.value - 1].authority is None:
                raise ValueError(
                    "the selected value has no bound DESIGN; construct it with des design"
                )
            design = DeliveryContinuationRunner().selected_authority(
                root, stored, args.value
            )
            if isinstance(design, DeliveryOutcome):
                raise ValueError(
                    f"{design.failure.what}: {design.failure.why}; {design.failure.how}"
                )
            if args.role in ("nw-software-crafter", "nw-functional-software-crafter"):
                expected = (
                    "nw-functional-software-crafter"
                    if design.paradigm == "functional"
                    else "nw-software-crafter"
                )
                if args.role != expected:
                    raise ValueError(
                        f"bound paradigm {design.paradigm} requires {expected}; use that published role"
                    )
                if targets is None:
                    targets = DeliveryContinuationRunner._mutable_targets(design)
                if not set(targets) <= set(
                    DeliveryContinuationRunner._mutable_targets(design)
                ):
                    raise ValueError(
                        "prompt targets must be mutable production targets of the bound DESIGN"
                    )
                if args.phase is None:
                    # craft.impl-v3 tells the crafter its public oracle is
                    # recorded and RED; say it only when the graph holds it.
                    state = read_state(root)
                    if isinstance(state, Blocked):
                        raise ValueError(f"{state.what}: {state.why}; {state.how}")
                    oracle = state.values[args.value - 1].oracle
                    if not state.values[args.value - 1].oracle_recorded:
                        raise ValueError(
                            f"the public oracle of value {args.value} is {oracle}, not recorded, "
                            "and the implementation prompt tells the crafter it is recorded and RED; "
                            f"record it with des oracle --repo-root {root} --value {args.value} --input -, "
                            "then repeat this prompt"
                        )
        handoff = accumulated(stored)
        facts = _facts(stored, args.role, args.value, targets, directory)
    template = _template(root, args, stored, facts, context, design, targets=targets)
    # The measured template contains the root bytes verbatim; untemplated role
    # instructions receive them through the final caller-owned context block.
    has_root = not args.template and args.role not in (
        "nw-product-owner",
        "nw-software-crafter-reviewer",
        "nw-user-examiner",
        "nw-acceptance-designer-reviewer",
    )
    sys.stdout.write(
        compose(
            args.role,
            handoff,
            template,
            root_context="" if has_root else context,
            context={"native_input": _json(facts)},
            value=args.value,
            targets=targets,
            base_dir=directory,
            prepared_projection=prepared_projection,
        )
    )
    return 0


def main(argv=None):
    parser = operations.build_parser(native=True)
    operations.configure_streams()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.cmd in ("describe", "rules"):
        return args.fn(args)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        print(f"WHAT: {root.what}\nWHY: {root.why}\nHOW: {root.how}", file=sys.stderr)
        return 2
    try:
        detached_inspection = args.cmd in ("check", "summary", "render") and bool(
            args.files
        )
        stored = stored_handover(root)
        if isinstance(stored, Blocked):
            raise ValueError(f"{stored.what}: {stored.why}; {stored.how}")
        if stored is None and not detached_inspection:
            raise ValueError(
                "no accumulated handover; construct product facts with des po and DESIGN with des design --input -"
            )
        if args.cmd == "run":
            args.version_command = (
                shlex.split(args.version_argv) if args.version_argv else None
            )
            if args.cwd:
                args.cwd = str((root / args.cwd).resolve())
        if args.cmd == "render" and args.html:
            args.html = str(root / args.html)
        if hasattr(args, "dir"):
            args.dir = (
                str((root / args.dir).resolve())
                if args.dir
                else str(root / ".nwave/des")
            )
        if args.cmd == "check" and args.targets is None and stored is not None:
            from des.ports.driven_ports.task_invocation_port import DesignFacts

            if all(isinstance(value.authority, DesignFacts) for value in stored.values):
                designs = [value.authority for value in stored.values]
                if stored.shared_design is not None:
                    designs.insert(0, stored.shared_design.design)
                args.targets = ",".join(
                    dict.fromkeys(
                        target.path for design in designs for target in design.targets
                    )
                )
        if args.cmd == "prompt":
            for field in ("template_dir", "skills_dir"):
                supplied = getattr(args, field)
                if supplied is not None:
                    setattr(args, field, str(root / supplied))
            return _prompt(root, args, stored)
        if args.cmd in ("run", "record"):
            args.receipt_store = HandoverReceiptStore(root, stored)
        elif not args.files:
            args.handoff = accumulated(stored)
        else:
            args.files = [str(root / path) for path in args.files]
        return args.fn(args)
    except ProjectionError as error:
        print(report([error.defect]), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, architect_prompt.PromptError) as error:
        print(
            f"WHAT: handoff operation cannot complete: {error}\nWHY: required typed input or bound evidence is unavailable or inconsistent.\nHOW: supply the named input through des design, des prepare-role, or an explicit path and repeat this operation.",
            file=sys.stderr,
        )
        return 1
