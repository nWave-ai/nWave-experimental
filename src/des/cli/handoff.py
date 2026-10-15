"""Construct architect role prompts and observe explicit handoff commands."""

from __future__ import annotations

import json
import shlex
import sys
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
from des.domain.design_document import (
    DesignDocument,
    build_fact_catalog,
    fact_references,
    normalized_wire,
    resolve_inheritance,
)
from des.ports.driven_ports.task_invocation_port import DesignFacts
from des.runtime.packaged_asset import resolve_packaged_asset


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _catalog(stored):
    designs = [item.authority for item in stored.values if item.authority is not None]
    if stored.shared_design is not None:
        designs.insert(0, stored.shared_design.design)
    if any(not isinstance(design, DesignFacts) for design in designs):
        raise ValueError(
            "DesignFactsPreNormalized: bound DESIGN cannot be consumed; "
            "use des design --replace-current --input - for the same scope"
        )
    catalog = build_fact_catalog(
        record for design in designs for record in design.facts
    )
    if isinstance(catalog, tuple):
        raise ValueError("DesignInheritanceRefused: " + "\n".join(catalog))
    return catalog


def _facts(  # noqa: PLR0913 - explicit caller scope and already-resolved native context
    stored, role, value, targets, directory, *, design=None, handoff=None, catalog=None
):
    payload = {
        "request": stored.request,
        "values": [
            {
                "observation": item.observation,
                "dependencies": list(item.dependencies),
                "design_semantic_sha256": item.design_semantic_sha256,
            }
            for index, item in enumerate(stored.values, 1)
            if value is None or index == value
        ],
        **DeliveryContinuationRunner._shared(stored),
    }
    original = json.loads(stored.raw)
    for key in ("scope", "product_authority"):
        if key in original:
            payload[key] = original[key]
    shared = None if stored.shared_design is None else stored.shared_design.design
    if shared is not None and not isinstance(shared, DesignFacts):
        raise ValueError(
            "DesignFactsPreNormalized: shared DESIGN cannot be consumed; use des design --shared --replace-current --input -"
        )
    if catalog is None and (
        value is None or stored.values[value - 1].authority is None
    ):
        catalog = _catalog(stored)
    inherits = ()
    if value is None:
        authorities = {
            str(index): normalized_wire(item.authority)
            for index, item in enumerate(stored.values, 1)
            if isinstance(item.authority, DesignFacts)
        }
        if shared is not None:
            authorities["shared"] = normalized_wire(shared)
        for authority in authorities.values():
            authority.pop("facts", None)
            authority.pop("architect_handoff", None)
        payload["selected_authority"] = authorities
        payload["inherited_records"] = {}
        payload["shared_verification"] = {}
    if value is not None and stored.values[value - 1].authority is not None:
        own = stored.values[value - 1].authority
        if not isinstance(own, DesignFacts):
            raise ValueError(
                "DesignFactsPreNormalized: value DESIGN cannot be consumed; use des design --value N --replace-current --input -"
            )
        resolved = resolve_inheritance(
            shared,
            (
                item.authority
                for index, item in enumerate(stored.values, 1)
                if index != value and isinstance(item.authority, DesignFacts)
            ),
            own,
        )
        if isinstance(resolved, tuple):
            raise ValueError("DesignInheritanceRefused: " + "\n".join(resolved))
        if catalog is None:
            catalog = resolved.catalog
        selected = (
            DeliveryContinuationRunner._typed_facts(design)
            if design is not None
            else normalized_wire(own)
        )
        selected.pop("facts", None)
        selected.pop("architect_handoff", None)
        payload["selected_authority"] = selected
        payload["inherited_records"] = normalized_wire(resolved.inherited_records)
        payload["shared_verification"] = normalized_wire(resolved.shared_verification)
        inherits = own.inherits
    payload["architect_projection"] = projection(
        role,
        accumulated(stored) if handoff is None else handoff,
        value=value,
        targets=targets,
        base_dir=directory,
        inherits=inherits,
        catalog=catalog,
    )
    roots = (
        payload.get("selected_authority", {}),
        payload.get("inherited_records", {}),
        payload.get("shared_verification", {}),
        payload["architect_projection"],
    )
    if handoff is not None:
        missing = set()
        for reference in fact_references(roots):
            try:
                catalog.resolve(reference)
            except KeyError:
                missing.add(reference.ref)
        if missing:
            raise ValueError(
                "DesignFactUnresolved: detached catalog omits "
                + ", ".join(sorted(missing))
                + "; supply digest-bound schema-2 manifest catalog locators"
            )
    payload["facts"] = catalog.reachable(*roots)
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
        ), False
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
        return load_role_instructions(asset.path), False
    if args.role == "nw-solution-architect":
        name = args.template_name or "design.architect-v9"
        fixture = {
            "des_facts": "See canonical native_input in [C] orchestrator.",
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
        authority = ["See canonical native_input.selected_authority.authority."]
        if stored.product_authority is not None:
            authority.insert(
                0, "See canonical native_input.product_authority (locator and sha256)."
            )
        if stored.shared_design is not None:
            authority.append(
                "See canonical native_input.shared_design (authority_locator and section_sha256)."
            )
        if stored.feature_id:
            feature = "See canonical native_input.scope.feature_id."
        else:
            facts["invocation"]["feature"] = "project scope"
            feature = "See canonical native_input.invocation.feature."
        fixture = {
            "feature": feature,
            "request": "See canonical native_input.request.",
            "value": str(args.value),
            "observation": "See canonical native_input.values[0].observation.",
            "authority": authority,
            "targets": [
                "See canonical native_input.selected_authority.targets"
                + (
                    ", restricted by native_input.invocation.targets."
                    if targets is not None
                    else "."
                )
            ],
            "paradigm": "See canonical native_input.selected_authority.paradigm.",
            "verification": [
                "See canonical native_input.selected_authority.verification."
            ],
            "state_lines": ["See canonical native_input in [C] orchestrator."],
            "repo_root": str(root),
            "root_input": context,
        }
        if args.role == "nw-acceptance-designer":
            name = args.template_name or "oracle.atd-v3"
            fixture.update(
                {
                    "oracle_path": "See canonical native_input.selected_authority.oracle.",
                    "supports": [
                        "See canonical native_input.selected_authority.acceptance_supports (empty means none declared)."
                    ],
                    "public_oracle": "See canonical native_input.selected_authority.public_oracle.",
                    "obligations": [
                        "See canonical native_input.selected_authority.constraints (empty means none declared)."
                    ],
                    "arch_tests": "See canonical native_input.selected_authority.architectural_tests.",
                    "contract_tests": "See canonical native_input.selected_authority.contract_tests.",
                }
            )
        else:
            facts["invocation"]["operations"] = (
                "UNASSESSED: no operational authority supplied to this prompt; root must supply any applicable operational input"
            )
            fixture["operations"] = "See canonical native_input.invocation.operations."
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
                        "move": "See canonical native_input.selected_authority.prefactoring.move.",
                        "preserved": "See canonical native_input.selected_authority.prefactoring.preserved_observation.",
                        "existing_oracle": "See canonical native_input.selected_authority.prefactoring.existing_oracle.",
                        "verification": [
                            "See canonical native_input.selected_authority.prefactoring.verification."
                        ],
                    }
                )
            else:
                name = args.template_name or "craft.impl-v3"
                fixture.update(
                    {
                        "oracle_line": "See canonical native_input.selected_authority.oracle.",
                        "supports": [
                            "See canonical native_input.selected_authority.acceptance_supports (empty means none declared)."
                        ],
                        "obligations": [
                            "See canonical native_input.selected_authority.constraints (empty means none declared)."
                        ],
                    }
                )
                fixture["implementation_mode"] = (
                    "No product changes authorized; preserve the recorded public observation "
                    "without product edits."
                    if design.product_change == "none"
                    else "The public oracle for this value is recorded and RED; make it GREEN."
                )
    used_fields = set()
    text, _ = architect_prompt.render(
        name,
        fixture,
        directory=args.template_dir,
        root=root,
        role_id=args.role,
        skills_directory=args.skills_dir,
        used_fields=used_fields,
    )
    if args.role == "nw-acceptance-designer":
        # The task template scopes the work; it does not replace the role's
        # canonical knowledge or its conditional loading instructions.
        asset = resolve_packaged_asset(f"nWave/agents/{args.role}.md", start=root)
        if not asset.is_usable:
            raise ValueError(
                f"role instructions unavailable: {asset.detail}; pass --template"
            )
        text = load_role_instructions(asset.path) + "\n\n" + text
    return text, "root_input" in used_fields


def _prompt(root, args, stored):
    if args.value is not None and not 1 <= args.value <= len(stored.values):
        raise ValueError(
            "--value must be a one-based position within the accumulated Request"
        )
    defect = DeliveryContinuationRunner.design_consumption_defect(stored, args.value)
    if defect is not None:
        raise ValueError(f"{defect.what}: {defect.why}; {defect.how}")
    handoff = None
    catalog = None
    if args.files:
        handoff, catalog, defects = operations.load_context(
            [str(root / path) for path in args.files], base_dir=args.dir
        )
        if defects:
            raise ValueError(report(defects))
        if catalog is None:
            raise ValueError(
                "WHAT: ArchitectHandoffCatalogUnavailable; WHY: FactRefs require an explicit catalog; "
                "HOW: add digest-bound catalog locators or run natively with --repo-root"
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
        if role == "reviewer" and "architect_projection" not in facts:
            facts = {**facts, "architect_projection": projection(args.role, {})}
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
                root, stored, args.value, inspect_only=True
            )
            if (
                isinstance(design, DeliveryOutcome)
                and args.role == "nw-acceptance-designer"
                and design.failure.what == "SelectedRevisionRealignmentNeeded"
            ):
                design = DeliveryContinuationRunner().selected_authority(
                    root,
                    stored,
                    args.value,
                    current_design_only=True,
                    inspect_only=True,
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
                        "WHAT: prompt targets are outside mutable production authority; "
                        f"WHY: supplied {targets!r}, authorized "
                        f"{DeliveryContinuationRunner._mutable_targets(design)!r}; "
                        "HOW: omit --targets or select only bound EXTEND/CREATE_NEW production "
                        "paths; change authority with des design --repo-root ROOT --value N --input -"
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
        facts = _facts(
            stored,
            args.role,
            args.value,
            targets,
            directory,
            design=design,
            handoff=handoff,
            catalog=catalog,
        )
        invocation = {"repo_root": str(root)}
        if args.value is not None:
            invocation["value"] = args.value
        if targets is not None:
            invocation["targets"] = list(targets)
        if args.phase is not None:
            invocation["phase"] = args.phase
        facts["invocation"] = invocation
    template, has_root = _template(
        root, args, stored, facts, context, design, targets=targets
    )
    sys.stdout.write(
        compose(
            args.role,
            {},
            template,
            root_context="" if has_root else context,
            context={"native_input": _json(facts)},
            value=args.value,
            targets=targets,
            base_dir=directory,
            prepared_projection=[],
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
            if args.dir:
                args.dir = str((root / args.dir).resolve())
            elif not args.files:
                args.dir = str(root / ".nwave/des")
        if args.cmd == "check" and args.targets is None and stored is not None:
            if all(
                isinstance(value.authority, DesignFacts) for value in stored.values
            ) and (
                stored.shared_design is None
                or isinstance(stored.shared_design.design, DesignFacts)
            ):
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
            args.catalog = _catalog(stored)
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
