"""Cross-field and cross-section rules. Shape (closed vocabularies, required fields, one record per atom
kind) is in g10_types.py and g10_codec.py; what a shape cannot say is here. Every rule has WHAT / WHY / HOW
and a source: the repository text it comes from, and the measured rubric gap it relates to, if any.
A gap is "related" when it concerns the same subject; it does not prove the rule would have prevented it.

check() returns ALL defects in one pass (E-G08-52) plus the checks that could not run and why."""

from __future__ import annotations

import os
import typing as t

from . import g10_render as R
from . import g10_scope as S
from . import g10_types as T
from .g10_defect import Defect


# id -> (what, why, how, source)
RULES: dict[str, tuple[str, str, str, str]] = {
    "X1": (
        "a required section is absent at shared scope",
        "an absent section cannot be told from one judged not applicable, so the gap stays silent",
        "deliver it as applicable, or as not_applicable with a reason",
        "GDP-6/8; no related gap: the scenario-flow gaps (E-G09-01 read the skill, -03 verified renderer, -05 human review) are about flow and "
        "rendering, and a section delivered not_applicable with a reason passes this rule",
    ),
    "L1": (
        "an id is used twice in one scope, or in the shared scope and in a value scope",
        "ids are the join keys that tests, receipts and claims cite; the same id in two different values never meets",
        "give every observation, constructor, generator, law and refuted law its own id (within shared plus one value)",
        "structure; no related gap",
    ),
    "L2": (
        "a law uses an id that is not a declared observation or constructor",
        "a law relates declared observations and constructors, nothing else",
        "declare the id in `observations` or `constructors` of a laws section at shared scope or at the same value, or fix `uses`",
        "nw-algebraic-design-protocol (observations first); structure; no related gap (E-G05-56 concerns the Observation fields)",
    ),
    "L3": (
        "equality names an observation that is not declared",
        "equality is agreement under a stated set of observations, never structural",
        "list in `equality.under` only ids declared in `observations` (shared scope or the same value)",
        "nw-algebraic-design-protocol; structure; no related gap",
    ),
    "L4": (
        "an owner is not a path declared in `targets`",
        "the crafter must know which responsibility keeps the law, and which file it may change",
        "write the owner as a path of a declared target (path, path::symbol or path:line); for new code write CREATE_NEW:<path>::<symbol> and declare that path as a target",
        "nw-software-crafter:46 'declared mutable targets'; nw-code-craftsmanship 'invariant owner'; no related gap",
    ),
    "L5": (
        "executed evidence is not about the law: a receipt is missing, no ok run of the fixed or base code names the law, or (broad treatment) "
        "no violation run of the unfixed code or of a mutant names it",
        "a check never seen to fail is not evidence; a broad law needs a run that shows its falsifier is caught; a violation of the FIXED code is a bug, not a falsifier",
        "cite receipts whose `checks` name this law: one ok run with variant fixed or base and, for a broad treatment, one violation run with variant "
        "unfixed or mutant:<id>; the runs target prototype or implementation",
        "CLAUDE.md Evidence: 'a check you have not seen FAIL is not evidence'; related gap: E-G08-79 partial in v7r1-r3, met in v9lb1 (run the stated laws "
        "against a reference over generated inputs that include the refuting case); `checks` is declared by whoever records the run, so this rule compares declarations",
    ),
    "L6": (
        "a refuted law cites a receipt that does not exist",
        "the receipt is kept beside the counterexample",
        "cite the id of a run in a receipts section at shared scope or the same value, or omit `run`",
        "related gap: E-G08-79 partial in v7r1-r3 (covers only 'the receipt beside the counterexample', not whether the run included the refuting case)",
    ),
    "L7": (
        "a broad treatment cites a generator that is not declared in `generators`",
        "the generator is where size, seed and the refuting cases live; a law cannot cite what is not written",
        "declare the generator in `laws.generators` and cite its id, or fix `generator`",
        "structure; no related gap",
    ),
    "C1": (
        "a construction claim id is used twice in one scope, or in the shared scope and in a value scope",
        "ids are join keys",
        "make ids unique",
        "structure; no related gap",
    ),
    "C2": (
        "a claim weaker than proof names no bypass route",
        "a guarantee the runtime can bypass must say how, or it reads as proof",
        "list in `bypass` who can still construct the invalid state",
        "nw-certainty-by-construction:103-106; nw-type-level-design:55; related gap: E-G04-88 met/partial/partial in v7r1-r3 (covers 'who could construct it')",
    ),
    "C3": (
        "a construction owner is not a path declared in `targets`",
        "an invariant needs one owner the crafter can change",
        "write the owner as a path of a declared target, or CREATE_NEW:<path>::<symbol> and declare that path as a target",
        "nw-code-craftsmanship 'invariant owner'; no related gap",
    ),
    "M1": (
        "a model id, a mutant id or an atom name repeats, or a kill does not cite a violation run of that mutant on that model for that property",
        "the kill matrix must be checkable: a property that no run of a mutant violates is not killed by it; a repeated name makes a lookup depend on list order",
        (
            "fix repeated ids and names; every kill cites a run with tool quint_run, quint_verify, tlc or apalache, target model, result violation, "
            "variant mutant:<mutant id>, the model_id of this model, and the killed property in the run's `checks`"
        ),
        "nw-solution-architect-formal-verification:74-76 (counterexample exit); no related gap",
    ),
    "M2": (
        "an action template names a placeholder that is not a state atom of its model",
        "a scenario sentence prints only what the model's state holds; anything else would be invented narration",
        "write each placeholder as {name} or {name@pre} with `name` the name of a state atom of the same model",
        "nw-po-scenario-exploration:61-65, 83-88 (explicit domain action templates); related gap: E-G09-03 (the templates part) absent in v7r1-r3 and v9lb1",
    ),
    "R1": (
        "a run id is used twice in one scope, or in the shared scope and in a value scope",
        "receipts are cited by id",
        "make run ids unique",
        "structure; no related gap",
    ),
    "R2": (
        "result_class and exit_status disagree (ok needs exit 0; the others need non-zero)",
        "a receipt that contradicts itself is a transcription error",
        "copy exit_status and result_class from the same execution; `g10 run` records both from the process",
        "nw-solution-architect-formal-verification:61 (literal argv, exit status, result); no related gap",
    ),
    "R3": (
        "a run names a model that does not exist at its scope",
        "a receipt binds to what it checked",
        "set `model_id` to the id of a model in a model section at shared scope or the same value, or omit it",
        "structure; no related gap",
    ),
    "R4": (
        "a run variant names a mutant that its model does not declare",
        "variants are a closed vocabulary",
        "use `mutant:<id>` of a mutant declared by the run's model (or by a visible model when the run has no model_id)",
        "structure; no related gap",
    ),
    "R5": (
        "a run of a model records no identity of the text it used, or one that differs from the model text (a mutant run records the sha256 of the mutant text, which is not the model text)",
        "a receipt about another version of the model is not evidence for this one; a kill that binds to no text could be a kill of anything",
        "run the command again with `g10 run --model-file <file>`, which records the sha256 of the file (for a mutant: the mutant file), or set `model_sha256` to the sha256 of the text that ran",
        "related gap: E-V2-A-70 partial in v7r1-r3 (covers 'retains model identity')",
    ),
    "R6": (
        "a file kept for a run is missing or changed after the run, an output file is not artifacts/<run id>.out, or one file is cited by two runs",
        "a raw output or trace that no longer matches its sha256 proves nothing about the run; a file cited by two runs is evidence for at most one of them",
        "keep the artifact files beside the sidecar unchanged, or run the command again with `g10 run`, which writes artifacts/<run id>.out and refuses a trace path that already exists",
        "related gap: E-G08-18 met/partial/partial in v7r1-r3 (covers 'keep raw traces')",
    ),
    "CL1": (
        "a closure claim has a basis its class cannot take",
        "safety rests on a check, a construction or an argument; inhabitation and reachability on a route; liveness on a check or an argument",
        "change `basis.tag` to one the class allows",
        "nw-certainty-by-construction:11-15 (four separate claims); no related gap",
    ),
    "CL2": (
        "a BLOCKED claim has no design_note, or a PASS claim rests on a refuted proof",
        "BLOCKED must say what is missing or refuted; a counterexample against a claim blocks it",
        "write design_note for BLOCKED; set design BLOCKED when `basis.proof` is refuted",
        (
            "nw-design:403-406 (the DESIGN axis is PASS or BLOCKED) and 421-435 (a refutation is a root-cause question); 'refuted means BLOCKED' is my inference "
            "from the two-valued axis, not a quoted sentence; related gap: E-V2-A-54 partial/met/partial in v7r1-r3 (covers exact PASS|BLOCKED and the runtime values)"
        ),
    ),
    "CL3": (
        "a checked claim's proof status disagrees with its runs",
        "a passing simulation is not a completed formal verification; a passed proof that a cited run violates is contradictory; a proof that is not passed says why",
        (
            "proof passed: for every property cite in `runs` an ok run with tool quint_verify, tlc, apalache or agda, target model, the model_id of `basis`, "
            "variant base (fairness for liveness) and the property in `checks`, and cite no violation run of that model, property and variant. "
            "If the checker cannot run, set proof indeterminate and write proof_note (nw-design:463-466: only that proof is INDETERMINATE; tool absence does not block DESIGN). "
            "proof refuted: cite a violation run of this model, variant base (fairness for liveness), not a mutant, that names the property, and write proof_note with the counterexample"
        ),
        (
            "nw-solution-architect-formal-verification:17-23 (completion needs an executed checker; otherwise the claim stays INDETERMINATE, not PASS on substitute evidence), 44-51; "
            "nw-design:463-466; related gap: E-G05-12 partial/declared_na_weak/partial in v7r1-r3 (covers 'execute the temporal property')"
        ),
    ),
    "CL4": (
        "a passed claim has a property that no mutant kills",
        "a check that kills no mutant may check nothing",
        "add a behavioral mutant of the model whose kill row names this property and cites its violation run",
        "nw-solution-architect-formal-verification:71-85; no related gap",
    ),
    "CL5": (
        "a checked liveness claim has no fairness",
        "liveness under no stated fairness is vacuous",
        "write the fairness assumption in `basis.fairness`",
        "nw-solution-architect-formal-verification:57-60; related gap: E-G05-12 partial/declared_na_weak/partial in v7r1-r3 (covers 'fairness assumptions')",
    ),
    "CL6": (
        "runtime INDETERMINATE without runtime_note, or OBSERVED without an ok implementation run in `runs`",
        "OBSERVED is a statement about built code; INDETERMINATE must say what was not seen",
        "write runtime_note for INDETERMINATE; for OBSERVED cite in `runs` an ok run with target implementation",
        "nw-design:403-404, 410-412; no related gap (the note and the run are this grammar's requirement)",
    ),
    "CL7": (
        "a claim cites a run, law, model or construction claim that does not exist at its scope",
        "every join must resolve inside what the projection of that scope keeps",
        "cite the id of an existing entry at shared scope or the same value, or add the missing entry",
        "structure; no related gap",
    ),
    "CL8": (
        "an inherited liveness is used outside a value scope, or the shared scope states no liveness for the same subject",
        "the claim inherited must exist",
        "state the liveness of the same subject at shared scope as a claim or not_applicable, and use `inherited` only in a value scope",
        "structure; v4r1 'LIVENESS inherits shared INDETERMINATE'; no related gap",
    ),
    "CL9": (
        "a PASS argued claim states no assumptions",
        "an argument without stated assumptions is an assertion",
        "list in `assumptions` what the argument rests on (bounds, environment, fairness)",
        "ADR wording 'PASS under ...' (ADR-DES-003:1358); nw-design:403-406; no related gap",
    ),
    "CL10": (
        "two closures of one scope have the same subject",
        "each public value has one closure; a second one would contradict or hide the first",
        "give every closure of a scope its own subject",
        "nw-design:399 'for every public value'; structure; no related gap",
    ),
    "S1": (
        "a scenario has a review in auto mode",
        "silence or no human reply is never approval; the producer cannot judge its own scenarios",
        "deliver every scenario as pending in auto mode; a human sets the judgment",
        "nw-po-scenario-exploration:22; related gap: E-G09-06 partial/absent/partial in v7r1-r3 (covers 'never treat silence as approval')",
    ),
    "S2": (
        "a scenario's source run does not fit its kind, keeps no trace, or its kept trace has a status that does not fit the kind",
        "a scenario is read from a real trace of the model, never authored; a bug trace must not pass for a design counterexample, and a passing walk must not pass for a counterexample",
        (
            "`source_run` names a run with tool quint_run, quint_verify, tlc or apalache, target model and a model_id, that keeps an artifact with role trace. "
            "kind counterexample: result violation, a variant that is not a mutant, and a trace with status violation. kind mutant: result violation, variant mutant:<id>, trace status violation. "
            "kind example: result ok and trace status ok, or variant witness and trace status violation. For counterexample and mutant the run's `checks` names exactly one property"
        ),
        "nw-po-scenario-exploration:58-60; related gap: E-V2-A-70 partial in v7r1-r3 (covers 'scenario traces from the actual model' and 'the raw trace')",
    ),
    "S3": (
        "a scenario cannot be rendered from its trace: the trace names an action with no action atom, names none, or lacks a variable a template prints",
        "unsupported actions are reported, never filled in with invented narration",
        "run quint with --mbt so that the trace names its actions; give every action of the trace an action atom with a template, and every variable a template prints a state atom",
        "nw-po-scenario-exploration:61-65, 83-88; related gap: E-G09-03 (a verified deterministic renderer) absent in v7r1-r3 and v9lb1; E-G09-04 partial in v7r1-r3",
    ),
    "S4": (
        "a judgment is stale (the model or the trace it judged is not the current one), or depends/unclear/correction has no note",
        "feedback on another model or another trace must not be reused; a conditional judgment must carry its condition",
        "a stale judgment cannot be reused: regenerate the scenario and set it pending; write a note for depends, unclear or correction",
        "nw-po-scenario-exploration:69-72, 97; related gap: E-G09-06 partial/absent/partial in v7r1-r3 (covers 'against the exact model and scenario')",
    ),
    "S5": (
        "a scenario id is used twice in one scope, or in the shared scope and in a value scope",
        "ids are join keys",
        "make scenario ids unique",
        "structure; no related gap",
    ),
}

CLASSES = ("safety", "inhabitation", "public_reachability", "liveness")
ALLOWED_BASIS: dict[str, tuple[type, ...]] = {
    "safety": (T.Checked, T.Constructed, T.Argued),
    "inhabitation": (T.Route,),
    "public_reachability": (T.Route,),
    "liveness": (T.Checked, T.Argued),
}


def _dups(ids: list[str]) -> list[str]:
    return sorted({i for i in ids if ids.count(i) > 1})


def _clashing(pairs: list[tuple[str, str]]) -> list[str]:
    """Ids that one entry can resolve to another: used twice in one scope, or in `shared` and anywhere else.
    The same id in two different values never meets (scope.visible keeps shared plus one value)."""
    scopes: dict[str, list[str]] = {}
    for i, sc in pairs:
        scopes.setdefault(i, []).append(sc)
    return sorted(
        i
        for i, scs in scopes.items()
        if len(scs) > 1 and (len(set(scs)) < len(scs) or "shared" in scs)
    )


def _is_mutant(variant: str) -> bool:
    return variant.startswith("mutant:")


def _names_the_law(r: T.Run | None, law_id: str) -> bool:
    """A run of the prototype or the implementation that names the law in `checks` (a probe or a model run backs nothing)."""
    return (
        r is not None
        and law_id in r.checks
        and r.target in ("prototype", "implementation")
    )


def _law_ok(r: T.Run | None, law_id: str) -> bool:
    """An ok run of the code that is meant to be right (variant fixed or base): the law holds there."""
    return (
        _names_the_law(r, law_id)
        and r.result_class == "ok"
        and r.variant in ("fixed", "base")
    )


def _law_falsified(r: T.Run | None, law_id: str) -> bool:
    """A violation run of the unfixed code or of a mutant: the law can fail. A violation of the FIXED code is a bug, not a falsifier."""
    return (
        _names_the_law(r, law_id)
        and r.result_class == "violation"
        and (r.variant == "unfixed" or _is_mutant(r.variant))
    )


def _status_fits(kind: str, r: T.Run, status: str) -> bool:
    """The kept trace agrees with the scenario kind: violation for a counterexample or mutant; ok for an example, violation for a witness."""
    if kind in ("counterexample", "mutant"):
        return status == "violation"
    return status == ("violation" if r.variant == "witness" else "ok")


def _is_the_kill(r: T.Run | None, mutant_id: str, model_id: str, prop: str) -> bool:
    """The run is a violation of THAT mutant of THAT model that names THAT property."""
    return (
        r is not None
        and r.tool in T.MODEL_TOOLS
        and r.target == "model"
        and r.result_class == "violation"
        and r.variant == f"mutant:{mutant_id}"
        and r.model_id == model_id
        and prop in r.checks
    )


def _verifies(r: T.Run | None, model_id: str, variant: str, prop: str) -> bool:
    """An ok run of a VERIFIER (a simulation verifies nothing) on this model, in this variant, that names the property."""
    return (
        r is not None
        and r.result_class == "ok"
        and r.tool in T.VERIFIERS
        and r.target == "model"
        and r.model_id == model_id
        and r.variant == variant
        and prop in r.checks
    )


def _refutes(r: T.Run | None, model_id: str, variant: str, prop: str) -> bool:
    """A violation run of THIS model in the variant under test (the violation of a mutant refutes nothing about the design)."""
    return (
        r is not None
        and r.result_class == "violation"
        and r.target == "model"
        and r.model_id == model_id
        and r.variant == variant
        and prop in r.checks
    )


def _fits(r: T.Run | None, kind: str, models: dict[str, T.Model]) -> bool:
    """The run can source a scenario of this kind (rule S2)."""
    if not (
        r is not None
        and r.model_id in models
        and r.tool in T.MODEL_TOOLS
        and r.target == "model"
    ):
        return False
    if kind == "counterexample":
        return (
            r.result_class == "violation"
            and not _is_mutant(r.variant)
            and len(r.checks) == 1
        )
    if kind == "mutant":
        return (
            r.result_class == "violation"
            and _is_mutant(r.variant)
            and len(r.checks) == 1
        )
    return r.result_class == "ok" or (
        r.variant == "witness" and r.result_class == "violation"
    )


def check(
    h: T.Handoff,
    targets: t.Sequence[str] | None = None,
    mode: str = "auto",
    base_dir: str | None = None,
) -> tuple[list[Defect], list[str]]:
    """All defects in one pass, plus the checks that could not run and why."""
    ds: list[Defect] = []
    skipped: list[str] = []

    def add(rid: str, where: str, detail: str) -> None:
        w, y, how, _ = RULES[rid]
        ds.append(Defect(rid, where, f"{w}: {detail}", y, how))

    def pays(kind: str) -> list[tuple[str, t.Any]]:
        return [
            (s, e.status.payload)
            for (k, s), e in sorted(h.items())
            if k == kind and isinstance(e.status, T.Applicable)
        ]

    cache: dict[str, S.Visible] = {}

    def vis(scope: str) -> S.Visible:
        if scope not in cache:
            cache[scope] = S.visible(h, scope)
        return cache[scope]

    tset = set(targets) if targets is not None else None
    if tset is None:
        skipped.append(
            "L4 and C3 (owner is a declared target) need --targets; none were given"
        )
    for kind in T.REQUIRED_SHARED:
        if (kind, "shared") not in h:
            add("X1", f"{kind}@shared", "no entry")

    laws_p, cons_p, model_p = pays("laws"), pays("construction"), pays("model")
    clos_p, rec_p, scen_p = pays("closure"), pays("receipts"), pays("scenarios")

    # ---- laws
    laws_ids = [
        (x.id, s)
        for s, p in laws_p
        for x in (*p.observations, *p.constructors, *p.generators, *p.laws, *p.refuted)
    ]
    for i in _clashing(laws_ids):
        add("L1", f"laws:{i}", f"id {i}")
    for scope, p in laws_p:
        v = vis(scope)
        if any(u not in v.observations for u in p.equality.under):
            add("L3", f"laws@{scope}.equality", f"under={list(p.equality.under)}")
        for lw in p.laws:
            where = f"laws:{lw.id}"
            bad = [u for u in lw.uses if u not in v.observations | v.constructors]
            if bad:
                add("L2", where, f"unknown {bad}")
            broad = isinstance(lw.treatment, T.Broad)
            if broad and lw.treatment.generator not in v.generators:
                add("L7", where, f"generator {lw.treatment.generator}")
            if tset is not None and T.locator_path(lw.owner) not in tset:
                add("L4", where, f"owner {lw.owner!r}")
            if isinstance(lw.evidence, T.Executed):
                rs = [v.runs.get(x) for x in lw.evidence.receipts]
                why = []
                if any(r is None for r in rs):
                    why.append("a cited receipt does not exist")
                if not any(_law_ok(r, lw.id) for r in rs):
                    why.append(
                        f"no ok run of the fixed or base code names {lw.id} in `checks`"
                    )
                if broad and not any(_law_falsified(r, lw.id) for r in rs):
                    why.append(
                        f"no violation run of the unfixed code or of a mutant names {lw.id} in `checks`"
                    )
                if why:
                    add(
                        "L5",
                        where,
                        f"receipts={list(lw.evidence.receipts)}: " + "; ".join(why),
                    )
        for rf in p.refuted:
            if rf.run is not None and rf.run not in v.runs:
                add("L6", f"laws:{rf.id}", f"run {rf.run}")

    # ---- construction
    for i in _clashing([(c.id, s) for s, p in cons_p for c in p.claims]):
        add("C1", f"construction:{i}", f"id {i}")
    for _, p in cons_p:
        for c in p.claims:
            if c.strength != "proof" and not c.bypass:
                add(
                    "C2", f"construction:{c.id}", f"strength {c.strength} and no bypass"
                )
            if tset is not None and T.locator_path(c.owner) not in tset:
                add("C3", f"construction:{c.id}", f"owner {c.owner!r}")

    # ---- models, templates and kills
    scoped_models = [(s, m) for s, p in model_p for m in p.models]
    for i in _clashing([(m.id, s) for s, m in scoped_models]) + _clashing(
        [(mu.id, s) for s, m in scoped_models for mu in m.mutants]
    ):
        add("M1", f"model:{i}", f"id {i} repeats")
    for _, m in scoped_models:
        for i in _dups([a.name for a in m.atoms]):
            add("M1", f"model:{m.id}", f"atom name {i} repeats")
    for scope, p in model_p:
        v = vis(scope)
        for m in p.models:
            for problem in R.template_problems(m):
                add("M2", f"model:{m.id}", problem)
            for mu in m.mutants:
                for k in mu.kills:
                    if not _is_the_kill(v.runs.get(k.run), mu.id, m.id, k.property):
                        add(
                            "M1",
                            f"model:{m.id}.{mu.id}",
                            f"kill ({k.property}, {k.run})",
                        )

    # ---- receipts
    for i in _clashing([(r.id, s) for s, p in rec_p for r in p.runs]):
        add("R1", f"receipts:{i}", f"id {i}")
    cited: dict[str, set[tuple[str, str]]] = {}
    for scope, p in rec_p:
        for r in p.runs:
            for a in r.artifacts:
                cited.setdefault(a.path, set()).add((scope, r.id))
    have_artifacts = False
    for scope, p in rec_p:
        v = vis(scope)
        for r in p.runs:
            where = f"receipts:{r.id}"
            if (r.result_class == "ok") != (r.exit_status == 0):
                add("R2", where, f"{r.result_class} with exit {r.exit_status}")
            m = v.models.get(r.model_id) if r.model_id is not None else None
            if r.model_id is not None and m is None:
                add("R3", where, f"model_id {r.model_id}")
            if _is_mutant(r.variant):
                declared = {
                    mu.id
                    for x in ([m] if m is not None else v.models.values())
                    for mu in x.mutants
                }
                if r.variant.removeprefix("mutant:") not in declared:
                    add("R4", where, f"variant {r.variant}")
                elif m is not None and (
                    r.model_sha256 is None or r.model_sha256 == m.sha256
                ):
                    add(
                        "R5",
                        where,
                        f"a run of {r.variant} records "
                        + (
                            "no model_sha256"
                            if r.model_sha256 is None
                            else "the sha256 of the unmutated model, not of the mutant text"
                        ),
                    )
            elif m is not None and r.model_sha256 != m.sha256:
                add(
                    "R5",
                    where,
                    f"model_sha256 {r.model_sha256!r} but the model {m.id} text has {m.sha256}",
                )
            for a in r.artifacts:
                have_artifacts = True
                if a.role == "output" and a.path != f"artifacts/{r.id}.out":
                    add(
                        "R6", where, f"output file {a.path} is not artifacts/{r.id}.out"
                    )
                if len(cited[a.path]) > 1:
                    add(
                        "R6",
                        where,
                        f"file {a.path} is cited by runs "
                        f"{sorted(rid if scope == 'shared' else f'{scope}:{rid}' for scope, rid in cited[a.path])}",
                    )
                if base_dir is None:
                    continue
                path = os.path.join(base_dir, a.path)
                try:
                    with open(path, "rb") as fh:
                        digest = T.sha256_bytes(fh.read())
                except OSError:
                    add("R6", where, f"{a.role} file {a.path} is missing")
                    continue
                if digest != a.sha256:
                    add(
                        "R6",
                        where,
                        f"{a.role} file {a.path} has sha256 {digest}, the receipt says {a.sha256}",
                    )
    if have_artifacts and base_dir is None:
        skipped.append(
            "R6 and S3 (kept files match their sha256; scenarios render from their trace) need the directory of the sidecar files; none was given"
        )

    # ---- closure
    for i in _dups([f"{sc}/{c.subject}" for sc, p in clos_p for c in p.closures]):
        add("CL10", f"closure@{i.split('/')[0]}", f"subject {i.split('/', 1)[1]!r}")
    shared_set = dict(clos_p).get("shared")
    for scope, p in clos_p:
        v = vis(scope)
        for c in p.closures:
            for cname in CLASSES:
                entry = getattr(c, cname)
                where = f"closure@{scope}[{c.subject}].{cname}"
                if isinstance(entry, T.NotApplicableClaim):
                    continue
                if isinstance(entry, T.Inherited):
                    sh = (
                        next(
                            (x for x in shared_set.closures if x.subject == c.subject),
                            None,
                        )
                        if shared_set is not None
                        else None
                    )
                    if (
                        scope == "shared"
                        or sh is None
                        or not isinstance(sh.liveness, (T.Claim, T.NotApplicableClaim))
                    ):
                        add("CL8", where, f"scope {scope}")
                    continue
                cl: T.Claim = entry
                b = cl.basis
                if not isinstance(b, ALLOWED_BASIS[cname]):
                    add("CL1", where, f"basis {b.tag}")
                if cl.design == "BLOCKED" and not (cl.design_note or "").strip():
                    add("CL2", where, "BLOCKED without design_note")
                if (
                    cl.design == "PASS"
                    and isinstance(b, T.Checked)
                    and b.proof == "refuted"
                ):
                    add("CL2", where, "PASS on a refuted proof")
                crs = [v.runs.get(x) for x in cl.runs]
                for x, r in zip(cl.runs, crs, strict=True):
                    if r is None:
                        add("CL7", where, f"run {x}")
                for x in cl.laws:
                    if x not in v.laws:
                        add("CL7", where, f"law {x}")
                if isinstance(b, T.Checked):
                    m = v.models.get(b.model_id)
                    if m is None:
                        add("CL7", where, f"model {b.model_id}")
                    if cname == "liveness" and not (b.fairness or "").strip():
                        add("CL5", where, "no fairness")
                    if b.proof != "passed" and not (b.proof_note or "").strip():
                        add("CL3", where, f"proof {b.proof} without proof_note")
                    variant = "fairness" if cname == "liveness" else "base"
                    for prop in b.properties if m is not None else ():
                        if b.proof == "passed":
                            if not any(_verifies(r, m.id, variant, prop) for r in crs):
                                add(
                                    "CL3",
                                    where,
                                    f"property {prop} has no ok verification run with variant {variant}",
                                )
                            if any(_refutes(r, m.id, variant, prop) for r in crs):
                                add(
                                    "CL3",
                                    where,
                                    f"property {prop} is passed, but a cited run violates it in variant {variant}",
                                )
                            if not any(
                                k.property == prop for mu in m.mutants for k in mu.kills
                            ):
                                add("CL4", where, f"property {prop}")
                        elif b.proof == "refuted":
                            if not any(_refutes(r, m.id, variant, prop) for r in crs):
                                add(
                                    "CL3",
                                    where,
                                    f"property {prop} is refuted but no violation run of this model with variant {variant} (a mutant run does not count) names it",
                                )
                elif isinstance(b, T.Constructed):
                    for x in b.claims:
                        if x not in v.constructions:
                            add("CL7", where, f"construction claim {x}")
                elif (
                    isinstance(b, T.Argued)
                    and cl.design == "PASS"
                    and not cl.assumptions
                ):
                    add("CL9", where, "no assumptions")
                if (
                    cl.runtime == "INDETERMINATE"
                    and not (cl.runtime_note or "").strip()
                ):
                    add("CL6", where, "INDETERMINATE without runtime_note")
                if cl.runtime == "OBSERVED" and not any(
                    r and r.result_class == "ok" and r.target == "implementation"
                    for r in crs
                ):
                    add("CL6", where, "OBSERVED without an ok implementation run")

    # ---- scenarios
    for i in _clashing([(sc.id, s) for s, p in scen_p for sc in p.scenarios]):
        add("S5", f"scenarios:{i}", f"id {i}")
    s3_skips: list[str] = []
    for scope, p in scen_p:
        v = vis(scope)
        for sc in p.scenarios:
            where = f"scenarios:{sc.id}"
            r = v.runs.get(sc.source_run)
            fits = _fits(r, sc.kind, v.models)
            art = T.trace_of(r) if r is not None else None
            if not fits or art is None:
                add(
                    "S2",
                    where,
                    f"source_run {sc.source_run} kind {sc.kind}"
                    + (
                        ""
                        if art is not None or r is None
                        else "; the run keeps no trace"
                    ),
                )
            else:
                out = R.render_scenario(v, sc, base_dir)
                if isinstance(out, R.Bad):
                    add("S3", where, "; ".join(out.problems))
                elif isinstance(out, R.Skipped):
                    if out.reason not in s3_skips:
                        s3_skips.append(out.reason)
                elif not _status_fits(sc.kind, r, out.trace_status):
                    add(
                        "S2",
                        where,
                        f"the kept trace of run {r.id} has status {out.trace_status!r}, which does not fit kind {sc.kind}",
                    )
            if mode == "auto" and not isinstance(sc.review, T.Pending):
                add("S1", where, "review is not pending")
            if isinstance(sc.review, T.Judged):
                model = (
                    v.models.get(r.model_id) if r is not None and r.model_id else None
                )
                if model is not None and sc.review.model_identity != model.sha256:
                    add(
                        "S4",
                        where,
                        "STALE: model_identity is not the sha256 of the model of the source run",
                    )
                if art is not None and sc.review.trace_identity != art.sha256:
                    add(
                        "S4",
                        where,
                        "STALE: trace_identity is not the sha256 of the trace of the source run",
                    )
                if (
                    sc.review.judgment in ("depends", "unclear", "correction")
                    and not (sc.review.note or "").strip()
                ):
                    add("S4", where, f"judgment {sc.review.judgment} without a note")
    skipped += [f"S3 for a scenario: {x}" for x in s3_skips if base_dir is not None]
    return ds, skipped


def rules_markdown() -> str:
    lines = [
        "| rule | what is refused | why | how to fix | source and related gap |",
        "|---|---|---|---|---|",
    ]
    for rid, (w, y, how, src) in RULES.items():
        lines.append(f"| {rid} | {w} | {y} | {how} | {src} |")
    return "\n".join(lines)
