"""prompt(role) = template WHAT (+ what the grammar derives) ⊕ projection(handoff, role) ⊕ orchestrator context.

Deterministic: the same (handoff, role, value, targets, files, template, context) gives the same bytes.
"All and only": a role receives every section it consumes (completeness) and nothing it does not
(locality); a consumed-but-absent section arrives as an explicit UNASSESSED marker, never as
silence. The examiner consumes no design section by construction (source-blind).

Each consumer row carries its BASIS, which starts with its class (counted by `consumers_markdown`): [direct] a quoted line of the
repository says the role uses that kind of fact for that decision; [inferred] a line plus ONE named inference step; [hypothesis] no
line, a hypothesis. Only a measured ablation can turn an inference or hypothesis into a fact.
Native DESIGN transports these sections alongside its other semantic decisions; the classes
record whether the ROLE needs that KIND of fact, not evidence that its architectural claims hold."""

from __future__ import annotations

import dataclasses as dc
import json
import re
import typing as t

from . import g10_render as R
from . import g10_rules as RU
from . import g10_scope as S
from . import g10_types as T
from .g10_codec import canon, canonical, enc, is_union, sha
from .g10_defect import Defect


if t.TYPE_CHECKING:
    from des.domain.design_document import FactCatalog


ROLES = (
    "architect",
    "product_owner",
    "atd",
    "atd_reviewer",
    "software_crafter",
    "functional_crafter",
    "reviewer",
    "examiner",
    "human",
)

# role -> kind -> (view, the decision the role takes with it, basis).
# software_crafter serves object_oriented AND procedural paradigms (nw-software-crafter.md); the functional
# crafter serves the functional paradigm. The DATA each receives is the same; the template (the WHAT) differs,
# and DES picks the role by the bound paradigm (src/des/application/delivery_steps.py:1276-1281).
_ATD = {
    "laws": (
        "full",
        "write one generative property per broad law (its generator, independent observation and falsifier) and native example tables for finite laws",
        "[direct] nw-property-based-testing/SKILL.md:9-10 (declared broad laws -> properties); nw-distill-prior-wave-reading/SKILL.md:14-16 'cross-layer laws'; "
        "nw-tdd-methodology-paradigm/SKILL.md:21-22 (broad law -> property, finite -> examples)",
    ),
    "construction": (
        "full",
        "for each claim the oracle observes the refused outcome with its reason and the accepted outcome; the unknown states are residue the design states",
        "[inferred] nw-at-completeness-check/SKILL.md:100 'the promised outcome and every materially distinguishable result' + one step: a claim's refused "
        "and accepted outcomes are distinguishable results; nw-distill-prior-wave-reading/SKILL.md:16 'residual stress decisions'",
    ),
    "model": (
        "falsifiers",
        "bind each public observation of the oracle to a runtime symbol through the atoms; treat the mutants as the falsifiers the oracle must catch; "
        "stay inside the stated assumptions",
        "[hypothesis] no ATD text names the model; nw-design/SKILL.md:414-416 is the architect's rule",
    ),
    "closure": (
        "axes",
        "OBSERVED is true today; DESIGNED_NOT_BUILT is a declared capability not deployed yet: write the RED oracle against the declared contract",
        "[inferred] nw-acceptance-designer.md:39 (a capability not yet deployed is written as a RED oracle), :43-44 (preserve satisfied obligations, no fabricated RED) "
        "+ one step: DESIGNED_NOT_BUILT means declared and not deployed",
    ),
}
# the ATD reviewer receives the same facts as the ATD (nw-acceptance-designer-reviewer.md:40-41) and JUDGES the oracle with them
_ATD_REVIEWER = {
    "laws": (
        "full",
        "verify that the oracle observes each declared law, with generative properties for broad laws and examples only for finite ones",
        "[direct] nw-at-completeness-check/SKILL.md:101-102 'declared state, composition and preservation laws, using PBT for broad domains'; "
        "nw-acceptance-designer-reviewer.md:41 (same facts as ATD)",
    ),
    "construction": (
        "full",
        "verify that every claim has a constructible stimulus -> expected observation -> falsifier chain through the declared public port",
        "[inferred] nw-acceptance-designer-reviewer.md:50-52 'Require every obligation to have a constructible stimulus -> expected observation -> falsifier chain' "
        "+ one step: a construction claim is an obligation",
    ),
    "model": (
        "falsifiers",
        "check that the mutants the design lists are falsifiers the oracle can catch",
        "[hypothesis] no text of the ATD reviewer names the model; it reads no additional candidate evidence (nw-acceptance-designer-reviewer.md:42)",
    ),
    "closure": (
        "axes",
        "a DESIGNED_NOT_BUILT claim is never a reason to reject; OBSERVED is true today",
        "[inferred] nw-acceptance-designer-reviewer.md:53-54 'missing production behaviour alone must never cause rejection' + one step: DESIGNED_NOT_BUILT is missing production behaviour",
    ),
}
CONSUMERS: dict[str, dict[str, tuple[str, str, str]]] = {
    "architect": dict.fromkeys(
        T.KINDS,
        (
            "full",
            "author this section; the rules are checked when you submit",
            "the producer",
        ),
    ),
    "atd": _ATD,
    "atd_reviewer": _ATD_REVIEWER,
    "software_crafter": {
        "laws": (
            "owned",
            "each law owned by one of your declared mutable targets becomes an invariant or contract of that owner, observable through the public port; "
            "the design authority is immutable: a change of a law or of its owner returns to DESIGN",
            "[inferred] nw-software-crafter.md:46 'follow decisions and obligations', :26-27 'preserve the immutable oracle and design authority', :51 'an implementation "
            "owner/name change returns to DESIGN' + one step: a declared law is a design decision",
        ),
        "construction": (
            "owned",
            "place each proposition at its owner; refuse the invalid state with its reason at the constructor; keep every named bypass route checked at its boundary",
            "[direct] nw-software-crafter.md:54-56 'for each rule the batch enforces about data or calls, apply nw-certainty-by-construction and nw-type-level-design'; "
            "nw-certainty-by-construction/SKILL.md:105-106 (name the bypass routes and keep their checks visible)",
        ),
        "model": (
            "interface",
            "keep the atom-to-symbol map true: do not rename, move or remove a mapped symbol",
            "[inferred] nw-software-crafter.md:51 'an implementation owner/name change returns to DESIGN for reconciliation' + one step: mapped symbols are the owners and "
            "names the design records (nw-design/SKILL.md:414-416); weak: no text makes the crafter read a model section",
        ),
    },
    "functional_crafter": {
        "laws": (
            "owned",
            "preserve every law owned by your declared mutable targets; use the algebra catalogue only to implement or judge preservation of a declared law, "
            "never to derive a new one",
            "[direct] nw-fp-algebra-driven-design/SKILL.md:11-13; nw-functional-software-crafter.md:23",
        ),
        "construction": (
            "owned",
            "encode each proposition at the stated strength; keep the bypass routes visible",
            "[direct] nw-functional-software-crafter.md:44-46 (the same rule as the OO crafter)",
        ),
        "model": (
            "interface",
            "keep the atom-to-symbol map true: do not rename, move or remove a mapped symbol",
            "[inferred] nw-functional-software-crafter.md:43 'Owner/name deviations return to the same DESIGN authority for reconciliation' + one step (as for the OO crafter); weak",
        ),
    },
    "reviewer": {
        "laws": (
            "full",
            "judge preservation of each law in the diff and the evidence behind it",
            "[direct] nw-software-crafter-reviewer.md:22 'judging whether an implementation preserves its declared algebraic operations and laws'; "
            "nw-fp-algebra-driven-design/SKILL.md:11-13",
        ),
        "construction": (
            "full",
            "judge each claim at its stated strength and bypass routes",
            "[inferred] nw-software-crafter-reviewer.md:13-14 preloads nw-certainty-by-construction and nw-type-level-design; nw-typesafe-system-one/SKILL.md:126 "
            "'invariant ownership; type precision' + one step: a construction claim states strength and bypass routes",
        ),
        "model": (
            "interface",
            "judge that the mapped symbols still exist and mean what the atoms say",
            "[inferred] nw-software-crafter-reviewer.md:35-36 (judge the whole-Request diff against the consumed design) + two steps: the design records the atom-to-symbol map "
            "(nw-design/SKILL.md:414-416), and a diff can break it; the weakest row",
        ),
        "closure": (
            "axes",
            "judge the runtime claims against the implementation you are given",
            "[inferred] nw-typesafe-system-one/SKILL.md:131-132 'DESIGNED_NOT_BUILT is not OBSERVED' (the reviewer preloads it) + one step: the reviewer decides which runtime "
            "claims the candidate now makes true",
        ),
    },
    "examiner": {},  # source-blind: no design section, by construction (nw-user-examiner.md:21-25; role_artifacts.py:220-262 give it criteria, public oracle and witness only)
    "product_owner": {
        "scenarios": (
            "rendered",
            "facilitate human judgment of trace-derived scenarios; request host execution when exploration is needed; silence is not approval",
            "[inferred] nw-product-owner.md:30-32 (return execution requests to the host), :41-44 (human scenario collaboration), "
            ":89-91 (real output and trace-derived text); one step: that collaboration consumes the rendered scenario view, "
            "but the role text does not explicitly name this typed section as an input",
        ),
        "closure": (
            "readable",
            "clarify the product outcome against declared guarantees, assumptions and unknowns; never infer human approval or proof",
            "[inferred] nw-product-owner.md:26-32,53-56,58-65 (clarify product outcomes; classify promises through public observations); "
            "one step: readable closure supplies the declared guarantees, assumptions and unknowns for that classification, "
            "but the role text does not explicitly name this typed section as an input",
        ),
    },
    "human": {
        "scenarios": (
            "rendered",
            "read each scenario and judge it: correct, incorrect, depends, unclear or correction. The scenario view is a join: it also carries the id, tool "
            "and command of the run it was read from, and what the mutant does",
            "[direct] nw-po-scenario-exploration/SKILL.md:24, 66-67 (the judgments); nw-solution-architect.md:29 (the architect presents model-generated scenarios "
            "for human review); the owner of the flow is Ale's decision of 2026-10-07 (not repository text)",
        ),
        "closure": (
            "readable",
            "read what is established, what is only designed, and what rests on which assumption",
            "[inferred] nw-design/SKILL.md:173-175 (human projection: examples/counterexamples, laws, guarantee ceiling and exclusions in ordinary language) "
            "+ one step: the runtime axis is the guarantee ceiling",
        ),
    },
}
_BASIS_CLASS = re.compile(r"\[(direct|inferred|hypothesis)\]")


def basis_class(basis: str) -> str:
    m = _BASIS_CLASS.match(basis)
    if m is None:
        raise ValueError(
            f"a consumer basis starts with [direct], [inferred] or [hypothesis]: {basis[:60]!r}"
        )
    return m.group(1)


def consumers_markdown() -> str:
    """The consumer table with the class of each row and the count per class (the architect, the producer, has no row)."""
    rows = [
        (role, kind, view, basis_class(b), d, b)
        for role, kinds in CONSUMERS.items()
        if role != "architect"
        for kind, (view, d, b) in kinds.items()
    ]
    counts = {
        c: sum(1 for r in rows if r[3] == c)
        for c in ("direct", "inferred", "hypothesis")
    }
    lines = [
        "| role | section | view | basis class | decision | basis |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {role} | {kind} | {view} | {cls} | {d} | {b} |"
        for role, kind, view, cls, d, b in rows
    ]
    lines += [
        "",
        f"rows: {len(rows)}; direct: {counts['direct']}; inferred: {counts['inferred']}; hypothesis: {counts['hypothesis']}",
    ]
    return "\n".join(lines)


class ProjectionError(Exception):
    def __init__(self, defect: Defect):
        super().__init__(defect.what)
        self.defect = defect


# --------------------------------------------------------------------------- views
def _owned(items: tuple, targets: t.Collection[str], keys: tuple[str, ...]) -> tuple:
    return tuple(
        x for x in items if any(T.locator_path(getattr(x, k)) in targets for k in keys)
    )


def _by(items: t.Iterable, key: t.Callable) -> list:
    """Sort by `key`; ties are broken by the canonical bytes of the item, and an identical repeat is dropped: set order and repeats never reach a prompt."""
    seen: set[str] = set()
    out = []
    for x in sorted(items, key=lambda x: (key(x), canon(x))):
        c = canon(x)
        if c not in seen:
            seen.add(c)
            out.append(x)
    return out


_ATOM_KEEP = {
    "interface": {
        "state": ("name", "symbol", "site", "tag"),
        "action": ("name", "symbol", "site", "atomicity", "tag"),
        "property": ("name", "symbol", "site", "tag"),
        "constant": ("name", "symbol", "site", "tag"),
    },
}
_ATOM_KEEP["falsifiers"] = _ATOM_KEEP["interface"]


def _closure_view(payload: T.ClosureSet, view: str) -> dict:
    out = []
    for c in payload.closures:
        row: dict[str, t.Any] = {"subject": enc(c.subject)}
        for cname in ("safety", "inhabitation", "public_reachability", "liveness"):
            e = getattr(c, cname)
            if isinstance(e, T.Claim):
                d: dict[str, t.Any] = {
                    "statement": enc(e.statement),
                    "design": e.design,
                    "runtime": e.runtime,
                }
                for k in ("design_note", "runtime_note"):
                    if getattr(e, k):
                        d[k] = enc(getattr(e, k))
                if view == "readable":
                    d["rests_on"] = e.basis.tag + (
                        f", proof {e.basis.proof}"
                        if isinstance(e.basis, T.Checked)
                        else ""
                    )
                    if isinstance(e.basis, T.Checked) and e.basis.proof_note:
                        d["proof_note"] = enc(e.basis.proof_note)
                    if e.assumptions:
                        d["assumptions"] = enc(e.assumptions)
                row[cname] = d
            else:
                row[cname] = enc(e)
        out.append(row)
    return {"closures": _by(out, lambda r: canon(r["subject"]))}


def view_payload(
    kind: str,
    payload: t.Any,
    view: str,
    targets: t.Collection[str] | None = None,
    *,
    dependency_uses: t.Collection[str] = (),
) -> t.Any:
    if view == "owned" and targets is None:
        raise ProjectionError(
            Defect(
                "P1",
                kind,
                "this role's view keeps only what its declared targets own, and no targets were given",
                "without the targets the view would silently be the whole section, and 'only what it needs' would be false",
                "pass the declared mutable targets of the value (--targets path1,path2)",
            )
        )
    if kind == "laws" and view == "owned":
        # the crafter keeps the laws its targets own: statement, kind, layer, owner and the vocabulary they use.
        # How a law is TESTED (treatment, generators, evidence) and what was refuted belong to the oracle author.
        mine = _owned(payload.laws, targets, ("owner",))
        used = {u for lw in mine for u in lw.uses} | set(dependency_uses)
        shared_equality_used = bool(
            set(dependency_uses)
            & {observation.id for observation in payload.observations}
        )
        if shared_equality_used:
            used.update(payload.equality.under)
        obs = tuple(o for o in payload.observations if o.id in used)
        d = enc(
            dc.replace(
                payload,
                laws=mine,
                generators=(),
                refuted=(),
                observations=obs,
                constructors=tuple(c for c in payload.constructors if c.id in used),
            )
        )
        d.pop("generators")
        d.pop("refuted")
        for lw in d["laws"]:
            lw.pop("treatment")
            lw.pop("evidence")
        if not mine and not shared_equality_used:
            d.pop("equality")
        else:
            shown = {o.id for o in obs}
            d["equality"]["under"] = [
                u for u in d["equality"]["under"] if u in shown
            ]  # no dangling reference
        return d
    if kind == "construction" and view == "owned":
        # a claim concerns the file that owns it, the file that constructs the value, and the file that consumes it
        mine = _owned(payload.claims, targets, ("owner", "constructor", "consumer"))
        d = enc(dc.replace(payload, claims=mine, unknown=()))
        d.pop(
            "unknown"
        )  # the residue and its owners are a design matter, not a placement decision
        if not mine:  # admitted and excluded have no owner: they are read through a claim; with none owned there is nothing to read them for
            d.pop("admitted")
            d.pop("excluded")
        return d
    if kind == "model" and view in ("interface", "falsifiers"):
        keep = _ATOM_KEEP[view]
        ms = []
        for m in _by(payload.models, lambda x: x.id):
            atoms = [
                {k: v for k, v in a.items() if k in keep[a["tag"]]}
                for a in enc(m.atoms)
            ]
            d = {
                "id": m.id,
                "language": m.language,
                "path": m.path,
                "sha256": m.sha256,
                "atoms": atoms,
            }
            if view == "falsifiers":
                d["assumptions"] = enc(m.assumptions)
                d["exclusions"] = enc(m.exclusions)
                d["mutants"] = _by(
                    (
                        {
                            "id": mu.id,
                            "description": enc(mu.description),
                            "kills": sorted({k.property for k in mu.kills}),
                        }
                        for mu in m.mutants
                    ),
                    lambda x: x["id"],
                )
            ms.append(d)
        return {"models": ms}
    if kind == "closure" and view in ("axes", "readable"):
        return _closure_view(payload, view)
    return enc(payload)


def _rendered_scenarios(
    h: T.Handoff, scope: str, payload: T.Scenarios, base_dir: str | None, catalog=None
) -> dict:
    v = S.visible(h, scope)
    out = []
    for sc in _by(payload.scenarios, lambda x: x.id):
        r = R.render_scenario(v, sc, base_dir, catalog)
        row: dict[str, t.Any] = {
            "id": sc.id,
            "title": enc(sc.title),
            "kind": sc.kind,
            "review": enc(sc.review),
        }
        if isinstance(r, R.Rendered):
            row.update(
                {
                    "run": r.run.id,
                    "model_identity": r.model.sha256,
                    "trace_identity": r.trace_sha256,
                    "tool": {
                        "name": r.run.tool,
                        "version": r.run.tool_version,
                        "command": " ".join(r.run.argv),
                    },
                    "events": [x for _, x in r.events],
                }
            )
            if r.scenario.kind == "mutant":
                mid = r.run.variant.removeprefix("mutant:")
                description = R.mutant_description(v.models[r.model.id], mid)
                if description is not None:
                    row["what_the_bug_does"] = enc(description)
        else:
            row["NOT_RENDERED"] = (
                r.reason if isinstance(r, R.Skipped) else "; ".join(r.problems)
            )
        out.append(row)
    return {"scenarios": out}


def selected_handoff(
    h: T.Handoff, value: int, inherits: t.Iterable[T.FactRef]
) -> T.Handoff:
    selected = {ref.ref for ref in inherits}
    out = {
        key: entry
        for key, entry in h.items()
        if key[1] == f"value:{value}" and key[0] != "receipts"
    }
    for (kind, scope), entry in h.items():
        if scope != "shared" or not isinstance(entry.status, T.Applicable):
            continue
        payload = entry.status.payload
        if kind == "laws":
            laws = tuple(law for law in payload.laws if law.id in selected)
            refuted = tuple(law for law in payload.refuted if law.id in selected)
            vocabulary = {
                item.id for item in (*payload.observations, *payload.constructors)
            } & selected
            selected_generators = {
                generator.id for generator in payload.generators
            } & selected
            if not laws and not refuted and not vocabulary and not selected_generators:
                continue
            used = vocabulary | {identifier for law in laws for identifier in law.uses}
            own = out.get(("laws", f"value:{value}"))
            own_uses = (
                {
                    identifier
                    for law in own.status.payload.laws
                    for identifier in law.uses
                }
                if own and isinstance(own.status, T.Applicable)
                else set()
            )
            if laws or own_uses & vocabulary & {
                observation.id for observation in payload.observations
            }:
                used.update(payload.equality.under)
            generators = selected_generators | {
                law.treatment.generator
                for law in laws
                if isinstance(law.treatment, T.Broad)
            }
            payload = dc.replace(
                payload,
                laws=laws,
                refuted=refuted,
                observations=tuple(
                    item for item in payload.observations if item.id in used
                ),
                constructors=tuple(
                    item for item in payload.constructors if item.id in used
                ),
                generators=tuple(
                    item for item in payload.generators if item.id in generators
                ),
            )
        elif kind == "construction":
            claims = tuple(claim for claim in payload.claims if claim.id in selected)
            if not claims:
                continue
            payload = dc.replace(payload, claims=claims)
        elif kind == "model":
            models = tuple(model for model in payload.models if model.id in selected)
            if not models:
                continue
            payload = dc.replace(payload, models=models)
        elif kind == "closure":
            own = h.get(("closure", f"value:{value}"))
            subjects = (
                {
                    closure.subject.ref
                    for closure in own.status.payload.closures
                    if isinstance(closure.liveness, T.Inherited)
                }
                if own and isinstance(own.status, T.Applicable)
                else set()
            )
            closures = tuple(
                closure
                for closure in payload.closures
                if closure.subject.ref in selected | subjects
            )
            if not closures:
                continue
            payload = dc.replace(payload, closures=closures)
        else:
            continue
        out[(kind, scope)] = dc.replace(entry, status=T.Applicable(payload=payload))
    return out


def project(  # noqa: PLR0913 - preserve public scope axes and explicit catalog ownership
    h: T.Handoff,
    role: str,
    value: int | None = None,
    targets: t.Collection[str] | None = None,
    base_dir: str | None = None,
    *,
    catalog: FactCatalog | None = None,
    inherits: t.Iterable[T.FactRef] = (),
) -> list[tuple]:
    """[(kind, scope, sha_of_what_is_shown, view, content)] in a fixed order. `value` keeps shared + that value only."""
    h = {key: canonical(entry) for key, entry in h.items()}
    need = CONSUMERS[role]
    if value is not None:
        evidence = {key: entry for key, entry in h.items() if key[0] == "receipts"}
        h = selected_handoff(h, value, inherits)
        h.update(evidence)
    out = []
    for (kind, scope), e in sorted(h.items()):
        if kind not in need or (
            value is not None and scope not in ("shared", f"value:{value}")
        ):
            continue
        view = need[kind][0]
        if isinstance(e.status, T.NotApplicable):
            content: t.Any = {"not_applicable": enc(e.status.reason)}
        elif view == "rendered":
            content = _rendered_scenarios(h, scope, e.status.payload, base_dir, catalog)
        else:
            payload = e.status.payload
            dependency_uses: set[str] = set()
            if (
                kind == "laws"
                and scope == "shared"
                and view == "owned"
                and targets is not None
            ):
                dependency_uses = {
                    identifier
                    for (source_kind, source_scope), own_entry in h.items()
                    if source_kind == "laws"
                    and source_scope != "shared"
                    and (value is None or source_scope == f"value:{value}")
                    and isinstance(own_entry.status, T.Applicable)
                    for law in _owned(
                        own_entry.status.payload.laws, targets, ("owner",)
                    )
                    for identifier in law.uses
                }
            content = view_payload(
                kind, payload, view, targets, dependency_uses=dependency_uses
            )
        content = enc(content) if dc.is_dataclass(content) else content
        out.append((kind, scope, sha(content), view, content))
    for kind, (view, _d, _b) in need.items():
        if (kind, "shared") not in h:
            out.append(
                (
                    kind,
                    "shared",
                    "-",
                    view,
                    {
                        "UNASSESSED": "this handoff has no such section; do not read this as not applicable"
                    },
                )
            )
    return sorted(out, key=lambda x: (x[0], x[1]))


# --------------------------------------------------------------------------- grammar description
def _fmt(tp: t.Any, meta: t.Mapping[str, t.Any]) -> str:
    o = t.get_origin(tp)
    if is_union(o):
        args = t.get_args(tp)
        none = type(None) in args
        rest = [a for a in args if a is not type(None)]
        s = " | ".join(_fmt(a, meta) for a in rest)
        return s + ("?" if none else "")
    if o is t.Literal:
        return "|".join(map(str, t.get_args(tp)))
    if o is tuple:
        return (
            f"[{_fmt(t.get_args(tp)[0], {})}]"
            + ("+" if meta.get("nonempty") else "")
            + (" (unique refs)" if meta.get("unique_refs") else "")
        )
    if tp is int:
        return "int>=1" if meta.get("positive") else "int"
    if tp is float:
        return "number>=0" if meta.get("nonneg") else "number"
    if tp is str:
        if meta.get("display"):
            return str(meta["display"])
        return "str"
    return getattr(tp, "__name__", str(tp))


def _reachable(root: type, seen: dict[str, type]) -> None:
    if root.__name__ in seen:
        return
    seen[root.__name__] = root
    for f in dc.fields(root):
        for sub in _subtypes(t.get_type_hints(root)[f.name]):
            _reachable(sub, seen)


def _subtypes(tp: t.Any) -> list[type]:
    if dc.is_dataclass(tp):
        return [tp]
    return [s for a in t.get_args(tp) for s in _subtypes(a)]


def describe_types() -> str:
    """The grammar as the architect sees it, derived from the dataclasses (cannot drift from them)."""
    seen: dict[str, type] = {}
    for _kind, cls in T.PAYLOAD.items():
        _reachable(cls, seen)
    literal_argv_fields = [
        f"`{name}.{field.name}`"
        for name, cls in seen.items()
        for field in dc.fields(cls)
        if field.metadata.get("literal_argv")
    ]
    string_rule = "Strings must be nonblank"
    if literal_argv_fields:
        string_rule += (
            f", except later elements of {', '.join(literal_argv_fields)} "
            "(command argv data arguments), which may be blank or whitespace "
            "and are kept literally; the executable (first element) must be nonblank"
        )
    lines = [
        "Every record is a closed JSON object: no extra key. `tag` selects a variant. "
        + string_rule
        + ";",
        "Semantic slots are exact FactRef objects {ref: FactId}; define text only in the schema-2 DESIGN facts catalog. Values select shared typed records by inherits ids, with their dependencies.",
        '[X]+ is a list with at least one item; a field with `?` may be left out. A document is {"sections": [{"kind", "scope", "status"}]};',
        'status is {"tag":"applicable","payload":...} or {"tag":"not_applicable","reason":...};',
        "kind is one of " + "|".join(T.KINDS) + "; scope is `shared` or `value:<n>`.",
        "",
    ]
    for name, cls in seen.items():
        hints = t.get_type_hints(cls)
        fields = []
        for f in dc.fields(cls):
            if f.name == "tag":
                fields.append(f"tag={f.default!r}")
                continue
            fields.append(f"{f.name}: {_fmt(hints[f.name], f.metadata)}")
        lines.append(f"{name} {{ " + "; ".join(fields) + " }")
    return "\n".join(lines)


def grammar_what(role: str) -> str:
    """The WHAT derived from the grammar, so the prompt and the validator cannot drift apart."""
    if role == "architect":
        out = [
            "Deliver these sections at shared scope, each applicable or not_applicable with a reason: "
            + ", ".join(T.REQUIRED_SHARED)
            + ". Section `construction` is optional.",
            "Receipts: run every formal command and test through `python3 g10.py run ... -- <command>`. The tool OBSERVES the argv, exit "
            "status, duration, tool version, raw output and trace; YOU DECLARE the tool kind, target, variant, model and the property names or "
            "law ids in --checks (a rule compares them with the sections that cite the run). A run you did not execute is a claim: "
            "`g10.py record`. A scenario is read from the raw trace of a run made with `quint run --mbt --out-itf=FILE`; you never write its steps.",
            "Grammar:",
            describe_types(),
            "",
            "Checked when you submit (python3 g10.py check FILE... --targets PATHS): every rule below, all at once, each with WHAT/WHY/HOW.",
        ]
        out += [
            f"- {rid}: {w}. Fix: {how}." for rid, (w, _y, how, _s) in RU.RULES.items()
        ]
        return "\n".join(out)
    lines = ["You receive these sections of the handoff and decide as follows:"]
    lines += [
        f"- {kind} (view {view}): {decision}."
        for kind, (view, decision, _b) in CONSUMERS[role].items()
    ]
    if not CONSUMERS[role]:
        lines.append("- none: this role receives no design section, by construction.")
    return "\n".join(lines)


# These independent WHAT, scoped authority and caller-context inputs are the
# preserved measured compose API, including its positional call contract.
def compose(  # noqa: PLR0913, PLR0917
    role: str,
    h: T.Handoff,
    template_what: str,
    context: dict[str, str] | None = None,
    verbatim: str = "",
    value: int | None = None,
    targets: t.Collection[str] | None = None,
    base_dir: str | None = None,
    catalog: FactCatalog | None = None,
    inherits: t.Iterable[T.FactRef] = (),
) -> str:
    if catalog is None:
        raise ValueError(R.CATALOG_UNAVAILABLE)
    rows = project(
        h, role, value, targets, base_dir, catalog=catalog, inherits=inherits
    )
    parts = [
        f"=== [T] WHAT ({role}) ===\n{template_what.strip()}\n{grammar_what(role)}"
    ]
    for kind, scope, s, view, content in rows:
        parts.append(
            f"=== [H] {kind}@{scope} sha={s[:12]} view={view} ===\n"
            + json.dumps(
                content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
        )
    parts.append(
        "=== [F] facts ===\n"
        + json.dumps(
            catalog.reachable(*(row[4] for row in rows)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    ctx = "\n".join(f"{k}: {(context or {})[k]}" for k in sorted(context or {}))
    parts.append(
        "=== [C] orchestrator ===\n" + ctx + (("\n" if ctx else "") + verbatim.strip())
    )
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------- summary and human views
def summary(h: T.Handoff, catalog: FactCatalog | None = None) -> dict:
    """GDP-8 arity: the third state (could not verify, absent, pending) reaches the aggregate."""
    h = R.resolved(h, catalog)
    out: dict[str, t.Any] = {
        "sections": {},
        "missing_shared": [k for k in T.REQUIRED_SHARED if (k, "shared") not in h],
        "claims": {"PASS": 0, "BLOCKED": 0, "NOT_APPLICABLE": 0, "INHERITED": 0},
        "proofs": {"passed": 0, "indeterminate": 0, "refuted": 0},
        "closure": {},
        "scenarios": {},
        "runs": {"kept_output": 0, "claim": 0},
    }
    for (k, s), e in sorted(h.items()):
        out["sections"][f"{k}@{s}"] = (
            "applicable"
            if isinstance(e.status, T.Applicable)
            else f"not_applicable: {e.status.reason}"
        )
        if not isinstance(e.status, T.Applicable):
            continue
        p = e.status.payload
        if k == "closure":
            for c in p.closures:
                row = {}
                for cname in (
                    "safety",
                    "inhabitation",
                    "public_reachability",
                    "liveness",
                ):
                    cl = getattr(c, cname)
                    if isinstance(cl, T.Claim):
                        proof = (
                            f", proof {cl.basis.proof}"
                            if isinstance(cl.basis, T.Checked)
                            else ""
                        )
                        row[cname] = f"{cl.design}/{cl.runtime} ({cl.basis.tag}{proof})"
                        out["claims"][cl.design] += 1
                        if isinstance(cl.basis, T.Checked):
                            out["proofs"][cl.basis.proof] += 1
                    elif isinstance(cl, T.NotApplicableClaim):
                        row[cname] = "NOT_APPLICABLE"
                        out["claims"]["NOT_APPLICABLE"] += 1
                    else:
                        row[cname] = "INHERITED"
                        out["claims"]["INHERITED"] += 1
                out["closure"][f"{s}/{c.subject}"] = row
        elif k == "scenarios":
            for sc in p.scenarios:
                key = (
                    "pending"
                    if isinstance(sc.review, T.Pending)
                    else sc.review.judgment
                )
                out["scenarios"][key] = out["scenarios"].get(key, 0) + 1
        elif k == "receipts":
            for r in p.runs:
                out["runs"]["kept_output" if r.artifacts else "claim"] += 1
    return out


def render_markdown(
    h: T.Handoff, base_dir: str | None = None, catalog: FactCatalog | None = None
) -> str:
    """Human projection of the typed sections. Never re-parsed by code (ADR-DES-003)."""
    h = {key: canonical(entry) for key, entry in R.resolved(h, catalog).items()}
    out = []
    for (kind, scope), e in sorted(h.items()):
        out.append(f"## {kind} ({scope})")
        if isinstance(e.status, T.NotApplicable):
            out += [f"Not applicable: {e.status.reason}", ""]
            continue
        p = e.status.payload
        if kind == "laws":
            out += [
                f"- observation {o.id}: {o.description} -> {o.result_type}; cannot distinguish: {o.cannot_distinguish}"
                for o in p.observations
            ]
            out += [f"- constructor {c.id}: {c.signature}" for c in p.constructors]
            out += [
                f"- law {x.id} [{x.kind}, {x.layer}] owner {x.owner}: {x.statement}"
                for x in p.laws
            ]
            out += [
                f"- refuted {x.id} ({x.cause}): {x.statement}; counterexample: {x.counterexample}"
                for x in p.refuted
            ]
        elif kind == "construction":
            out += [
                f"- {c.id} [{c.strength}] owner {c.owner}: {c.proposition}; harm: {c.harm}"
                for c in p.claims
            ]
            out += [
                f"- unknown: {u.state} (risk owner: {u.risk_owner})" for u in p.unknown
            ]
        elif kind == "model":
            for m in p.models:
                out.append(
                    f"- model {m.id} ({m.language}) at {m.path}, identity {m.sha256[:12]}; leaves out: {'; '.join(m.exclusions) or 'nothing'}"
                )
                out += [
                    f"  - mutant {mu.id}: {mu.description}; kills {', '.join(k.property for k in mu.kills)}"
                    for mu in m.mutants
                ]
        elif kind == "closure":
            for row in _closure_view(p, "readable")["closures"]:
                out.append(f"- {row['subject']}")
                for cname in (
                    "safety",
                    "inhabitation",
                    "public_reachability",
                    "liveness",
                ):
                    c = row[cname]
                    if "statement" in c:
                        out.append(
                            f"  - {cname}: design {c['design']}, runtime {c['runtime']} ({c['rests_on']}): {c['statement']}"
                        )
                    else:
                        out.append(
                            f"  - {cname}: {c['tag']}"
                            + (f": {c['reason']}" if "reason" in c else "")
                        )
        elif kind == "receipts":
            out += [
                f"- run {r.id} [{r.tool} {r.tool_version}, {r.target}, {r.variant}] exit {r.exit_status} {r.result_class}"
                f"{' (output kept)' if r.artifacts else ' (claim, no output)'}: {' '.join(r.argv)}"
                for r in p.runs
            ]
        else:  # scenarios: the kinds are closed, so nothing else reaches here
            v = S.visible(h, scope)
            for sc in _by(p.scenarios, lambda x: x.id):
                r = R.render_scenario(v, sc, base_dir, catalog)
                out.append(
                    R.scenario_text(r)
                    if isinstance(r, R.Rendered)
                    else f"{sc.title} [{sc.kind}]: not rendered: "
                    + (r.reason if isinstance(r, R.Skipped) else "; ".join(r.problems))
                )
        out.append("")
    return "\n".join(out)


def render_html(
    h: T.Handoff, base_dir: str | None = None, catalog: FactCatalog | None = None
) -> str:
    """The shared HTML view of the scenarios (E-G09-03): self-contained, escaped, deterministic."""
    h = R.resolved(h, catalog)
    items: list[R.Rendered] = []
    missing: list[str] = []
    for (kind, scope), e in sorted(h.items()):
        if kind != "scenarios" or not isinstance(e.status, T.Applicable):
            continue
        v = S.visible(h, scope)
        for sc in _by(e.status.payload.scenarios, lambda x: x.id):
            r = R.render_scenario(v, sc, base_dir, catalog)
            if isinstance(r, R.Rendered):
                items.append(r)
            else:
                missing.append(
                    f"{sc.title}: "
                    + (r.reason if isinstance(r, R.Skipped) else "; ".join(r.problems))
                )
    return R.scenarios_html(items, missing)
