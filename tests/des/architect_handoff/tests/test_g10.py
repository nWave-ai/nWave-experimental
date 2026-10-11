"""G10 tests. Standard library only (hypothesis is not installed on this host): seeded generators.

Run from the repository: PYTHONPATH=src python -W ignore -m unittest discover -s tests/des/architect_handoff/tests
What is proven here:
  * every rule fires on ONE minimal mutation of a valid handoff and on nothing else, with WHAT, WHY and HOW;
    the HOW, applied literally, makes the rule stop firing (a message that lies is worse than a traceback);
  * the defects two independent reviewers found are regressions here, each with the document that got through;
  * decode is closed and total: no input makes it raise, and it collects every shape defect in one pass;
  * algebra over RANDOM well-formed handoffs derived from the dataclasses: round trip, canonical form
    (set order never matters, argv order does), merge is a partial disjoint union, the projection is
    deterministic, complete and local per role and per value scope, the examiner prompt is constant;
  * the receipts have one writer (g10 run); a scenario is read from a real trace, never authored.
"""

from __future__ import annotations

import contextlib
import copy
import dataclasses as dc
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import types
import typing as t
import unittest
from pathlib import Path


HERE = str(Path(__file__).resolve().parent)
ROOT = str(Path(HERE).parent)

from des.application.architect_handoff import g10 as G
from des.application.architect_handoff import g10_codec as C
from des.application.architect_handoff import g10_itf as I
from des.application.architect_handoff import g10_project as P
from des.application.architect_handoff import g10_render as R
from des.application.architect_handoff import g10_rules as RU
from des.application.architect_handoff import g10_run as RUN
from des.application.architect_handoff import g10_scope as S
from des.application.architect_handoff import g10_types as T


G10 = "des.application.architect_handoff.g10"
FIX = os.path.join(ROOT, "fixtures")
MINIMAL = os.path.join(FIX, "minimal.g10.json")
OO = os.path.join(FIX, "oo.g10.json")
V9_DIR = os.path.join(FIX, "v9lb1")
V9_TARGETS = [
    "pagination.py",
    "tests/test_pagination.py",
    "README.md",
    "formal/pagination_walk.qnt",
    "formal/pagination_live.qnt",
]
OO_TARGETS = ["inventory.py", "units.py", "store.py", "cli.py"]
UNPROVEN = (
    "L2",
    "L3",
    "L4",
    "L5",
    "L6",
    "L7",
    "L11",
    "L13",
)  # laws the v9lb1 design calls executed, though no run of the architect's scripts shows them both pass and fail


# --------------------------------------------------------------------------- helpers
def read(path: str) -> dict:
    doc, ds = C.load_json(path)
    assert not ds, ds
    ds = C.resolve_authoring(doc, str(Path(path).parent))
    assert not ds, ds
    return doc


def merged(paths: list[str]) -> dict:
    return {"sections": [s for p in paths for s in read(p)["sections"]]}


def decode(doc: dict) -> T.Handoff:
    h, ds = C.decode_handoff(doc)
    assert h is not None, [f"{d.rule} {d.where} {d.what}" for d in ds]
    return h


def defects(
    doc: dict, targets=None, mode: str = "auto", base: str | None = None
) -> list:
    h, ds = C.decode_handoff(doc)
    if h is None:
        return ds
    return RU.check(h, targets, mode, base)[0]


def rule_ids(
    doc: dict, targets=None, mode: str = "auto", base: str | None = None
) -> set[str]:
    return {d.rule for d in defects(doc, targets, mode, base)}


def section(doc: dict, kind: str, scope: str = "shared") -> dict:
    for s in doc["sections"]:
        if s["kind"] == kind and s["scope"] == scope:
            return s["status"]["payload"]
    raise KeyError((kind, scope))


def v9_doc(d: str) -> dict:
    return merged([os.path.join(d, "g10.json"), os.path.join(d, "g10.receipts.json")])


def base_doc(d: str) -> dict:
    """The v9lb1 translation with the eight laws that have no proof of falsifiability set to to_run: valid, 0 defects."""
    doc = v9_doc(d)
    for lw in section(doc, "laws")["laws"]:
        if lw["id"] in UNPROVEN:
            lw["evidence"] = {"tag": "to_run"}
    return doc


@contextlib.contextmanager
def fresh_copy():
    with tempfile.TemporaryDirectory(prefix="g10-test-") as tmp:
        dst = os.path.join(tmp, "v9")
        shutil.copytree(V9_DIR, dst, ignore=shutil.ignore_patterns("mutants"))
        yield dst


def law(doc, id):
    return next(x for x in section(doc, "laws")["laws"] if x["id"] == id)


def run_(doc, id):
    return next(x for x in section(doc, "receipts")["runs"] if x["id"] == id)


def model_(doc, id):
    return next(x for x in section(doc, "model")["models"] if x["id"] == id)


def closure(doc):
    return section(doc, "closure")["closures"][0]


def scn(doc, id):
    return next(x for x in section(doc, "scenarios")["scenarios"] if x["id"] == id)


def atom_(model, name):
    return next(a for a in model["atoms"] if a["name"] == name)


def judged(doc: dict, sid: str, **over) -> None:
    sc = scn(doc, sid)
    run = run_(doc, sc["source_run"])
    model = model_(doc, run["model_id"])
    trace = next(a for a in run["artifacts"] if a["role"] == "trace")
    r = {
        "tag": "judged",
        "by": "ale",
        "judgment": "correct",
        "model_identity": T.sha256_text(model["text"]),
        "trace_identity": trace["sha256"],
    }
    r.update(over)
    sc["review"] = r


def authored_run(rid: str, **over) -> dict:
    r = {
        "id": rid,
        "tool": "quint_run",
        "tool_version": "quint 0.32.0",
        "target": "model",
        "variant": "base",
        "argv": ["quint", "run", "x.qnt"],
        "exit_status": 0,
        "result_class": "ok",
        "checks": [],
    }
    r.update(over)
    return r


def _rewrite_trace(raw: bytes, status: str | None) -> bytes:
    if status is None:
        return raw
    tr = json.loads(raw)
    tr["#meta"]["status"] = status
    return json.dumps(tr).encode()


def clone_run(
    doc: dict, d: str, src: str, new: str, trace_status: str | None = None, **over
) -> dict:
    """A second run with its OWN kept files (one file is cited by one run only): output and trace are copied under the new id."""
    twin = copy.deepcopy(run_(doc, src))
    twin["id"] = new
    for a in twin.get("artifacts", []):
        with open(os.path.join(d, a["path"]), "rb") as fh:
            raw = fh.read()
        a["path"] = (
            f"artifacts/{new}.out"
            if a["role"] == "output"
            else f"traces/{new}.itf.json"
        )
        if a["role"] == "trace":
            raw = _rewrite_trace(raw, trace_status)
        with open(os.path.join(d, a["path"]), "wb") as fh:
            fh.write(raw)
        a["sha256"] = T.sha256_bytes(raw)
    twin.update(over)
    section(doc, "receipts")["runs"].append(twin)
    return twin


def set_trace_status(doc: dict, d: str, run_id: str, status: str) -> None:
    """Rewrite the kept trace of a run in place with another `#meta.status`, and keep the receipt honest about its hash."""
    for a in run_(doc, run_id)["artifacts"]:
        if a["role"] == "trace":
            with open(os.path.join(d, a["path"]), "rb") as fh:
                raw = _rewrite_trace(fh.read(), status)
            with open(os.path.join(d, a["path"]), "wb") as fh:
                fh.write(raw)
            a["sha256"] = T.sha256_bytes(raw)


# --------------------------------------------------------------------------- random well-formed values, derived from the types
WORDS = ["alpha", "beta gamma", "delta", "\u00e9t\u00e9\n", "x"]


def rstr(rng: random.Random) -> str:
    return f"{rng.choice(WORDS)}{rng.randint(0, 99)}"


def rand(
    tp: t.Any, rng: random.Random, meta: t.Mapping[str, t.Any] | None = None
) -> t.Any:
    meta = meta or {}
    o = t.get_origin(tp)
    if o is t.Union or o is types.UnionType:
        args = t.get_args(tp)
        if type(None) in args and rng.random() < 0.4:
            return None
        return rand(rng.choice([a for a in args if a is not type(None)]), rng, meta)
    if o is t.Literal:
        return rng.choice(t.get_args(tp))
    if o is tuple:
        n = rng.randint(1 if meta.get("nonempty") else 0, 3)
        return tuple(rand(t.get_args(tp)[0], rng) for _ in range(n))
    if isinstance(tp, t.NewType):
        return {
            "ID": lambda: f"I{rng.randint(0, 9)}",
            "Locator": lambda: f"f{rng.randint(0, 2)}.py::s{rng.randint(0, 3)}",
            "RelPath": lambda: f"d/f{rng.randint(0, 3)}.txt",
            "Sha": lambda: "".join(rng.choice("0123456789abcdef") for _ in range(64)),
        }[tp.__name__]()
    if tp is str:
        if "pattern" in meta:
            return rng.choice(["base", "fairness", "mutant:M1"])
        return rstr(rng)
    if tp is int:
        return rng.randint(1, 9) if meta.get("positive") else rng.randint(-3, 9)
    if tp is float:
        return rng.random() * 10
    if dc.is_dataclass(tp):
        hints = t.get_type_hints(tp)
        return tp(
            **{
                f.name: rand(hints[f.name], rng, f.metadata)
                for f in dc.fields(tp)
                if f.name != "tag"
            }
        )
    raise TypeError(tp)


def random_handoff(rng: random.Random) -> T.Handoff:
    h: T.Handoff = {}
    for kind in T.KINDS:
        for scope in ("shared", "value:1", "value:2"):
            if scope != "shared" and rng.random() < 0.5:
                continue
            na = rng.random() < 0.15
            status = (
                T.NotApplicable(reason=rstr(rng))
                if na
                else T.Applicable(payload=rand(T.PAYLOAD[kind], rng))
            )
            h[(kind, scope)] = T.Entry(kind=kind, scope=scope, status=status)
    return h


SEEDS = range(30)
TARGETS = ["f0.py", "f1.py", "f2.py"]


def shuffled(o, rng, key=None):
    """Every list is a set except argv: shuffle them all."""
    if isinstance(o, dict):
        return {k: shuffled(v, rng, k) for k, v in o.items()}
    if isinstance(o, list):
        items = [shuffled(x, rng) for x in o]
        if key not in T.SEQUENCE_FIELDS:
            rng.shuffle(items)
        return items
    return o


def doubled(o, key=None):
    """Every set of the document written twice (argv and the list of sections excepted): a repeat must change nothing."""
    if isinstance(o, dict):
        return {k: doubled(v, k) for k, v in o.items()}
    if isinstance(o, list):
        items = [doubled(x) for x in o]
        return (
            items
            if key in T.SEQUENCE_FIELDS or key == "sections"
            else items + copy.deepcopy(items)
        )
    return o


def perturb(h: T.Handoff, key) -> T.Handoff:
    return C.replace(
        h,
        T.Entry(
            kind=key[0],
            scope=key[1],
            status=T.NotApplicable(reason="perturbed " + "/".join(key)),
        ),
    )


# =========================================================================== fixtures
class Fixtures(unittest.TestCase):
    def test_minimal_and_oo_examples_have_no_defect(self):
        self.assertEqual([], defects(read(MINIMAL), ["clamp.py"], base=FIX))
        self.assertEqual([], defects(read(OO), OO_TARGETS, base=FIX))

    def test_v9lb1_has_exactly_eight_laws_called_executed_without_the_runs_that_prove_them(
        self,
    ):
        doc = v9_doc(V9_DIR)
        ds = defects(doc, V9_TARGETS, base=V9_DIR)
        self.assertEqual(
            {("L5", f"laws:{i}") for i in UNPROVEN}, {(d.rule, d.where) for d in ds}
        )
        self.assertEqual(8, len(ds))

    def test_v9lb1_is_clean_once_those_eight_are_not_claimed_as_executed(self):
        with fresh_copy() as d:
            self.assertEqual([], defects(base_doc(d), V9_TARGETS, base=d))

    def test_the_kept_files_are_the_ones_the_receipts_name(self):
        doc = v9_doc(V9_DIR)
        runs = section(doc, "receipts")["runs"]
        kept = [a for r in runs for a in r.get("artifacts", [])]
        self.assertGreater(len(kept), 30)
        for a in kept:
            with open(os.path.join(V9_DIR, a["path"]), "rb") as fh:
                self.assertEqual(a["sha256"], T.sha256_bytes(fh.read()), a["path"])
        self.assertEqual(
            len(runs),
            sum(1 for r in runs if r.get("artifacts"))
            + sum(1 for r in runs if not r.get("artifacts")),
        )

    def test_the_kill_matrix_the_architect_wrote_was_reproduced_by_real_quint_runs(
        self,
    ):
        doc = v9_doc(V9_DIR)
        got = {
            (k["property"], mu["id"])
            for mu in model_(doc, "walk")["mutants"]
            for k in mu["kills"]
        }
        self.assertEqual(15, len(got))
        for mu in model_(doc, "walk")["mutants"]:
            for k in mu["kills"]:
                r = run_(doc, k["run"])
                self.assertEqual(
                    ("violation", 1, f"mutant:{mu['id']}", [k["property"]]),
                    (r["result_class"], r["exit_status"], r["variant"], r["checks"]),
                )
                self.assertTrue(r["artifacts"], "a kill is a measurement, not a claim")


# =========================================================================== generator
class Generated(unittest.TestCase):
    def test_random_handoffs_decode(self):
        for s in SEEDS:
            h = random_handoff(random.Random(s))
            self.assertTrue(h)
            decode(C.to_json(h))

    def test_check_and_every_projection_are_total_over_random_handoffs(self):
        for s in SEEDS:
            h = decode(C.to_json(random_handoff(random.Random(s))))
            RU.check(h, TARGETS, "auto", None)
            for role in P.ROLES:
                P.compose(role, h, "T", targets=TARGETS)
            P.render_markdown(h)
            P.render_html(h)
            P.summary(h)


# =========================================================================== algebra
class Algebra(unittest.TestCase):
    def test_round_trip_and_canonical_idempotence(self):
        for s in SEEDS:
            h = random_handoff(random.Random(s))
            j = C.to_json(h)
            h2 = decode(j)
            self.assertEqual(C.to_json(h), C.to_json(h2), f"seed {s}")
            self.assertEqual(j, C.to_json(h2), f"seed {s}")

    def test_set_order_changes_neither_identity_nor_any_prompt_but_argv_order_does(
        self,
    ):
        for s in SEEDS:
            j = C.to_json(random_handoff(random.Random(s)))
            h1, h2 = decode(j), decode(shuffled(j, random.Random(1000 + s)))
            self.assertEqual(C.to_json(h1), C.to_json(h2), f"seed {s}")
            for role in P.ROLES:
                self.assertEqual(
                    P.compose(role, h1, "T", {"k": "v"}, targets=TARGETS),
                    P.compose(role, h2, "T", {"k": "v"}, targets=TARGETS),
                    f"seed {s} role {role}",
                )
        doc = read(MINIMAL)
        runs = section(doc, "receipts")["runs"]
        before = C.to_json(decode(doc))
        runs[0]["argv"] = list(reversed(runs[0]["argv"]))
        self.assertNotEqual(before, C.to_json(decode(doc)))

    def test_a_repeated_item_in_a_set_does_not_change_identity(self):
        doc = read(OO)
        before = C.to_json(decode(doc))
        c = section(doc, "construction")["claims"][0]
        c["bypass"] = c["bypass"] + [c["bypass"][0]]
        self.assertEqual(before, C.to_json(decode(doc)))

    def test_a_repeat_of_every_set_item_changes_no_byte_of_any_prompt(self):
        for s in SEEDS:
            j = C.to_json(random_handoff(random.Random(s)))
            h1, h2 = decode(j), decode(doubled(j))
            self.assertEqual(C.to_json(h1), C.to_json(h2), f"seed {s}")
            for role in P.ROLES:
                self.assertEqual(
                    P.compose(role, h1, "T", targets=TARGETS),
                    P.compose(role, h2, "T", targets=TARGETS),
                    f"seed {s} role {role}",
                )

    def test_merge_is_a_partial_disjoint_union(self):
        for s in SEEDS:
            rng = random.Random(s)
            h = decode(C.to_json(random_handoff(rng)))
            keys = sorted(h)
            rng.shuffle(keys)
            c1, c2 = sorted(rng.randint(0, len(keys)) for _ in range(2))
            a, b, c = (
                {k: h[k] for k in keys[x:y]}
                for x, y in ((0, c1), (c1, c2), (c2, len(keys)))
            )
            whole = C.to_json(h)
            self.assertEqual(whole, C.to_json(C.merge(C.merge(a, b), c)))
            self.assertEqual(whole, C.to_json(C.merge(a, C.merge(b, c))))
            self.assertEqual(whole, C.to_json(C.merge(C.merge(c, b), a)))
            self.assertEqual(C.to_json(a), C.to_json(C.merge(a, a)))

    def test_merge_refuses_two_contents_for_one_key_with_what_why_how_and_replace_is_explicit(
        self,
    ):
        h = decode(C.to_json(random_handoff(random.Random(5))))
        k = sorted(h)[0]
        other = T.Entry(
            kind=k[0], scope=k[1], status=T.NotApplicable(reason="a different content")
        )
        with self.assertRaises(C.MergeConflict) as cm:
            C.merge(h, {k: other})
        for word in ("WHAT:", "WHY:", "HOW:"):
            self.assertIn(word, str(cm.exception))
        self.assertTrue(cm.exception.defect.how)
        self.assertEqual(C.sha(other), C.sha(C.replace(h, other)[k]))

    def test_the_prompt_is_deterministic_and_independent_of_insertion_order(self):
        for s in SEEDS:
            h = decode(C.to_json(random_handoff(random.Random(s))))
            keys = list(h)
            random.Random(s).shuffle(keys)
            h2 = {k: h[k] for k in keys}
            for role in P.ROLES:
                self.assertEqual(
                    P.compose(role, h, "T", {"a": "1"}, "v", targets=TARGETS),
                    P.compose(role, h2, "T", {"a": "1"}, "v", targets=TARGETS),
                )

    def test_the_orchestrator_context_and_template_reach_every_role(self):
        h = decode(C.to_json(random_handoff(random.Random(1))))
        for role in P.ROLES:
            out = P.compose(
                role,
                h,
                "TEMPLATE-WHAT",
                {"issue": "CONTEXT-7"},
                "VERBATIM-9",
                targets=TARGETS,
            )
            for needle in ("TEMPLATE-WHAT", "CONTEXT-7", "VERBATIM-9"):
                self.assertIn(needle, out, role)


# =========================================================================== projection
class Projection(unittest.TestCase):
    def test_complete_and_local_per_role(self):
        for s in SEEDS:
            h = decode(C.to_json(random_handoff(random.Random(s))))
            for role in P.ROLES:
                base = P.compose(role, h, "T", targets=TARGETS)
                for key in sorted(h):
                    after = P.compose(role, perturb(h, key), "T", targets=TARGETS)
                    self.assertEqual(
                        key[0] in P.CONSUMERS[role],
                        base != after,
                        f"seed {s} role {role} entry {key}",
                    )

    def test_value_scope_locality_including_a_value_that_prefixes_another(self):
        for s in SEEDS:
            j = C.to_json(random_handoff(random.Random(s)))
            j["sections"].append(
                {
                    "kind": "laws",
                    "scope": "value:10",
                    "status": {"tag": "not_applicable", "reason": "ten"},
                }
            )
            h = decode(j)
            for key in sorted(h):
                if key[1] not in ("value:2", "value:10"):
                    continue
                for role in P.ROLES:
                    self.assertEqual(
                        P.compose(role, h, "T", value=1, targets=TARGETS),
                        P.compose(role, perturb(h, key), "T", value=1, targets=TARGETS),
                        f"seed {s} role {role} entry {key}",
                    )

    def test_the_examiner_receives_the_same_prompt_whatever_the_design(self):
        outs = {
            P.compose(
                "examiner",
                decode(C.to_json(random_handoff(random.Random(s)))),
                "WHAT",
                {"k": "v"},
            )
            for s in SEEDS
        }
        self.assertEqual(1, len(outs))

    def test_a_consumed_section_that_is_missing_arrives_as_unassessed_never_as_silence(
        self,
    ):
        h = decode(C.to_json(random_handoff(random.Random(4))))
        for key in list(h):
            if key[1] == "shared" and key[0] in ("laws", "closure"):
                del h[key]
        self.assertIn("UNASSESSED", P.compose("atd", h, "T", targets=TARGETS))
        self.assertNotIn("UNASSESSED", P.compose("examiner", h, "T"))

    def test_the_header_hash_is_the_hash_of_what_is_shown_so_a_hidden_field_leaves_the_bytes_alone(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            h1 = decode(doc)
            law(doc, "L1")["treatment"]["independent_observation"] = (
                "a different reference"
            )
            h2 = decode(doc)
            self.assertEqual(
                P.compose("software_crafter", h1, "T", targets=["pagination.py"]),
                P.compose("software_crafter", h2, "T", targets=["pagination.py"]),
            )
            self.assertNotEqual(
                P.compose("atd", h1, "T", targets=["pagination.py"]),
                P.compose("atd", h2, "T", targets=["pagination.py"]),
            )

    def test_an_owned_view_without_targets_is_refused_not_silently_widened(self):
        h = decode(read(OO))
        with self.assertRaises(P.ProjectionError) as cm:
            P.compose("software_crafter", h, "T")
        d = cm.exception.defect
        self.assertTrue(d.what and d.why and d.how)
        self.assertIn("--targets", d.how)

    def test_the_owned_view_keeps_what_the_targets_own_constructed_or_consume(self):
        h = decode(read(OO))
        only_inventory = json.dumps(
            P.project(h, "software_crafter", targets=["inventory.py"])
        )
        only_store = json.dumps(P.project(h, "software_crafter", targets=["store.py"]))
        only_units = json.dumps(P.project(h, "software_crafter", targets=["units.py"]))
        self.assertIn(
            '"id": "E1"', only_inventory.replace('"id":"', '"id": "')
        )  # inventory.py consumes E1
        self.assertIn('"E2"', only_store)  # store.py is the consumer of E2
        self.assertNotIn('"E2"', only_units)
        self.assertNotIn('"L1"', only_units)  # L1 is owned by inventory.py

    def test_the_equality_never_names_an_observation_the_view_dropped(self):
        doc = read(OO)
        laws_section = section(doc, "laws")
        laws_section["observations"].append(
            {
                "id": "O3",
                "description": "the length of the audit log",
                "result_type": "int >= 0",
                "cannot_distinguish": "which command wrote an entry",
            }
        )
        laws_section["equality"]["under"].append(
            "O3"
        )  # declared and named by the equality, used by no law
        h = decode(doc)
        for tg in (["inventory.py"], ["units.py"], OO_TARGETS):
            laws = next(
                c
                for k, s, _, v, c in P.project(h, "software_crafter", targets=tg)
                if k == "laws"
            )
            if "equality" in laws:
                shown = {o["id"] for o in laws["observations"]}
                self.assertLessEqual(set(laws["equality"]["under"]), shown, tg)
                self.assertTrue(laws["equality"]["under"], tg)

    def test_the_human_reads_rendered_scenarios_with_the_identities_to_judge_against_and_no_model_text(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
            out = P.compose("human", h, "T", base_dir=d)
            doc = base_doc(d)
            walk = model_(doc, "walk")
            self.assertIn("A list with 6 item(s) is read in pages of 1", out)
            self.assertIn(
                T.sha256_text(walk["text"]), out
            )  # model identity to judge against
            self.assertIn("trace_identity", out)
            self.assertNotIn(
                "module pagination_walk", out
            )  # the human never reads Quint
            self.assertIn("what_the_bug_does", out)

    def test_the_atd_reviewer_judges_the_same_facts_the_atd_was_given(self):
        with fresh_copy() as d:
            h = decode(base_doc(d))
            self.assertEqual(
                P.project(h, "atd", targets=V9_TARGETS),
                P.project(h, "atd_reviewer", targets=V9_TARGETS),
            )

    def test_no_consumer_row_claims_a_role_may_run_commands_it_is_forbidden_to_run(
        self,
    ):
        for role, rows in P.CONSUMERS.items():
            for kind, (_view, decision, basis) in rows.items():
                self.assertNotIn("re-run", decision, (role, kind))
                self.assertTrue(basis.strip(), (role, kind))

    def test_describe_names_every_record_of_the_grammar(self):
        text = P.describe_types()
        seen: dict = {}
        for cls in T.PAYLOAD.values():
            P._reachable(cls, seen)
        for name in seen:
            self.assertIn(f"\n{name} {{", "\n" + text)

    def test_the_architect_prompt_carries_the_grammar_and_every_rule(self):
        out = P.grammar_what("architect")
        for rid in RU.RULES:
            self.assertIn(f"- {rid}:", out)
        self.assertIn("g10.py run", out)


# =========================================================================== OO and procedural crafter
class ObjectOriented(unittest.TestCase):
    def setUp(self):
        self.h = decode(read(OO))

    def test_a_crafter_receives_only_what_its_declared_targets_own(self):
        a = P.compose("software_crafter", self.h, "T", targets=["units.py"])
        b = P.compose("software_crafter", self.h, "T", targets=OO_TARGETS)
        self.assertLess(len(a), len(b))
        self.assertNotIn("available() == capacity", a)
        self.assertIn("available() == capacity", b)

    def test_the_crafter_gets_the_law_not_how_it_is_tested_and_the_oracle_author_gets_both(
        self,
    ):
        crafter = P.compose("software_crafter", self.h, "T", targets=OO_TARGETS)
        for hidden in (
            '"treatment"',
            '"evidence"',
            '"generators"',
            '"refuted"',
            '"unknown"',
            "recount of ACTIVE reservations",
            "seeded, 500 sequences",
        ):
            self.assertNotIn(hidden, crafter, hidden)
        for shown in (
            '"statement":"available() ==',
            '"owner":"inventory.py::Inventory"',
            '"kind":"invariant"',
            '"bypass"',
            '"strength":"centralised"',
        ):
            self.assertIn(shown, crafter, shown)
        atd = P.compose("atd", self.h, "T", targets=OO_TARGETS)
        for shown in (
            '"treatment"',
            '"generators"',
            "recount of ACTIVE reservations",
            "seeded, 500 sequences",
            '"unknown"',
        ):
            self.assertIn(shown, atd, shown)

    def test_both_crafters_get_the_same_data_and_differ_only_in_the_what(self):
        for targets in (["units.py"], ["inventory.py"], OO_TARGETS):
            sw = P.compose("software_crafter", self.h, "T", targets=targets)
            fn = P.compose("functional_crafter", self.h, "T", targets=targets)
            self.assertEqual(sw.split("=== [H]", 1)[1], fn.split("=== [H]", 1)[1])
            self.assertNotEqual(sw.split("=== [H]")[0], fn.split("=== [H]")[0])

    def test_the_oo_example_needs_no_formal_model_and_still_states_the_four_claims(
        self,
    ):
        self.assertEqual([], defects(read(OO), OO_TARGETS, base=FIX))
        s = P.summary(self.h)
        self.assertEqual(4, s["claims"]["PASS"] + s["claims"]["NOT_APPLICABLE"])
        self.assertEqual(0, s["proofs"]["passed"])


# =========================================================================== renderer and ITF
def itf(status: str, states: list[tuple[str | None, dict]]) -> dict:
    return {
        "#meta": {"format": "ITF", "status": status},
        "vars": [],
        "states": [
            {
                "#meta": {"index": i},
                **{k: {"#bigint": str(v)} for k, v in vs.items()},
                **({"mbt::actionTaken": a} if a else {}),
                "mbt::nondetPicks": {},
            }
            for i, (a, vs) in enumerate(states)
        ],
    }


class Renderer(unittest.TestCase):
    def test_a_real_quint_trace_parses_and_prints_deterministically(self):
        tr = I.load(os.path.join(V9_DIR, "traces", "EX1.itf.json"))
        self.assertEqual("ok", tr.status)
        self.assertEqual(
            ["init", "step", "step", "step", "step", "probeEnd"],
            [s.action for s in tr.states],
        )
        self.assertEqual(
            I.fmt(tr.states[2].vars["count"]),
            I.fmt(
                I.load(os.path.join(V9_DIR, "traces", "EX1.itf.json"))
                .states[2]
                .vars["count"]
            ),
        )
        self.assertEqual(
            "{0 -> 1, 1 -> 1, 2 -> 0, 3 -> 0, 4 -> 0, 5 -> 0}",
            I.fmt(tr.states[2].vars["count"]),
        )

    def test_formatting_sorts_sets_and_maps_so_the_text_never_depends_on_trace_order(
        self,
    ):
        a = I.QSet([3, 1, 2])
        b = I.QSet([2, 3, 1])
        self.assertEqual(I.fmt(a), I.fmt(b))
        self.assertEqual("{1, 2, 3}", I.fmt(a))
        self.assertEqual(
            I.fmt(I.QMap([(2, 0), (1, 5)])), I.fmt(I.QMap([(1, 5), (2, 0)]))
        )
        self.assertEqual(
            "{2, 10}", I.fmt(I.QSet([10, 2]))
        )  # numbers sort as numbers, not as text
        self.assertEqual(
            I.fmt(I.QSet(["b", "a"])), I.fmt(I.QSet(["a", "b"]))
        )  # a set of anything else sorts by its printed form

    def test_a_scenario_is_rendered_from_the_trace_with_before_and_after_values(self):
        with fresh_copy() as d:
            h = decode(base_doc(d))
            v = S.visible(h, "shared")
            sc = next(
                s
                for (k, _), e in h.items()
                if k == "scenarios"
                for s in e.status.payload.scenarios
                if s.id == "SC2"
            )
            r = R.render_scenario(v, sc, d)
            self.assertIsInstance(r, R.Rendered)
            self.assertEqual(
                "A list with 4 item(s) is read in pages of 1, starting at offset 0",
                r.events[0][1],
            )
            self.assertIn(
                "starts at offset 1 (page size 1) and moves on to offset 2",
                r.events[2][1],
            )
            self.assertEqual(r.events, R.render_scenario(v, sc, d).events)

    def test_a_counterexample_run_ends_with_the_property_that_failed_in_domain_words(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
            sc = next(
                s
                for (k, _), e in h.items()
                if k == "scenarios"
                for s in e.status.payload.scenarios
                if s.id == "SC1"
            )
            r = R.render_scenario(S.visible(h, "shared"), sc, d)
            self.assertIn(
                "The check fails in this state: the page the code returns equals the filter definition",
                r.events[-1][1],
            )

    def test_an_action_the_model_does_not_cover_is_reported_never_narrated(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            atom_(model_(doc, "walk"), "probeEnd")["name"] = "renamed"
            ds = defects(doc, V9_TARGETS, base=d)
            self.assertEqual({"S3"}, {x.rule for x in ds})
            self.assertIn("probeEnd", ds[0].what)

    def test_a_trace_written_without_mbt_names_no_action_and_is_refused_with_the_fix(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            path = os.path.join(d, "traces", "EX1.itf.json")
            raw = json.load(open(path))
            for s in raw["states"]:
                s.pop("mbt::actionTaken")
            self.write_trace(doc, d, "EX1", raw)
            ds = defects(doc, V9_TARGETS, base=d)
            self.assertEqual({"S3"}, {x.rule for x in ds})
            self.assertIn("--mbt", ds[0].how)

    def write_trace(self, doc, d, run_id, raw):
        path = os.path.join(d, "traces", f"{run_id}.itf.json")
        with open(path, "w") as fh:
            json.dump(raw, fh)
        digest = T.sha256_bytes(open(path, "rb").read())
        for a in run_(doc, run_id)["artifacts"]:
            if a["role"] == "trace":
                a["sha256"] = digest

    def test_a_pre_placeholder_on_a_first_state_is_refused(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            raw = {
                "#meta": {"status": "ok"},
                "vars": [],
                "states": [
                    {
                        "#meta": {"index": 0},
                        "offset": {"#bigint": "0"},
                        "n": {"#bigint": "1"},
                        "lim": {"#bigint": "1"},
                        "mbt::actionTaken": "move",
                    }
                ],
            }
            self.write_trace(doc, d, "EX1", raw)
            ds = defects(doc, V9_TARGETS, base=d)
            self.assertEqual({"S3"}, {x.rule for x in ds})
            self.assertIn("offset@pre", ds[0].what)

    def test_html_view_is_self_contained_and_escapes_everything(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            scn(doc, "SC1")["title"] = "<script>alert(1)</script> & co"
            out = P.render_html(decode(doc), d)
            self.assertNotIn("<script>", out)
            self.assertIn("&lt;script&gt;", out)
            self.assertNotIn("http", out)
            self.assertEqual(out, P.render_html(decode(doc), d))

    def test_quint_scenarios_has_the_shape_discuss_already_records(self):
        with fresh_copy() as d:
            h = decode(base_doc(d))
            v = S.visible(h, "shared")
            items = [
                R.render_scenario(v, s, d)
                for (k, _), e in sorted(h.items())
                if k == "scenarios"
                for s in e.status.payload.scenarios
            ]
            q = R.quint_scenarios([i for i in items if isinstance(i, R.Rendered)])
            self.assertEqual({"status", "model", "tool", "trace", "scenarios"}, set(q))
            self.assertEqual({"path", "identity"}, set(q["model"]))
            self.assertEqual({"name", "version", "command"}, set(q["tool"]))
            self.assertEqual({"title", "events"}, set(q["scenarios"][0]))
            self.assertEqual(
                {"trace_index", "text"}, set(q["scenarios"][0]["events"][0])
            )

    def test_every_itf_value_kind_prints_one_way(self):
        big = lambda n: {"#bigint": str(n)}  # noqa: E731
        tr = I.parse(
            {
                "#meta": {"status": "ok"},
                "states": [
                    {
                        "#meta": {"index": 0},
                        "b": True,
                        "c": False,
                        "n": big(-7),
                        "s": "x",
                        "set": {"#set": [big(2), big(1)]},
                        "map": {"#map": [["k", big(1)]]},
                        "tup": {"#tup": [big(1), "a"]},
                        "some": {"tag": "Some", "value": big(1)},
                        "none": {"tag": "None", "value": {"#tup": []}},
                        "list": [big(1), "b"],
                        "rec": {"b": big(1), "a": True},
                    }
                ],
            }
        )
        self.assertEqual(
            {
                "b": "true",
                "c": "false",
                "n": "-7",
                "s": "x",
                "set": "{1, 2}",
                "map": "{k -> 1}",
                "tup": "(1, a)",
                "some": "Some(1)",
                "none": "None",
                "list": "[1, b]",
                "rec": "{a: true, b: 1}",
            },
            {k: I.fmt(x) for k, x in tr.states[0].vars.items()},
        )

    def test_a_trace_with_no_state_is_a_problem_and_never_an_index_error(self):
        model = S.visible(decode(v9_doc(V9_DIR)), "shared").models["walk"]
        trace = I.parse({"#meta": {"status": "violation"}, "states": []})
        self.assertEqual(["the trace has no state"], R.trace_problems(model, trace))
        with self.assertRaises(ValueError):
            R.render_trace(model, trace, ["pageMatchesSpec"])

    def test_itf_parse_refuses_what_it_cannot_read_with_a_message(self):
        for bad in (
            None,
            [],
            {"states": 1},
            {"#meta": {}, "states": [5]},
            {"#meta": {}, "states": [{"#meta": {"index": 0}, "mbt::actionTaken": 3}]},
            {"#meta": {}, "states": [{"x": {"#bigint": "abc"}}]},
            {"#meta": {}, "states": [{"x": {"#map": [[1]]}}]},
        ):
            with self.assertRaises(I.ItfError, msg=str(bad)):
                I.parse(bad)


# =========================================================================== decode (shape)
class Decode(unittest.TestCase):
    def doc(self):
        return read(MINIMAL)

    def codes(self, doc):
        _, ds = C.decode_handoff(doc)
        for d in ds:
            self.assertTrue(d.what and d.why and d.how, d)
        return {d.rule for d in ds}

    def test_each_shape_defect_fires(self):
        def with_law(mut):
            d = self.doc()
            mut(section(d, "laws")["laws"][0])
            return d

        def with_generator(mut):
            d = self.doc()
            mut(section(d, "laws")["generators"][0])
            return d

        cases = {
            "G1": with_law(lambda lw: lw["treatment"].pop("tag")),
            "G2": with_law(lambda lw: lw.__setitem__("kind", "magic")),
            "G3": with_law(lambda lw: lw.__setitem__("statement", 7)),
            "G4": with_law(lambda lw: lw.__setitem__("extra", 1)),
            "G5": with_law(lambda lw: lw.pop("owner")),
            "G7": with_law(lambda lw: lw.__setitem__("statement", "  ")),
            "G8": with_law(lambda lw: lw.__setitem__("uses", [])),
            "G9": with_generator(lambda g: g.__setitem__("size_bound", 0)),
            "G10": with_law(lambda lw: lw.__setitem__("owner", "not a locator, prose")),
        }
        for code, d in cases.items():
            self.assertIn(code, self.codes(d), code)
        dup = self.doc()
        dup["sections"].append(copy.deepcopy(dup["sections"][0]))
        self.assertIn("G6", self.codes(dup))
        scope = self.doc()
        scope["sections"][0]["scope"] = "value:0"
        self.assertIn("G10", self.codes(scope))
        self.assertIn("G4", self.codes({"sections": [], "x": 1}))
        self.assertIn("G4", self.codes([]))
        missing = self.doc()
        missing["sections"][1]["status"] = {"tag": "not_applicable"}
        self.assertIn("G5", self.codes(missing))

    def test_a_blank_string_and_an_unknown_field_cannot_hide(self):
        d = self.doc()
        section(d, "laws")["observations"][0]["cannot_distinguish"] = ""
        self.assertIn("G7", self.codes(d))

    def test_every_shape_defect_is_collected_in_one_pass(self):
        d = self.doc()
        lw = section(d, "laws")["laws"][0]
        lw["kind"] = "magic"
        lw["statement"] = 3
        lw["owner"] = "prose, not a path"
        lw["bogus"] = 1
        _, ds = C.decode_handoff(d)
        self.assertGreaterEqual({x.rule for x in ds}, {"G2", "G3", "G4", "G10"})
        self.assertGreaterEqual(len(ds), 4)

    def test_a_trailing_newline_never_makes_a_value_valid(self):
        for mutate in (
            lambda d: d["sections"][0].__setitem__("scope", "shared\n"),
            lambda d: section(d, "laws")["laws"][0].__setitem__("id", "L1\n"),
            lambda d: section(d, "laws")["laws"][0].__setitem__(
                "owner", "clamp.py::clamp\n"
            ),
            lambda d: section(d, "receipts")["runs"][0].__setitem__(
                "variant", "fixed\n"
            ),
            lambda d: section(d, "receipts")["runs"][0].__setitem__("tool_version", ""),
        ):
            d = self.doc()
            mutate(d)
            self.assertTrue(
                self.codes(d), "a value with a trailing newline was accepted"
            )

    def test_locators_of_other_languages_are_accepted_and_traversal_is_not(self):
        ok = [
            "src/lib.rs::Foo::bar",
            "a.cpp::ns::Foo::bar",
            "src/app.ts::Foo#bar",
            "src/@scope/pkg/index.ts::Foo.bar",
            "src/a.js::$init",
            "src/mod.py:3:5",
            "pkg/x.py::f.<locals>.g",
            "x.py:3-9",
            "CREATE_NEW:new/mod.py::C.m",
            "plain.py",
        ]
        bad = [
            "../x.py",
            "/etc/passwd",
            "a/../b.py::f",
            "a b.py::f",
            "x.py::",
            "",
            "CREATE_NEW:",
            "x.py:abc",
        ]
        for loc in ok:
            d = self.doc()
            section(d, "laws")["laws"][0]["owner"] = loc
            self.assertNotIn("G10", self.codes(d), loc)
        for loc in bad:
            d = self.doc()
            section(d, "laws")["laws"][0]["owner"] = loc
            self.assertIn("G10", self.codes(d), loc)

    def test_text_file_is_confined_to_the_directory_of_the_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "side")
            Path(sub).mkdir(parents=True)
            secret = os.path.join(tmp, "secret.txt")
            open(secret, "w").write("outside")
            open(os.path.join(sub, "m.qnt"), "w").write("module m {}\n")
            for rel, expect_ok in (
                ("m.qnt", True),
                ("../secret.txt", False),
                (secret, False),
                (7, False),
            ):
                doc = {
                    "sections": [
                        {
                            "kind": "model",
                            "scope": "shared",
                            "status": {
                                "tag": "applicable",
                                "payload": {"models": [{"text_file": rel}]},
                            },
                        }
                    ]
                }
                ds = C.resolve_authoring(doc, sub)
                self.assertEqual(expect_ok, not ds, rel)
                if not expect_ok:
                    self.assertEqual("G11", ds[0].rule)
                    self.assertTrue(ds[0].how)

    def test_decode_never_raises_whatever_the_document_is(self):
        junk = [
            None,
            True,
            0,
            -1,
            10**40,
            1.5,
            float("nan"),
            float("inf"),
            "",
            "x\n",
            "A" * 5000,
            [],
            {},
            [[]],
            {"tag": "x"},
            {"tag": None},
        ]
        for base in (read(MINIMAL), read(OO), v9_doc(V9_DIR)):
            for s in range(150):
                rng = random.Random(s)
                doc = copy.deepcopy(base)
                nodes: list = []

                def walk(o, nodes):
                    if isinstance(o, dict):
                        for k in list(o):
                            nodes.append((o, k))
                            walk(o[k], nodes)
                    elif isinstance(o, list):
                        for i in range(len(o)):
                            nodes.append((o, i))
                            walk(o[i], nodes)

                walk(doc, nodes)
                for _ in range(rng.randint(1, 3)):
                    holder, key = rng.choice(nodes)
                    try:
                        holder[key] = rng.choice(junk)
                    except (IndexError, KeyError):
                        pass
                h, ds = C.decode_handoff(doc)
                self.assertTrue(h is not None or ds, "no handoff and no defect")
                for d in ds:
                    self.assertTrue(d.what and d.why and d.how, d)
                if h is not None:
                    RU.check(h, V9_TARGETS, "auto", None)
                    for role in P.ROLES:
                        P.compose(role, h, "T", targets=V9_TARGETS)
                    P.render_markdown(h)
                    P.render_html(h)
                    P.summary(h)

    def test_reading_a_file_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp:

            def w(name, data: bytes):
                p = os.path.join(tmp, name)
                open(p, "wb").write(data)
                return p

            cases = [
                os.path.join(tmp, "missing.json"),
                w("empty.json", b""),
                w("bad.json", b"{not json"),
                w("bin.json", b"\xff\xfe\x00"),
                w("nan.json", b'{"sections": [], "x": NaN}'),
                w("dup.json", b'{"sections": [], "sections": []}'),
                w("deep.json", b"[" * 100000 + b"]" * 100000),
            ]
            for p in cases:
                doc, ds = C.load_json(p)
                self.assertIsNone(doc, p)
                self.assertEqual(["G12"], [d.rule for d in ds], p)
                self.assertTrue(ds[0].how)
            self.assertEqual(
                "G12", C.load_json(os.path.join(tmp, "dup.json"))[1][0].rule
            )
            doc, ds = C.load_json(w("ok.json", b'{"sections": []}'))
            self.assertEqual(({"sections": []}, []), (doc, ds))

    def test_a_non_finite_or_negative_duration_is_refused(self):
        for bad in (-5, float("nan"), float("inf")):
            d = self.doc()
            section(d, "receipts")["runs"][0]["duration_s"] = bad
            self.assertIn("G9", self.codes(d), bad)


# =========================================================================== every rule fires on one mutation, and only that rule
def _kill_of(doc, mutant, prop):
    return next(
        k
        for k in next(m for m in model_(doc, "walk")["mutants"] if m["id"] == mutant)[
            "kills"
        ]
        if k["property"] == prop
    )


def _drop_trace_file(doc, d):
    (Path(d) / "traces/K-M1-pageMatchesSpec.itf.json").unlink()


def _rename_action(doc, d):
    atom_(model_(doc, "walk"), "probeEnd")["name"] = "probeEnd2"


def _judge_wrong_model(doc, d):
    judged(doc, "SC1", model_identity="0" * 64)


CASES: dict[str, tuple[t.Callable, dict]] = {
    "X1": (
        lambda doc, d: doc.__setitem__(
            "sections", [s for s in doc["sections"] if s["kind"] != "scenarios"]
        ),
        {},
    ),
    "L1": (
        lambda doc, d: section(doc, "laws")["generators"].append(
            copy.deepcopy(section(doc, "laws")["generators"][0])
        ),
        {},
    ),
    "L2": (lambda doc, d: law(doc, "L1").__setitem__("uses", ["O1", "nope"]), {}),
    "L3": (lambda doc, d: section(doc, "laws")["equality"]["under"].append("O99"), {}),
    "L4": (lambda doc, d: law(doc, "L1").__setitem__("owner", "other.py::f"), {}),
    "L5": (
        lambda doc, d: law(doc, "L1").__setitem__(
            "evidence", {"tag": "executed", "receipts": ["LAWS-FIXED"]}
        ),
        {},
    ),
    "L6": (
        lambda doc, d: section(doc, "laws")["refuted"][0].__setitem__("run", "NOPE"),
        {},
    ),
    "L7": (
        lambda doc, d: law(doc, "L1")["treatment"].__setitem__("generator", "G-NOPE"),
        {},
    ),
    "C1": (
        lambda doc, d: section(doc, "construction")["claims"][1].__setitem__(
            "id", "E1"
        ),
        {},
    ),
    "C2": (
        lambda doc, d: section(doc, "construction")["claims"][0].__setitem__(
            "bypass", []
        ),
        {},
    ),
    "C3": (
        lambda doc, d: section(doc, "construction")["claims"][0].__setitem__(
            "owner", "x.py::f"
        ),
        {},
    ),
    "M1": (
        lambda doc, d: _kill_of(doc, "M2", "noSkipNoRepeat").__setitem__(
            "run", "K-M2-completeAtEnd"
        ),
        {},
    ),
    "M2": (
        lambda doc, d: atom_(model_(doc, "walk"), "move").__setitem__(
            "template", "The caller is at {nope}"
        ),
        {},
    ),
    "R1": (
        lambda doc, d: section(doc, "receipts")["runs"].append(
            copy.deepcopy(run_(doc, "BASELINE"))
        ),
        {},
    ),
    "R2": (lambda doc, d: run_(doc, "R4").__setitem__("exit_status", 1), {}),
    "R3": (lambda doc, d: run_(doc, "R1").__setitem__("model_id", "nope"), {}),
    "R4": (
        lambda doc, d: section(doc, "receipts")["runs"].append(
            authored_run(
                "RX",
                variant="mutant:NOPE",
                model_id="walk",
                exit_status=1,
                result_class="violation",
            )
        ),
        {},
    ),
    "R5": (lambda doc, d: run_(doc, "R4").__setitem__("model_sha256", "0" * 64), {}),
    "R6": (_drop_trace_file, {}),
    "CL1": (
        lambda doc, d: closure(doc)["safety"].__setitem__(
            "basis",
            {
                "tag": "path",
                "admitted_input": "i",
                "producer": "pagination.py::paginate",
                "consumer": "pagination.py:7",
                "public_observation": "o",
            },
        ),
        {},
    ),
    "CL2": (lambda doc, d: closure(doc)["safety"].__setitem__("design", "BLOCKED"), {}),
    "CL3": (
        lambda doc, d: closure(doc)["safety"].__setitem__(
            "runs", [r for r in closure(doc)["safety"]["runs"] if r not in ("R4", "R5")]
        ),
        {},
    ),
    "CL4": (
        lambda doc, d: model_(doc, "walk")["mutants"][-1].__setitem__(
            "kills",
            [
                k
                for k in model_(doc, "walk")["mutants"][-1]["kills"]
                if k["property"] != "bounded"
            ],
        ),
        {},
    ),
    "CL5": (lambda doc, d: closure(doc)["liveness"]["basis"].pop("fairness"), {}),
    "CL6": (lambda doc, d: closure(doc)["public_reachability"].pop("runtime_note"), {}),
    "CL7": (lambda doc, d: closure(doc)["safety"]["laws"].append("L99"), {}),
    "CL8": (
        lambda doc, d: closure(doc).__setitem__("liveness", {"tag": "inherited"}),
        {},
    ),
    "CL9": (
        lambda doc, d: closure(doc)["safety"].update(
            basis={"tag": "argued", "argument": "it is total"}, assumptions=[]
        ),
        {},
    ),
    "CL10": (
        lambda doc, d: section(doc, "closure")["closures"].append(
            copy.deepcopy(closure(doc))
        ),
        {},
    ),
    "S1": (lambda doc, d: judged(doc, "SC1"), {}),
    "S2": (lambda doc, d: scn(doc, "SC2").__setitem__("kind", "counterexample"), {}),
    "S3": (_rename_action, {}),
    "S4": (_judge_wrong_model, {"mode": "interactive"}),
    "S5": (lambda doc, d: scn(doc, "SC2").__setitem__("id", "SC1"), {}),
}


class EveryRuleFires(unittest.TestCase):
    def check_rule(self, rid: str):
        mutate, kw = CASES[rid]
        with fresh_copy() as d:
            doc = base_doc(d)
            mutate(doc, d)
            ds = defects(doc, V9_TARGETS, kw.get("mode", "auto"), d)
        self.assertEqual(
            {rid}, {x.rule for x in ds}, [f"{x.rule} {x.where} {x.what}" for x in ds]
        )
        for x in ds:
            self.assertTrue(x.what.startswith(RU.RULES[rid][0]), x.what)
            self.assertEqual(RU.RULES[rid][1], x.why)
            self.assertEqual(RU.RULES[rid][2], x.how)
            self.assertTrue(x.where)


def _rule_case(rid):
    return lambda self: self.check_rule(rid)


for _rid in RU.RULES:
    setattr(
        EveryRuleFires,
        f"test_{_rid}",
        _rule_case(_rid),
    )


class RulesAreComplete(unittest.TestCase):
    def test_every_rule_has_a_case_and_every_case_a_rule(self):
        self.assertEqual(set(RU.RULES), set(CASES))

    def test_every_rule_carries_what_why_how_and_a_source_that_names_its_related_gap_or_says_none(
        self,
    ):
        for rid, (what, why, how, src) in RU.RULES.items():
            self.assertTrue(
                what.strip() and why.strip() and how.strip() and src.strip(), rid
            )
            self.assertTrue("related gap:" in src or "no related gap" in src, rid)

    def test_the_rules_table_is_the_generated_file(self):
        self.assertEqual(
            open(os.path.join(ROOT, "rules.md"), encoding="utf-8").read().strip(),
            RU.rules_markdown().strip(),
        )


# =========================================================================== the HOW, applied literally, fixes the WHAT
class HowWorks(unittest.TestCase):
    def fix(self, mutate_bad, apply_how, **kw):
        with fresh_copy() as d:
            doc = base_doc(d)
            mutate_bad(doc, d)
            before = rule_ids(
                doc, kw.get("targets", V9_TARGETS), kw.get("mode", "auto"), d
            )
            self.assertTrue(before, "the bad document must be refused first")
            apply_how(doc, d)
            after = defects(
                doc, kw.get("targets", V9_TARGETS), kw.get("mode", "auto"), d
            )
            self.assertEqual([], [f"{x.rule} {x.where} {x.what}" for x in after])

    def test_L4_create_new_with_the_path_declared_as_a_target(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            law(doc, "L1")["owner"] = "CREATE_NEW:new_mod.py::Paginator"
            self.assertEqual({"L4"}, rule_ids(doc, V9_TARGETS, base=d))
            self.assertEqual(set(), rule_ids(doc, [*V9_TARGETS, "new_mod.py"], base=d))

    def test_L5_cite_receipts_whose_checks_name_the_law(self):
        def how(doc, d):
            runs = section(doc, "receipts")["runs"]
            runs += [
                authored_run(
                    "RL3-OK",
                    tool="script",
                    target="prototype",
                    variant="fixed",
                    checks=["L3"],
                ),
                authored_run(
                    "RL3-BAD",
                    tool="script",
                    target="implementation",
                    variant="unfixed",
                    checks=["L3"],
                    exit_status=1,
                    result_class="violation",
                ),
            ]
            law(doc, "L3")["evidence"] = {
                "tag": "executed",
                "receipts": ["RL3-OK", "RL3-BAD"],
            }

        self.fix(
            lambda doc, d: law(doc, "L3").__setitem__(
                "evidence",
                {"tag": "executed", "receipts": ["LAWS-FIXED", "LAWS-UNFIXED"]},
            ),
            how,
        )

    def test_L7_declare_the_generator(self):
        self.fix(
            lambda doc, d: law(doc, "L1")["treatment"].__setitem__(
                "generator", "G-NEW"
            ),
            lambda doc, d: section(doc, "laws")["generators"].append(
                {**copy.deepcopy(section(doc, "laws")["generators"][0]), "id": "G-NEW"}
            ),
        )

    def test_M1_cite_the_run_that_violates_that_property_for_that_mutant(self):
        def how(doc, d):
            section(doc, "receipts")["runs"].append(
                authored_run(
                    "K-new",
                    variant="mutant:M2",
                    model_id="walk",
                    exit_status=1,
                    result_class="violation",
                    checks=["noSkipNoRepeat"],
                    model_sha256="1" * 64,
                )
            )  # the sha256 of the mutant text
            _kill_of(doc, "M2", "noSkipNoRepeat")["run"] = "K-new"

        self.fix(
            lambda doc, d: _kill_of(doc, "M2", "noSkipNoRepeat").__setitem__(
                "run", "K-M2-completeAtEnd"
            ),
            how,
        )

    def test_R5_record_the_sha256_of_the_model_text(self):
        self.fix(
            lambda doc, d: run_(doc, "R4").__setitem__("model_sha256", "0" * 64),
            lambda doc, d: run_(doc, "R4").__setitem__(
                "model_sha256", T.sha256_text(model_(doc, "walk")["text"])
            ),
        )

    def test_CL2_write_the_design_note_for_a_blocked_claim(self):
        self.fix(
            lambda doc, d: closure(doc)["safety"].__setitem__("design", "BLOCKED"),
            lambda doc, d: closure(doc)["safety"].__setitem__(
                "design_note", "the check found a counterexample"
            ),
        )

    def test_CL3_when_the_checker_cannot_run_the_proof_is_indeterminate_and_the_design_may_stay_PASS(
        self,
    ):
        def bad(doc, d):
            closure(doc)["safety"]["runs"] = [
                r for r in closure(doc)["safety"]["runs"] if r not in ("R4", "R5")
            ]

        def how(doc, d):
            closure(doc)["safety"]["basis"].update(
                proof="indeterminate",
                proof_note="apalache needs a JVM that was not started in this run",
            )

        self.fix(bad, how)

    def test_CL5_state_the_fairness(self):
        self.fix(
            lambda doc, d: closure(doc)["liveness"]["basis"].pop("fairness"),
            lambda doc, d: closure(doc)["liveness"]["basis"].__setitem__(
                "fairness", "weakFair(step, vars)"
            ),
        )

    def test_CL6_write_the_runtime_note(self):
        self.fix(
            lambda doc, d: closure(doc)["public_reachability"].pop("runtime_note"),
            lambda doc, d: closure(doc)["public_reachability"].__setitem__(
                "runtime_note", "the second page is wrong until the fix"
            ),
        )

    def test_S2_a_bug_trace_is_a_mutant_scenario(self):
        self.fix(
            lambda doc, d: scn(doc, "SC1").__setitem__("kind", "counterexample"),
            lambda doc, d: scn(doc, "SC1").__setitem__("kind", "mutant"),
        )

    def test_S4_a_stale_judgment_is_regenerated_as_pending(self):
        self.fix(
            _judge_wrong_model,
            lambda doc, d: scn(doc, "SC1").__setitem__("review", {"tag": "pending"}),
            mode="interactive",
        )

    def test_S4_a_conditional_judgment_carries_its_note(self):
        self.fix(
            lambda doc, d: judged(doc, "SC1", judgment="depends"),
            lambda doc, d: scn(doc, "SC1")["review"].__setitem__(
                "note", "only when the list is empty"
            ),
            mode="interactive",
        )

    def test_S1_in_auto_mode_every_scenario_is_pending(self):
        self.fix(
            lambda doc, d: judged(doc, "SC1"),
            lambda doc, d: scn(doc, "SC1").__setitem__("review", {"tag": "pending"}),
        )

    def test_X1_an_absent_section_is_delivered_not_applicable_with_a_reason(self):
        self.fix(
            lambda doc, d: doc.__setitem__(
                "sections", [s for s in doc["sections"] if s["kind"] != "scenarios"]
            ),
            lambda doc, d: doc["sections"].append(
                {
                    "kind": "scenarios",
                    "scope": "shared",
                    "status": {"tag": "not_applicable", "reason": "order is clear"},
                }
            ),
        )

    def test_R6_run_the_command_again_restores_a_file_that_matches(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            path = os.path.join(d, "traces", "EX1.itf.json")
            open(path, "a").write(" ")  # changed after the run
            self.assertIn("R6", rule_ids(doc, V9_TARGETS, base=d))


# =========================================================================== defects the two independent reviewers found
class Docs:
    """Helpers for tests that change ONE field of a valid document and expect a rule to fire (or not)."""

    def refused(self, mutate, rule, **kw):
        with fresh_copy() as d:
            doc = base_doc(d)
            mutate(doc, d)
            ids = rule_ids(
                doc, kw.get("targets", V9_TARGETS), kw.get("mode", "auto"), d
            )
        self.assertIn(rule, ids)

    def accepted(self, mutate, **kw):
        with fresh_copy() as d:
            doc = base_doc(d)
            mutate(doc, d)
            self.assertEqual(
                [],
                [
                    f"{x.rule} {x.where}"
                    for x in defects(doc, V9_TARGETS, kw.get("mode", "auto"), d)
                ],
            )


class ReviewRegressions(Docs, unittest.TestCase):
    # --- a kill must be tied to the property it claims (BreakG10 D1)
    def test_kills_with_swapped_properties_are_refused(self):
        def swap(doc, d):
            _kill_of(doc, "M2", "noSkipNoRepeat")["run"] = "K-M2-completeAtEnd"
            _kill_of(doc, "M2", "completeAtEnd")["run"] = "K-M2-noSkipNoRepeat"

        self.refused(swap, "M1")

    def test_one_run_cited_as_the_kill_of_every_property_is_refused(self):
        def all_one(doc, d):
            for k in next(m for m in model_(doc, "walk")["mutants"] if m["id"] == "M1")[
                "kills"
            ]:
                k["run"] = "K-M1-pageMatchesSpec"

        self.refused(all_one, "M1")

    def test_a_kill_cited_from_another_model_is_refused(self):
        def other(doc, d):
            run_(doc, "K-M1-pageMatchesSpec")["model_id"] = "live"

        self.refused(other, "M1")

    def test_a_kill_run_that_is_not_a_model_run_is_refused(self):
        self.refused(
            lambda doc, d: run_(doc, "K-M1-pageMatchesSpec").__setitem__(
                "tool", "script"
            ),
            "M1",
        )

    # --- a scenario is read from a real trace of the right kind (BreakG10 D2)
    def test_a_mutant_trace_cannot_pass_for_a_counterexample_of_the_design(self):
        self.refused(
            lambda doc, d: scn(doc, "SC1").__setitem__("kind", "counterexample"), "S2"
        )

    def test_a_design_trace_cannot_pass_for_a_mutant(self):
        self.refused(lambda doc, d: scn(doc, "SC2").__setitem__("kind", "mutant"), "S2")

    def test_a_run_without_a_kept_trace_cannot_source_a_scenario(self):
        self.refused(
            lambda doc, d: run_(doc, "EX1").__setitem__(
                "artifacts",
                [a for a in run_(doc, "EX1")["artifacts"] if a["role"] != "trace"],
            ),
            "S2",
        )

    def test_a_witness_violation_is_a_valid_example(self):
        def witness(doc, d):
            r = run_(doc, "EX1")
            r.update(
                variant="witness",
                exit_status=1,
                result_class="violation",
                checks=["reachesEnd"],
            )
            set_trace_status(
                doc, d, "EX1", "violation"
            )  # a witness is a trace that ends in the reached state the check reported

        self.accepted(witness)

    def test_a_judgment_is_bound_to_the_exact_trace_too(self):
        self.refused(
            lambda doc, d: judged(doc, "SC1", trace_identity="0" * 64),
            "S4",
            mode="interactive",
        )

    def test_a_current_judgment_is_accepted_in_interactive_mode(self):
        self.accepted(
            lambda doc, d: judged(doc, "SC1", judgment="incorrect"), mode="interactive"
        )

    def test_a_scenario_cannot_cite_a_run_that_lives_in_another_value(self):
        def cross(doc, d):
            twin = copy.deepcopy(run_(doc, "EX1"))
            twin["id"] = (
                "W2"  # a good run, kept with its trace, that belongs to value 2
            )
            doc["sections"] = [s for s in doc["sections"] if s["kind"] != "scenarios"]
            doc["sections"].append(
                {
                    "kind": "scenarios",
                    "scope": "shared",
                    "status": {"tag": "not_applicable", "reason": "see the values"},
                }
            )
            doc["sections"].append(
                {
                    "kind": "scenarios",
                    "scope": "value:1",
                    "status": {
                        "tag": "applicable",
                        "payload": {
                            "scenarios": [
                                {
                                    "id": "SV1",
                                    "title": "t",
                                    "source_run": "W2",
                                    "kind": "example",
                                    "review": {"tag": "pending"},
                                }
                            ]
                        },
                    },
                }
            )
            doc["sections"].append(
                {
                    "kind": "receipts",
                    "scope": "value:2",
                    "status": {"tag": "applicable", "payload": {"runs": [twin]}},
                }
            )

        self.refused(cross, "S2")

    # --- receipts must be about the law (BreakG10 D3)
    def test_a_probe_and_a_run_of_other_laws_do_not_back_a_law(self):
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "evidence", {"tag": "executed", "receipts": ["P-QUINT", "LAWS-UNFIXED"]}
            ),
            "L5",
        )
        self.refused(
            lambda doc, d: law(doc, "L3").__setitem__(
                "evidence",
                {"tag": "executed", "receipts": ["LAWS-FIXED", "LAWS-UNFIXED"]},
            ),
            "L5",
        )

    # --- omitting the closure is refused (BreakG10 D4)
    def test_no_closure_section_is_refused_even_when_there_is_no_model(self):
        def drop(doc, d):
            doc["sections"] = [s for s in doc["sections"] if s["kind"] != "closure"]
            for s in doc["sections"]:
                if s["kind"] == "model":
                    s["status"] = {"tag": "not_applicable", "reason": "no formal model"}

        self.refused(drop, "X1")

    # --- the check on where a value is cut (BreakG10 D5, D8)
    def test_a_scope_with_a_trailing_newline_cannot_hide_a_second_section(self):
        doc = read(MINIMAL)
        doc["sections"].append(
            {**copy.deepcopy(doc["sections"][-1]), "scope": "shared\n"}
        )
        self.assertIn("G10", {d.rule for d in C.decode_handoff(doc)[1]})

    def test_a_law_id_with_a_trailing_newline_is_not_an_id(self):
        doc = read(MINIMAL)
        section(doc, "laws")["laws"][0]["id"] = "L1\n"
        self.assertIn("G10", {d.rule for d in C.decode_handoff(doc)[1]})

    def test_an_owner_must_be_a_declared_path_not_a_prefix_of_one(self):
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "owner", "pagination.pyc::paginate"
            ),
            "L4",
        )
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "owner", "pagination.p::paginate"
            ),
            "L4",
        )

    # --- the four design axes (SourceCheckG10 D1)
    def test_an_unexecuted_checker_leaves_only_the_proof_indeterminate_and_never_blocks_the_design(
        self,
    ):
        def indeterminate(doc, d):
            c = closure(doc)["safety"]
            c["runs"] = []
            c["basis"].update(
                proof="indeterminate",
                proof_note="quint verify needs the Apalache JVM, which could not start",
            )

        self.accepted(indeterminate)
        self.refused(
            lambda doc, d: closure(doc)["safety"]["basis"].update(
                proof="indeterminate"
            ),
            "CL3",
        )  # the note is required

    def test_a_pass_on_a_refuted_proof_is_refused_and_a_blocked_design_on_a_counterexample_is_accepted(
        self,
    ):
        self.refused(
            lambda doc, d: closure(doc)["safety"]["basis"].update(
                proof="refuted", proof_note="counterexample"
            ),
            "CL2",
        )

        def blocked(doc, d):
            c = closure(doc)["liveness"]
            c.update(design="BLOCKED", design_note="counterexample under fairness")
            c["basis"].update(
                proof="refuted",
                proof_note="stuttering in the page step",
                fairness="weakFair(step, (n, lim, offset))",
            )
            section(doc, "receipts")["runs"].append(
                authored_run(
                    "RV",
                    tool="quint_verify",
                    model_id="live",
                    variant="fairness",
                    exit_status=1,
                    result_class="violation",
                    checks=["liveUnderFairness"],
                    model_sha256=T.sha256_text(model_(doc, "live")["text"]),
                )
            )
            c["runs"] = ["RV"]

        self.accepted(blocked)

        def refuted_by_a_mutant_only(doc, d):
            blocked(doc, d)
            closure(doc)["liveness"]["runs"] = [
                "R8"
            ]  # R8 is the violation of the mutant LM1, not of the design

        self.refused(refuted_by_a_mutant_only, "CL3")

    def test_a_simulation_is_never_a_verification(self):
        def sim_only(doc, d):
            closure(doc)["safety"]["runs"] = [
                r for r in closure(doc)["safety"]["runs"] if r not in ("R4", "R5")
            ] + ["R3-1", "R3-2", "R3-3", "R3-4", "R3-5"]

        self.refused(sim_only, "CL3")

    def test_a_verification_run_must_have_the_right_variant_target_model_and_property(
        self,
    ):
        for field, value in (
            ("variant", "fixed"),
            ("target", "prototype"),
            ("model_id", "live"),
            ("checks", ["somethingElse"]),
            ("result_class", "violation"),
            ("result_class", "error"),
            ("result_class", "timeout"),
        ):  # a run that did not finish verifies nothing

            def bad(doc, d, f=field, v=value):
                for rid in ("R4", "R5"):
                    run_(doc, rid)[f] = v
                    if f == "result_class":
                        run_(doc, rid)["exit_status"] = {
                            "violation": 1,
                            "error": 2,
                            "timeout": 124,
                        }[v]

            self.refused(bad, "CL3")

    def test_a_liveness_verification_needs_the_fairness_variant(self):
        self.refused(
            lambda doc, d: run_(doc, "R7").__setitem__("variant", "no_fairness"), "CL3"
        )

    # --- the rest of what survived the first suite (BreakG10 D10)
    def test_a_non_ok_run_with_exit_zero_is_refused(self):
        self.refused(
            lambda doc, d: run_(doc, "R4").__setitem__("result_class", "violation"),
            "R2",
        )

    def test_an_unclear_or_correcting_judgment_needs_its_note(self):
        for j in ("unclear", "correction"):
            self.refused(
                lambda doc, d, j=j: judged(doc, "SC1", judgment=j),
                "S4",
                mode="interactive",
            )

    def test_an_inherited_liveness_is_refused_at_shared_scope_and_accepted_at_a_value_that_has_a_shared_claim(
        self,
    ):
        self.refused(
            lambda doc, d: closure(doc).__setitem__("liveness", {"tag": "inherited"}),
            "CL8",
        )

        def value_closure(doc, d):
            c = copy.deepcopy(closure(doc))
            c["liveness"] = {"tag": "inherited"}
            doc["sections"].append(
                {
                    "kind": "closure",
                    "scope": "value:1",
                    "status": {"tag": "applicable", "payload": {"closures": [c]}},
                }
            )

        self.accepted(value_closure)

        def orphan(doc, d):
            value_closure(doc, d)
            doc["sections"] = [
                s
                for s in doc["sections"]
                if not (s["kind"] == "closure" and s["scope"] == "shared")
            ]
            doc["sections"].append(
                {
                    "kind": "closure",
                    "scope": "shared",
                    "status": {"tag": "not_applicable", "reason": "values only"},
                }
            )

        self.refused(orphan, "CL8")

    def test_a_model_whose_runs_name_no_model_hash_is_refused_for_a_design_run(self):
        def strip(doc, d):
            r = run_(doc, "EX1")
            r.pop("model_sha256")

        self.refused(strip, "R5")

    # --- the validator and the CLI refuse in the open (BreakG10 D9)
    def test_a_sections_value_that_is_not_a_list_is_a_defect_not_a_crash(self):
        for bad in (
            {"sections": None},
            {"sections": 5},
            {"sections": "x"},
            {"sections": [None]},
        ):
            self.assertTrue(C.decode_handoff(bad)[1], bad)
            self.assertEqual([], C.resolve_authoring(bad, "."))


# =========================================================================== the sole writer of receipts
PY = sys.executable


class SoleWriter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="g10-run-")
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def receipts(self):
        doc, ds = C.load_json(os.path.join(self.dir, RUN.RECEIPTS_FILE))
        self.assertEqual([], ds)
        return {r["id"]: r for r in doc["sections"][0]["status"]["payload"]["runs"]}

    def exe(self, rid="R1", code="print('hi')", **kw):
        kw.setdefault("version_argv", [PY, "--version"])
        return RUN.execute(
            self.dir, rid, "script", "prototype", "fixed", [PY, "-c", code], **kw
        )

    def test_the_tool_records_argv_exit_version_duration_and_the_raw_output_with_its_hash(
        self,
    ):
        r = self.exe(
            code="import sys; print('out'); print('err', file=sys.stderr)",
            checks=["L1"],
            seed="7",
            measure=("cases", 5),
        )
        got = self.receipts()["R1"]
        self.assertEqual(
            [PY, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
            got["argv"],
        )
        self.assertEqual(
            (0, "ok", ["L1"]), (got["exit_status"], got["result_class"], got["checks"])
        )
        self.assertTrue(got["tool_version"].startswith("Python"))
        self.assertGreaterEqual(got["duration_s"], 0)
        self.assertEqual({"role": "output"}, {"role": got["artifacts"][0]["role"]})
        raw = open(os.path.join(self.dir, got["artifacts"][0]["path"]), "rb").read()
        self.assertIn(b"out", raw)
        self.assertIn(b"err", raw)
        self.assertEqual(T.sha256_bytes(raw), got["artifacts"][0]["sha256"])
        self.assertEqual(r.id, "R1")

    def test_a_script_exit_is_an_error_unless_the_caller_declares_the_exit_that_means_a_violation(
        self,
    ):
        self.exe("V", "import sys; sys.exit(1)", violation_exit=1)
        self.exe(
            "E", "import sys; sys.exit(1)"
        )  # the same exit, undeclared: the tool cannot read a script's output
        self.exe("E2", "import sys; sys.exit(2)", violation_exit=1)
        got = self.receipts()
        self.assertEqual(
            ("violation", 1), (got["V"]["result_class"], got["V"]["exit_status"])
        )
        self.assertEqual(
            ("error", 1), (got["E"]["result_class"], got["E"]["exit_status"])
        )
        self.assertEqual(
            ("error", 2), (got["E2"]["result_class"], got["E2"]["exit_status"])
        )

    def test_exit_one_of_a_probe_is_an_error_not_a_violation(self):
        RUN.execute(
            self.dir,
            "P",
            "probe",
            "environment",
            "base",
            [PY, "-c", "import sys; sys.exit(1)"],
            version_argv=[PY, "--version"],
        )
        got = self.receipts()["P"]
        self.assertEqual(("error", 1), (got["result_class"], got["exit_status"]))

    def test_a_command_that_runs_too_long_is_a_timeout_not_a_hang(self):
        self.exe("TO", "import time; time.sleep(30)", timeout_s=1)
        got = self.receipts()["TO"]
        self.assertEqual("timeout", got["result_class"])
        self.assertNotEqual(0, got["exit_status"])

    def test_a_trace_the_command_writes_is_kept_with_its_hash(self):
        (Path(self.dir) / "traces").mkdir(parents=True)
        self.exe(
            "T",
            "open('traces/t.json','w').write('{}')",
            trace="traces/t.json",
            cwd=self.dir,
        )
        art = {a["role"]: a for a in self.receipts()["T"]["artifacts"]}
        self.assertEqual(T.sha256_bytes(b"{}"), art["trace"]["sha256"])

    def test_a_trace_the_command_did_not_write_is_refused_with_the_fix(self):
        with self.assertRaises(RUN.RunError) as cm:
            self.exe("T2", "print(1)", trace="traces/none.json")
        self.assertTrue(cm.exception.defect.how)
        self.assertNotIn(
            "T2",
            self.receipts()
            if os.path.exists(os.path.join(self.dir, RUN.RECEIPTS_FILE))
            else {},
        )

    def test_a_bad_shape_is_refused_before_the_command_runs(self):
        marker = os.path.join(self.dir, "ran")
        with self.assertRaises(RUN.RunError):
            RUN.execute(
                self.dir,
                "R1",
                "script",
                "prototype",
                "not a variant",
                [PY, "-c", f"open({marker!r}, 'w')"],
                version_argv=[PY, "--version"],
            )
        with self.assertRaises(RUN.RunError):
            RUN.execute(
                self.dir,
                "bad id",
                "script",
                "prototype",
                "fixed",
                [PY, "-c", f"open({marker!r}, 'w')"],
                version_argv=[PY, "--version"],
            )
        self.assertFalse(
            os.path.exists(marker),
            "the command ran although the receipt could not be written",
        )

    def test_a_command_that_does_not_start_is_refused_not_recorded(self):
        with self.assertRaises(RUN.RunError) as cm:
            RUN.execute(
                self.dir,
                "R1",
                "script",
                "prototype",
                "fixed",
                ["/no/such/binary"],
                version_argv=[PY, "--version"],
            )
        self.assertEqual("RUN4", cm.exception.defect.rule)

    def test_a_missing_version_command_is_refused(self):
        with self.assertRaises(RUN.RunError) as cm:
            RUN.execute(
                self.dir, "R1", "script", "prototype", "fixed", [PY, "-c", "pass"]
            )
        self.assertEqual("RUN1", cm.exception.defect.rule)

    def test_a_repeated_id_is_refused_before_the_command_runs(self):
        marker = os.path.join(self.dir, "ran")
        self.exe("R1", "print(1)")
        with self.assertRaises(RUN.RunError) as cm:
            self.exe("R1", f"open({marker!r}, 'w')")
        self.assertEqual("RUN2", cm.exception.defect.rule)
        self.assertFalse(
            os.path.exists(marker),
            "the command ran although its receipt could not be written",
        )

    def test_a_trace_path_outside_the_directory_is_refused_before_the_command_runs(
        self,
    ):
        marker = os.path.join(self.dir, "ran")
        with self.assertRaises(RUN.RunError) as cm:
            self.exe("T3", f"open({marker!r}, 'w')", trace="../x.json")
        self.assertEqual("RUN3", cm.exception.defect.rule)
        self.assertFalse(os.path.exists(marker))

    def test_a_receipt_id_is_never_silently_overwritten(self):
        self.exe("R1", "print(1)")
        with self.assertRaises(RUN.RunError) as cm:
            self.exe("R1", "print(2)")
        self.assertEqual("RUN2", cm.exception.defect.rule)
        self.assertIn("--replace", cm.exception.defect.how)
        self.exe("R1", "print(2)", replace=True)
        self.assertEqual(1, len(self.receipts()))

    def test_a_model_file_is_hashed_and_must_stay_inside_the_sidecar_directory(self):
        open(os.path.join(self.dir, "m.qnt"), "w").write("module m {}\n")
        self.exe("M", "pass", model_id="m", model_file="m.qnt")
        self.assertEqual(
            T.sha256_text("module m {}\n"), self.receipts()["M"]["model_sha256"]
        )
        with self.assertRaises(RUN.RunError) as cm:
            self.exe("M2", "pass", model_id="m", model_file="../m.qnt")
        self.assertIn("not a relative path inside", cm.exception.defect.what)

    def test_an_id_recorded_by_another_writer_while_the_command_ran_is_never_overwritten(
        self,
    ):
        from unittest import mock

        self.exe("RACE", "print('first')")
        before = self.receipts()["RACE"]
        with mock.patch.object(
            RUN, "_refuse_repeat", lambda *a, **k: None
        ):  # the check before the command saw nothing; the one under the lock must still see it
            with self.assertRaises(RUN.RunError) as cm:
                self.exe("RACE", "print('second')")
        self.assertIn("RUN2", cm.exception.defect.rule)
        self.assertIn("NOTHING was recorded", cm.exception.defect.what)
        self.assertEqual(before, self.receipts()["RACE"])

    def test_an_authored_claim_has_no_artifacts_so_every_reader_can_tell_it_from_a_measurement(
        self,
    ):
        RUN.record_authored(
            self.dir,
            "C1",
            "quint_verify",
            "quint 0.32.0",
            "model",
            "base",
            ["quint", "verify", "m.qnt"],
            0,
            "ok",
            checks=["p"],
        )
        self.exe("R1")
        got = self.receipts()
        self.assertEqual([], got["C1"]["artifacts"])
        self.assertTrue(got["R1"]["artifacts"])

    def test_the_receipts_file_written_by_the_tool_decodes_and_merges_with_the_sidecar(
        self,
    ):
        with fresh_copy() as d:
            self.assertEqual(
                2,
                sum(
                    1
                    for f in ("g10.json", "g10.receipts.json")
                    if os.path.exists(os.path.join(d, f))
                ),
            )


# =========================================================================== command line
class CLI(unittest.TestCase):
    def g10(self, *args: str):
        p = subprocess.run(
            [PY, "-m", G10, *args],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertNotIn("Traceback", p.stderr + p.stdout, (args, p.stderr[-400:]))
        return p

    def test_exit_codes_say_what_happened(self):
        self.assertEqual(
            0, self.g10("check", MINIMAL, "--targets", "clamp.py").returncode
        )
        skipped = self.g10("check", MINIMAL)
        self.assertEqual(3, skipped.returncode)
        self.assertIn("Not run:", skipped.stdout)
        bad = self.g10(
            "check",
            os.path.join(V9_DIR, "g10.json"),
            os.path.join(V9_DIR, "g10.receipts.json"),
            "--targets",
            ",".join(V9_TARGETS),
        )
        self.assertEqual(1, bad.returncode)
        self.assertTrue(bad.stdout.startswith("8 defect(s)."), bad.stdout[:80])
        for word in ("WHAT:", "WHY:", "HOW:"):
            self.assertIn(word, bad.stdout)
        self.assertIn("Receipts:", bad.stdout)

    def test_the_report_counts_before_it_lists_and_says_how_many_receipts_were_measured(
        self,
    ):
        out = self.g10("check", MINIMAL, "--targets", "clamp.py").stdout
        self.assertTrue(out.startswith("0 defects."))
        self.assertIn(
            "0 with a kept output (sha256 checked by R6), 2 claims without output", out
        )

    def test_wrong_usage_is_exit_two_with_a_message(self):
        for args in (
            ["prompt", MINIMAL, "--role", "nobody"],
            ["check", MINIMAL, "--targets"],
            ["prompt", MINIMAL, "--role", "atd", "--value", "x"],
            ["nothing"],
            [],
        ):
            p = self.g10(*args)
            self.assertEqual(2, p.returncode, args)
            self.assertTrue(p.stderr.strip(), args)

    def test_unreadable_input_is_a_defect_with_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in (
                ("empty.json", b""),
                ("bad.json", b"{x"),
                ("null.json", b'{"sections": null}'),
                ("five.json", b'{"sections": 5}'),
                ("deep.json", b"[" * 100000 + b"]" * 100000),
            ):
                p = os.path.join(tmp, name)
                open(p, "wb").write(data)
                out = self.g10("check", p)
                self.assertEqual(1, out.returncode, name)
                self.assertIn("WHAT:", out.stdout, name)
            out = self.g10("check", os.path.join(tmp, "missing.json"))
            self.assertEqual(1, out.returncode)
            self.assertIn("G12", out.stdout)

    def test_prompt_for_a_crafter_without_targets_says_how_to_fix_it(self):
        p = self.g10("prompt", OO, "--role", "software_crafter")
        self.assertEqual(1, p.returncode)
        self.assertIn("--targets", p.stdout)

    def test_prompt_render_summary_and_describe_work_end_to_end(self):
        files = [
            os.path.join(V9_DIR, "g10.json"),
            os.path.join(V9_DIR, "g10.receipts.json"),
        ]
        for role in P.ROLES:
            args = ["prompt", *files, "--role", role, "--targets", ",".join(V9_TARGETS)]
            self.assertEqual(0, self.g10(*args).returncode, role)
        self.assertIn("The second page is empty", self.g10("render", *files).stdout)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "s.html")
            self.assertEqual(
                0, self.g10("render", *files, "--html", out, "--dir", V9_DIR).returncode
            )
            self.assertIn("<li>", open(out).read())
        self.assertEqual(0, self.g10("summary", *files).returncode)
        self.assertIn("Closure {", self.g10("describe").stdout)

    def test_run_and_record_then_check_close_the_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            side = os.path.join(tmp, "g10.json")
            doc = read(MINIMAL)
            doc["sections"] = [s for s in doc["sections"] if s["kind"] != "receipts"]
            json.dump(doc, open(side, "w"))
            ran = self.g10(
                "run",
                "--dir",
                tmp,
                "--id",
                "RL-OK",
                "--tool",
                "script",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--checks",
                "L1,L2",
                "--version-argv",
                f"{PY} --version",
                "--",
                PY,
                "-c",
                "print(1)",
            )
            self.assertEqual(0, ran.returncode, ran.stdout)
            rec = self.g10(
                "record",
                "--dir",
                tmp,
                "--id",
                "RL-BAD",
                "--tool",
                "script",
                "--tool-version",
                "python 3.12",
                "--target",
                "prototype",
                "--variant",
                "unfixed",
                "--checks",
                "L1",
                "--exit",
                "1",
                "--result",
                "violation",
                "--",
                "python3",
                "laws.py",
                "--bug",
                "x",
            )
            self.assertEqual(0, rec.returncode, rec.stdout)
            out = self.g10(
                "check",
                side,
                os.path.join(tmp, RUN.RECEIPTS_FILE),
                "--targets",
                "clamp.py",
            )
            self.assertEqual(0, out.returncode, out.stdout)
            self.assertIn(
                "1 with a kept output (sha256 checked by R6), 1 claims without output",
                out.stdout,
            )


# =========================================================================== one condition at a time
class OneCondition(Docs, unittest.TestCase):
    """A rule is a conjunction of conditions. Each test changes ONE field of a valid document, so that removing any single
    condition from a rule makes one of these tests fail (tests/mutation_check.py removes them one by one and checks that)."""

    # ----- laws and construction
    def test_a_model_run_that_names_a_law_does_not_back_it(self):
        def bad(doc, d):
            section(doc, "receipts")["runs"].append(
                authored_run(
                    "RM",
                    model_id="walk",
                    checks=["L1"],
                    model_sha256=T.sha256_text(model_(doc, "walk")["text"]),
                )
            )
            law(doc, "L1")["evidence"] = {
                "tag": "executed",
                "receipts": ["RM", "LAWS-UNFIXED"],
            }

        self.refused(bad, "L5")

    def test_a_law_citing_a_receipt_that_does_not_exist_is_refused_even_when_the_others_back_it(
        self,
    ):
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "evidence",
                {"tag": "executed", "receipts": ["LAWS-FIXED", "LAWS-UNFIXED", "NOPE"]},
            ),
            "L5",
        )

    def test_a_law_needs_an_ok_run_and_a_broad_law_also_a_violation_run(self):
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "evidence", {"tag": "executed", "receipts": ["LAWS-UNFIXED"]}
            ),
            "L5",
        )
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "evidence", {"tag": "executed", "receipts": ["LAWS-FIXED"]}
            ),
            "L5",
        )

    def test_a_finite_law_needs_no_violation_run(self):
        def ok(doc, d):
            section(doc, "receipts")["runs"].append(
                authored_run(
                    "RL10",
                    tool="script",
                    target="prototype",
                    variant="fixed",
                    checks=["L10"],
                )
            )
            law(doc, "L10")["evidence"] = {"tag": "executed", "receipts": ["RL10"]}

        self.accepted(ok)

    def test_an_id_used_twice_in_the_laws_section_is_refused_whatever_its_kind(self):
        for pick in ("observations", "constructors", "generators", "refuted"):
            self.refused(
                lambda doc, d, pick=pick: section(doc, "laws")[pick][0].__setitem__(
                    "id", "L1"
                ),
                "L1",
            )
        self.refused(lambda doc, d: law(doc, "L2").__setitem__("id", "L1"), "L1")

    def test_the_equality_and_a_law_may_name_only_declared_observations_and_constructors(
        self,
    ):
        self.refused(
            lambda doc, d: section(doc, "laws")["equality"]["under"].append("O99"), "L3"
        )
        self.refused(
            lambda doc, d: law(doc, "L1").__setitem__(
                "uses", ["O1", "paginate", "O99"]
            ),
            "L2",
        )

    def test_a_construction_claim_by_proof_needs_no_bypass_and_any_other_strength_does(
        self,
    ):
        self.accepted(
            lambda doc, d: section(doc, "construction")["claims"][0].update(
                strength="proof", bypass=[]
            )
        )
        self.refused(
            lambda doc, d: section(doc, "construction")["claims"][0].update(bypass=[]),
            "C2",
        )

    # ----- models, kills and receipts
    def test_a_kill_cites_a_violation_run_of_that_mutant_on_that_model_naming_that_property(
        self,
    ):
        self.refused(
            lambda doc, d: _kill_of(doc, "M2", "noSkipNoRepeat").__setitem__(
                "run", "K-M1-noSkipNoRepeat"
            ),
            "M1",
        )  # the run of another mutant
        self.refused(
            lambda doc, d: run_(doc, "K-M2-noSkipNoRepeat").update(
                result_class="ok", exit_status=0
            ),
            "M1",
        )  # not a violation
        self.refused(
            lambda doc, d: run_(doc, "K-M2-noSkipNoRepeat").__setitem__(
                "target", "prototype"
            ),
            "M1",
        )  # not about the model

    def test_two_models_or_two_mutants_with_one_id_are_refused(self):
        def two_models(doc, d):
            twin = copy.deepcopy(model_(doc, "walk"))
            twin["mutants"] = []
            section(doc, "model")["models"].append(twin)

        def two_mutants(doc, d):
            twin = copy.deepcopy(model_(doc, "walk")["mutants"][0])
            twin["description"] = "the same id, described again"
            model_(doc, "walk")["mutants"].append(twin)

        self.refused(two_models, "M1")
        self.refused(two_mutants, "M1")

    def test_a_mutant_run_names_a_mutant_of_its_own_model(self):
        self.refused(
            lambda doc, d: section(doc, "receipts")["runs"].append(
                authored_run(
                    "RX",
                    variant="mutant:LM1",
                    model_id="walk",
                    exit_status=1,
                    result_class="violation",
                )
            ),
            "R4",
        )

    def test_a_construction_owner_must_be_a_declared_path_not_a_prefix_of_one(self):
        self.refused(
            lambda doc, d: section(doc, "construction")["claims"][0].__setitem__(
                "owner", "pagination.pyc::paginate"
            ),
            "C3",
        )

    def test_a_blocked_argued_claim_needs_no_assumptions(self):
        def blocked(doc, d):
            closure(doc)["safety"].update(
                design="BLOCKED",
                design_note="the argument is incomplete",
                assumptions=[],
                runs=[],
                basis={"tag": "argued", "argument": "it is total"},
            )

        self.accepted(blocked)
        self.refused(
            lambda doc, d: closure(doc)["safety"].update(
                assumptions=[],
                runs=[],
                basis={"tag": "argued", "argument": "it is total"},
            ),
            "CL9",
        )

    # ----- closure
    def test_each_closure_class_accepts_only_the_bases_its_skill_allows(self):
        bases = {
            "checked": {
                "tag": "checked",
                "model_id": "walk",
                "properties": ["bounded"],
                "proof": "indeterminate",
                "proof_note": "not run",
            },
            "constructed": {"tag": "constructed", "claims": ["E1"]},
            "argued": {"tag": "argued", "argument": "it is total"},
            "path": {
                "tag": "path",
                "admitted_input": "i",
                "producer": "pagination.py::paginate",
                "consumer": "pagination.py::main",
                "public_observation": "o",
            },
        }
        allowed = {
            "safety": {"checked", "constructed", "argued"},
            "inhabitation": {"path"},
            "public_reachability": {"path"},
            "liveness": {"checked", "argued"},
        }
        for cname, ok in allowed.items():
            for tag, basis in bases.items():
                with fresh_copy() as d:
                    doc = base_doc(d)
                    claim = closure(doc)[cname]
                    claim["basis"] = dict(basis)
                    claim["assumptions"] = ["an assumption"]
                    ids = rule_ids(doc, V9_TARGETS, "auto", d)
                self.assertEqual(tag in ok, "CL1" not in ids, (cname, tag))

    def test_a_claim_cannot_cite_a_run_a_law_a_model_or_a_construction_claim_that_does_not_exist(
        self,
    ):
        self.refused(
            lambda doc, d: closure(doc)["safety"]["runs"].append("NOPE"), "CL7"
        )
        self.refused(lambda doc, d: closure(doc)["safety"]["laws"].append("L99"), "CL7")
        self.refused(
            lambda doc, d: closure(doc)["safety"]["basis"].update(model_id="nomodel"),
            "CL7",
        )
        self.refused(
            lambda doc, d: closure(doc)["safety"].update(
                basis={"tag": "constructed", "claims": ["E99"]}
            ),
            "CL7",
        )

    def test_observed_needs_an_ok_run_of_the_implementation_and_of_nothing_else(self):
        def observed(extra):
            def mutate(doc, d):
                closure(doc)["safety"]["runtime"] = "OBSERVED"
                closure(doc)["safety"]["runs"] = closure(doc)["safety"]["runs"] + extra

            return mutate

        self.refused(observed([]), "CL6")
        self.refused(
            observed(["CLI-AGREE"]), "CL6"
        )  # an ok run of the prototype is not an observation of the built code
        self.refused(
            observed(["LAWS-UNFIXED"]), "CL6"
        )  # an implementation run that is not ok
        self.accepted(observed(["BASELINE"]))

    # ----- scenarios
    def test_a_scenario_run_must_be_a_model_tool_run_of_a_model_that_exists(self):
        self.refused(
            lambda doc, d: run_(doc, "EX1").__setitem__("tool", "script"), "S2"
        )
        self.refused(
            lambda doc, d: run_(doc, "EX1").__setitem__("target", "prototype"), "S2"
        )
        self.refused(lambda doc, d: run_(doc, "EX1").pop("model_id"), "S2")

    def test_a_scenario_of_each_kind_needs_the_run_that_kind_means(self):
        self.refused(
            lambda doc, d: run_(doc, "K-M1-pageMatchesSpec").__setitem__(
                "checks", ["pageMatchesSpec", "noSkipNoRepeat"]
            ),
            "S2",
        )  # which one failed?
        self.refused(
            lambda doc, d: run_(doc, "EX1").update(
                exit_status=1, result_class="violation"
            ),
            "S2",
        )  # a violation is an example only as a witness

        def with_a_violation_of_the_design(
            doc, d, checks
        ):  # own kept files and a violating trace; SC2 keeps EX1
            clone_run(
                doc,
                d,
                "EX1",
                "EX2",
                trace_status="violation",
                exit_status=1,
                result_class="violation",
                checks=checks,
            )

        def as_mutant(doc, d):
            with_a_violation_of_the_design(doc, d, ["bounded"])
            scn(doc, "SC1")["source_run"] = "EX2"

        def as_counterexample(checks):
            def mutate(doc, d):
                with_a_violation_of_the_design(doc, d, checks)
                scn(doc, "SC2").update(kind="counterexample", source_run="EX2")

            return mutate

        self.refused(
            as_mutant, "S2"
        )  # a mutant scenario needs the violation of a MUTANT
        self.refused(
            as_counterexample(["bounded", "beyondEndEmpty"]), "S2"
        )  # which property failed?
        self.accepted(as_counterexample(["bounded"]))

    def test_a_refutation_needs_a_violation_run_of_this_model_naming_the_property(self):
        def blocked(**over):
            def mutate(doc, d):
                c = closure(doc)["liveness"]
                c.update(
                    design="BLOCKED",
                    design_note="counterexample under fairness",
                    runs=["RV"],
                )
                c["basis"].update(
                    proof="refuted",
                    proof_note="stuttering in the page step",
                    fairness="weakFair(step, (n, lim, offset))",
                )
                run = authored_run(
                    "RV",
                    tool="quint_verify",
                    model_id="live",
                    variant="fairness",
                    exit_status=1,
                    result_class="violation",
                    checks=["liveUnderFairness"],
                    model_sha256=T.sha256_text(model_(doc, "live")["text"]),
                )
                run.update(over)
                section(doc, "receipts")["runs"].append(run)

            return mutate

        self.accepted(blocked())
        self.refused(
            blocked(exit_status=0, result_class="ok"), "CL3"
        )  # not a violation
        self.refused(blocked(target="prototype"), "CL3")  # not about the model
        self.refused(blocked(model_id="walk"), "CL3")  # another model
        self.refused(blocked(checks=["reachesEnd"]), "CL3")  # another property
        self.refused(
            blocked(variant="no_fairness"), "CL3"
        )  # the ablation without fairness refutes nothing about the design under fairness


# =========================================================================== edges: files, hashes, symlinks, required sections
class StrictEdges(unittest.TestCase):
    def test_every_required_section_is_required_and_construction_is_optional(self):
        for kind in ("laws", "model", "closure", "receipts", "scenarios"):
            with fresh_copy() as d:
                doc = base_doc(d)
                doc["sections"] = [s for s in doc["sections"] if s["kind"] != kind]
                where = [
                    x.where
                    for x in defects(doc, V9_TARGETS, "auto", d)
                    if x.rule == "X1"
                ]
            self.assertEqual([f"{kind}@shared"], where, kind)
        with fresh_copy() as d:
            doc = base_doc(d)
            doc["sections"] = [
                s for s in doc["sections"] if s["kind"] != "construction"
            ]
            self.assertEqual(
                [], [f"{x.rule} {x.where}" for x in defects(doc, V9_TARGETS, "auto", d)]
            )

    def test_a_trace_whose_bytes_changed_after_the_run_is_not_rendered(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            with open(os.path.join(d, "traces", "EX1.itf.json"), "a") as fh:
                fh.write(" ")
            h = decode(doc)
            sc = next(
                s
                for (k, _), e in h.items()
                if k == "scenarios"
                for s in e.status.payload.scenarios
                if s.id == "SC2"
            )
            out = R.render_scenario(S.visible(h, "shared"), sc, d)
            self.assertIsInstance(out, R.Skipped)
            self.assertIn("changed after the run", out.reason)

    def test_a_text_file_cannot_escape_the_sidecar_directory_through_a_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "side")
            Path(sub).mkdir(parents=True)
            secret = os.path.join(tmp, "secret.txt")
            open(secret, "w").write("outside")
            (Path(sub) / "m.qnt").symlink_to(secret)
            doc = {
                "sections": [
                    {
                        "kind": "model",
                        "scope": "shared",
                        "status": {
                            "tag": "applicable",
                            "payload": {"models": [{"text_file": "m.qnt"}]},
                        },
                    }
                ]
            }
            ds = C.resolve_authoring(doc, sub)
            self.assertEqual(["G11"], [x.rule for x in ds])

    def test_the_oracle_author_sees_the_mutants_and_assumptions_the_oracle_must_respect_and_never_the_model_text(
        self,
    ):
        with fresh_copy() as d:
            atd = P.compose("atd", decode(base_doc(d)), "T", targets=V9_TARGETS)
        for needle in ('"mutants"', '"M1"', '"assumptions"', '"pageMatchesSpec"'):
            self.assertIn(needle, atd)
        self.assertNotIn("module pagination_walk", atd)

    def test_a_crafter_without_an_owned_law_receives_no_equality(self):
        laws = next(
            c
            for k, _s, _sha, _v, c in P.project(
                decode(read(OO)), "software_crafter", targets=["units.py"]
            )
            if k == "laws"
        )
        self.assertNotIn("equality", laws)

    def test_a_repeated_run_id_with_two_contents_never_makes_a_prompt_depend_on_list_order(
        self,
    ):
        with fresh_copy() as d:
            other = os.path.join(d, "traces", "K-M1-pageMatchesSpec.itf.json")
            digest = T.sha256_bytes(open(other, "rb").read())

            def variant(at_front):
                doc = base_doc(d)
                twin = copy.deepcopy(
                    run_(doc, "EX1")
                )  # a second receipt under the same id that keeps ANOTHER trace
                twin["artifacts"] = [
                    a for a in twin["artifacts"] if a["role"] != "trace"
                ] + [
                    {
                        "role": "trace",
                        "path": "traces/K-M1-pageMatchesSpec.itf.json",
                        "sha256": digest,
                    }
                ]
                runs = section(doc, "receipts")["runs"]
                if at_front:
                    runs.insert(0, twin)
                else:
                    runs.append(twin)
                return decode(doc)

            a, b = variant(True), variant(False)
            for role in P.ROLES:
                self.assertEqual(
                    P.compose(role, a, "T", targets=V9_TARGETS, base_dir=d),
                    P.compose(role, b, "T", targets=V9_TARGETS, base_dir=d),
                    role,
                )

    def test_a_repeated_model_id_with_two_contents_never_makes_a_prompt_depend_on_list_order(
        self,
    ):
        with fresh_copy() as d:

            def variant(at_front):
                doc = base_doc(d)
                twin = copy.deepcopy(model_(doc, "walk"))
                atom_(twin, "step")["template"] = (
                    "A different sentence for the step"  # `step` is the action the kept traces name
                )
                models = section(doc, "model")["models"]
                if at_front:
                    models.insert(0, twin)
                else:
                    models.append(twin)
                return decode(doc)

            a, b = variant(True), variant(False)
            for role in P.ROLES:
                self.assertEqual(
                    P.compose(role, a, "T", targets=V9_TARGETS, base_dir=d),
                    P.compose(role, b, "T", targets=V9_TARGETS, base_dir=d),
                    role,
                )

    def test_a_run_that_lists_two_traces_never_makes_a_prompt_depend_on_their_order(
        self,
    ):
        with fresh_copy() as d:
            other = os.path.join(d, "traces", "A.itf.json")
            shutil.copy(
                os.path.join(d, "traces", "K-M1-pageMatchesSpec.itf.json"), other
            )
            extra = {
                "role": "trace",
                "path": "traces/A.itf.json",
                "sha256": T.sha256_bytes(open(other, "rb").read()),
            }

            def variant(first):
                doc = base_doc(d)
                ex1 = run_(doc, "EX1")
                ex1["artifacts"] = (
                    [extra, *ex1["artifacts"]] if first else [*ex1["artifacts"], extra]
                )
                return decode(doc)

            a, b = variant(True), variant(False)
            for role in P.ROLES:
                self.assertEqual(
                    P.compose(role, a, "T", targets=V9_TARGETS, base_dir=d),
                    P.compose(role, b, "T", targets=V9_TARGETS, base_dir=d),
                    role,
                )


# =========================================================================== both reviewers' wording
class Wording(unittest.TestCase):
    def test_a_stale_judgment_says_which_identity_differs(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            judged(doc, "SC1", model_identity="0" * 64)
            ds = [
                x for x in defects(doc, V9_TARGETS, "interactive", d) if x.rule == "S4"
            ]
            self.assertIn("sha256 of the model of the source run", ds[0].what)
            self.assertNotIn("the model changed", ds[0].what)

    def test_L5_names_what_is_missing_for_the_law(self):
        ds = defects(v9_doc(V9_DIR), V9_TARGETS, base=V9_DIR)
        self.assertTrue(
            all(
                "no violation run of the unfixed code or of a mutant names" in x.what
                for x in ds
                if x.where in {"laws:L3", "laws:L11"}
            )
        )


# =========================================================================== second review round: each finding is a regression with its document
class ReviewRound2(Docs, unittest.TestCase):
    # --- L5 reads the variant: the proof that a law can fail is a failure of the UNFIXED code or of a mutant
    @staticmethod
    def l3(ok_variant="fixed", bad_variant="unfixed"):
        def mutate(doc, d):
            section(doc, "receipts")["runs"] += [
                authored_run(
                    "RL3-OK",
                    tool="script",
                    target="prototype",
                    variant=ok_variant,
                    checks=["L3"],
                ),
                authored_run(
                    "RL3-BAD",
                    tool="script",
                    target="implementation",
                    variant=bad_variant,
                    checks=["L3"],
                    exit_status=1,
                    result_class="violation",
                ),
            ]
            law(doc, "L3")["evidence"] = {
                "tag": "executed",
                "receipts": ["RL3-OK", "RL3-BAD"],
            }

        return mutate

    def test_a_law_needs_an_ok_run_of_the_fixed_code_and_a_violation_of_the_unfixed_code_or_of_a_mutant(
        self,
    ):
        self.accepted(self.l3())
        self.accepted(self.l3(bad_variant="mutant:M1"))
        self.refused(
            self.l3(bad_variant="fixed"), "L5"
        )  # a violation of the FIXED code is a bug, not a falsifier
        self.refused(
            self.l3(ok_variant="unfixed"), "L5"
        )  # an ok run of the broken code is not the law holding

    # --- a passed proof cannot be cited together with a run that violates it
    def test_a_passed_proof_cited_with_a_run_that_violates_the_same_property_is_refused(
        self,
    ):
        def contra(doc, d):
            r = copy.deepcopy(run_(doc, "R4"))
            r.update(
                id="CONTRA",
                exit_status=1,
                result_class="violation",
                checks=["pageMatchesSpec"],
            )
            section(doc, "receipts")["runs"].append(r)
            closure(doc)["safety"]["runs"].append("CONTRA")

        self.refused(contra, "CL3")

    def test_a_refuted_proof_states_the_counterexample(self):
        def refuted(note):
            def mutate(doc, d):
                c = closure(doc)["liveness"]
                c.update(
                    design="BLOCKED",
                    design_note="counterexample under fairness",
                    runs=["RV"],
                )
                c["basis"].update(
                    proof="refuted", fairness="weakFair(step, (n, lim, offset))"
                )
                if note:
                    c["basis"]["proof_note"] = note
                section(doc, "receipts")["runs"].append(
                    authored_run(
                        "RV",
                        tool="quint_verify",
                        model_id="live",
                        variant="fairness",
                        exit_status=1,
                        result_class="violation",
                        checks=["liveUnderFairness"],
                        model_sha256=T.sha256_text(model_(doc, "live")["text"]),
                    )
                )

            return mutate

        self.accepted(refuted("stuttering in the page step"))
        self.refused(refuted(None), "CL3")

    # --- a scenario is read from a trace whose own status fits its kind
    def test_a_counterexample_cannot_be_read_from_a_trace_that_passed_and_an_example_cannot_come_from_one_that_failed(
        self,
    ):
        def counterexample(status):
            def mutate(doc, d):
                clone_run(
                    doc,
                    d,
                    "EX1",
                    "CXE",
                    trace_status=status,
                    exit_status=1,
                    result_class="violation",
                    checks=["pageMatchesSpec"],
                )
                scn(doc, "SC2").update(kind="counterexample", source_run="CXE")

            return mutate

        self.refused(counterexample("ok"), "S2")
        self.accepted(counterexample("violation"))

        def example(status):
            def mutate(doc, d):
                clone_run(doc, d, "EX1", "EXV", trace_status=status)
                scn(doc, "SC2")["source_run"] = "EXV"

            return mutate

        self.accepted(example("ok"))
        self.refused(example("violation"), "S2")

        def witness(status):
            def mutate(doc, d):
                clone_run(
                    doc,
                    d,
                    "EX1",
                    "WIT",
                    trace_status=status,
                    variant="witness",
                    exit_status=1,
                    result_class="violation",
                    checks=["reachesEnd"],
                )
                scn(doc, "SC2")["source_run"] = "WIT"

            return mutate

        self.accepted(witness("violation"))
        self.refused(witness("ok"), "S2")

    # --- the run of a mutant records the text of the mutant
    def test_a_kill_run_must_record_the_sha256_of_the_mutant_text_not_nothing_and_not_the_model(
        self,
    ):
        self.refused(
            lambda doc, d: run_(doc, "K-M1-pageMatchesSpec").pop("model_sha256"), "R5"
        )
        self.refused(
            lambda doc, d: run_(doc, "K-M1-pageMatchesSpec").__setitem__(
                "model_sha256", T.sha256_text(model_(doc, "walk")["text"])
            ),
            "R5",
        )

    # --- one file, one run; an output is artifacts/<run id>.out; so "kept output" cannot be forged by pointing at another run's file
    def test_a_receipt_cannot_borrow_the_file_of_another_run(self):
        def borrow(doc, d):
            run_(doc, "LAWS-FIXED")["artifacts"] = copy.deepcopy(
                run_(doc, "P-JAVA")["artifacts"]
            )

        self.refused(borrow, "R6")

        def elsewhere(doc, d):
            r = run_(doc, "P-JAVA")
            shutil.copy(
                os.path.join(d, r["artifacts"][0]["path"]),
                os.path.join(d, "artifacts", "moved.out"),
            )
            r["artifacts"][0]["path"] = "artifacts/moved.out"

        self.refused(elsewhere, "R6")

        def shared_trace(
            doc, d
        ):  # the output paths follow the rule, so only the shared trace can be the defect
            twin = clone_run(doc, d, "EX1", "EX3")
            first = next(
                a for a in run_(doc, "EX1")["artifacts"] if a["role"] == "trace"
            )
            for a in twin["artifacts"]:
                if a["role"] == "trace":
                    a.update(path=first["path"], sha256=first["sha256"])

        self.refused(shared_trace, "R6")

    # --- an id is a clash inside one scope or between shared and a value; two different values never meet
    def test_ids_clash_within_a_scope_and_between_shared_and_a_value_but_not_between_two_values(
        self,
    ):
        def receipts_in(scope, *ids):
            return {
                "kind": "receipts",
                "scope": scope,
                "status": {
                    "tag": "applicable",
                    "payload": {"runs": [authored_run(i) for i in ids]},
                },
            }

        def two_values(doc, d):
            doc["sections"] += [
                receipts_in("value:1", "VR"),
                receipts_in("value:2", "VR"),
            ]

        def shared_and_value(doc, d):
            doc["sections"].append(receipts_in("value:1", "R1"))

        def twice_in_a_value(doc, d):
            doc["sections"].append(receipts_in("value:1", "VR", "VR"))

        self.accepted(two_values)
        self.refused(shared_and_value, "R1")
        self.refused(twice_in_a_value, "R1")

    # --- a repeated name in a model makes a lookup depend on list order, so it is refused, and no byte of a prompt depends on that order anyway
    def test_a_repeated_atom_name_or_mutant_id_is_refused_and_no_prompt_depends_on_the_order(
        self,
    ):
        def twin_atom(doc, d, front=False):
            m = model_(doc, "walk")
            twin = copy.deepcopy(atom_(m, "step"))
            twin["template"] = "An alternative sentence for the step"
            m["atoms"].insert(0, twin) if front else m["atoms"].append(twin)

        def twin_mutant(doc, d, front=False):
            ms = model_(doc, "walk")["mutants"]
            twin = copy.deepcopy(next(x for x in ms if x["id"] == "M1"))
            twin["description"] = "another description of the same mutant"
            ms.insert(0, twin) if front else ms.append(twin)

        self.refused(twin_atom, "M1")
        self.refused(twin_mutant, "M1")
        for twin in (twin_atom, twin_mutant):
            with fresh_copy() as d:
                outs = set()
                for front in (True, False):
                    doc = base_doc(d)
                    twin(doc, d, front)
                    outs.add(P.compose("human", decode(doc), "T", base_dir=d))
                self.assertEqual(1, len(outs), twin.__name__)

    # --- the view of a crafter that owns nothing is empty, not the vocabulary of the whole design
    def test_a_crafter_that_owns_nothing_receives_no_admitted_or_excluded_states(self):
        out = P.compose(
            "software_crafter", decode(read(OO)), "T", targets=["nothing.py"]
        )
        for hidden in ("a Key and an int >= 1 unit count", "Units(0)"):
            self.assertNotIn(hidden, out)
        owned = P.compose("software_crafter", decode(read(OO)), "T", targets=OO_TARGETS)
        self.assertIn("Units(0)", owned)

    # --- the receipts that rest on what a person declared say so
    def test_the_architect_is_told_which_fields_of_a_receipt_are_observed_and_which_are_declared(
        self,
    ):
        out = P.grammar_what("architect")
        self.assertIn("OBSERVES", out)
        self.assertIn("YOU DECLARE", out)

    # --- visibility, the positive side: a value sees `shared` and itself
    def test_a_value_section_may_cite_the_entries_of_its_own_value_and_not_of_another(
        self,
    ):
        def in_value(scope):
            def mutate(doc, d):
                twin = clone_run(doc, d, "EX1", "VEX")
                runs = section(doc, "receipts")["runs"]
                runs.remove(next(r for r in runs if r["id"] == "VEX"))
                doc["sections"].append(
                    {
                        "kind": "receipts",
                        "scope": "value:1",
                        "status": {"tag": "applicable", "payload": {"runs": [twin]}},
                    }
                )
                doc["sections"].append(
                    {
                        "kind": "scenarios",
                        "scope": scope,
                        "status": {
                            "tag": "applicable",
                            "payload": {
                                "scenarios": [
                                    {
                                        "id": "V1",
                                        "title": "A walk in value one",
                                        "source_run": "VEX",
                                        "kind": "example",
                                        "review": {"tag": "pending"},
                                    }
                                ]
                            },
                        },
                    }
                )

            return mutate

        self.accepted(in_value("value:1"))
        self.refused(in_value("value:2"), "S2")


class NoTraceback(unittest.TestCase):
    """Every command is total: a bad input is a message with WHAT/WHY/HOW and an exit status, never a traceback."""

    def g(self, *args: str, env: dict | None = None):
        e = {**os.environ, **(env or {})}
        return subprocess.run(
            [sys.executable, "-W", "ignore", "-m", G10, *args],
            capture_output=True,
            env=e,
            check=False,
        )

    def total(self, p, code):
        self.assertNotIn(
            b"Traceback", p.stderr + p.stdout, (p.stdout + p.stderr)[-400:]
        )
        self.assertEqual(code, p.returncode, (p.stdout + p.stderr)[-400:])
        return p.stdout.decode("utf-8") + p.stderr.decode("utf-8")

    def write(self, tmp: str, doc: dict, name="g10.json") -> str:
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                doc, fh
            )  # ensure_ascii: a lone surrogate is written as an escape, as a hostile file would
        return path

    def test_a_template_that_is_not_utf8_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "t.txt")
            open(bad, "wb").write(b"\xff\xfe\x00")
            out = self.total(
                self.g("prompt", MINIMAL, "--role", "atd", "--template", bad), 1
            )
            self.assertIn("HOW", out)

    def test_a_page_that_cannot_be_written(self):
        out = self.total(
            self.g("render", MINIMAL, "--html", "/nonexistent-g10-dir/x.html"), 1
        )
        self.assertIn("HOW", out)

    def test_a_model_file_name_with_a_nul_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = (
                read(os.path.join(V9_DIR, "g10.json"))
                if False
                else json.load(open(os.path.join(V9_DIR, "g10.json"), encoding="utf-8"))
            )
            model_(doc, "walk").pop("text", None)
            model_(doc, "walk")["text_file"] = "a\x00b"
            out = self.total(self.g("check", self.write(tmp, doc)), 1)
            self.assertIn("G11", out)

    def test_a_lone_surrogate_and_a_huge_integer_are_refused_at_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = read(MINIMAL)
            section(doc, "laws")["laws"][0]["statement"] = "x\ud800y"
            self.assertIn("G13", self.total(self.g("check", self.write(tmp, doc)), 1))
            doc = read(MINIMAL)
            section(doc, "laws")["generators"][0]["size_bound"] = 10**30
            self.assertIn("G9", self.total(self.g("check", self.write(tmp, doc)), 1))

    def test_a_trace_nested_deeper_than_the_limit_is_refused_by_a_message_not_by_the_interpreter_stack(
        self,
    ):
        def nested(n):
            v: object = 1
            for _ in range(n):
                v = [v]
            return v

        I.parse({"#meta": {}, "states": [{"x": nested(I.MAX_DEPTH - 1)}]})
        with self.assertRaises(I.ItfError):
            I.parse({"#meta": {}, "states": [{"x": nested(I.MAX_DEPTH + 5)}]})

    def test_the_output_is_the_same_utf8_bytes_whatever_the_locale(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = read(MINIMAL)
            section(doc, "laws")["laws"][0]["statement"] = (
                "temp\u00e9rature stays in range"
            )
            path = self.write(tmp, doc)
            plain = self.g(
                "prompt", path, "--role", "atd", "--dir", tmp, "--targets", "clamp.py"
            )
            ascii_env = {
                "LC_ALL": "C",
                "LANG": "C",
                "PYTHONCOERCECLOCALE": "0",
                "PYTHONUTF8": "0",
                "PYTHONIOENCODING": "ascii",
            }
            ascii_ = self.g(
                "prompt",
                path,
                "--role",
                "atd",
                "--dir",
                tmp,
                "--targets",
                "clamp.py",
                env=ascii_env,
            )
            self.total(plain, 0)
            self.total(ascii_, 0)
            self.assertEqual(plain.stdout, ascii_.stdout)
            self.assertIn("temp\u00e9rature".encode("utf-8"), ascii_.stdout)

    def test_files_in_different_directories_need_an_explicit_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = os.path.join(tmp, "a"), os.path.join(tmp, "b")
            Path(a).mkdir(parents=True)
            Path(b).mkdir(parents=True)
            doc = read(MINIMAL)
            runs = section(doc, "receipts")["runs"]
            laws_only = {
                "sections": [s for s in doc["sections"] if s["kind"] != "receipts"]
            }
            receipts_only = {
                "sections": [s for s in doc["sections"] if s["kind"] == "receipts"]
            }
            f1, f2 = (
                self.write(a, laws_only),
                self.write(b, receipts_only, "g10.receipts.json"),
            )
            self.assertTrue(runs)
            out = self.total(
                self.g("prompt", f1, f2, "--role", "atd", "--targets", "clamp.py"), 2
            )
            self.assertIn("--dir", out)
            self.total(
                self.g(
                    "prompt",
                    f1,
                    f2,
                    "--role",
                    "atd",
                    "--targets",
                    "clamp.py",
                    "--dir",
                    a,
                ),
                0,
            )
            self.total(
                self.g(
                    "prompt",
                    f2,
                    f1,
                    "--role",
                    "atd",
                    "--targets",
                    "clamp.py",
                    "--dir",
                    a,
                ),
                0,
            )


class CliCommands(unittest.TestCase):
    """Every command in this process: what it prints, what it returns, what it refuses. (`CLI` above runs the program as a user does.)"""

    def cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = G.main(list(args))
            except SystemExit as exc:  # argparse refuses a wrong command line
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_summary_prints_the_counts_as_json_and_a_file_that_does_not_decode_is_refused(
        self,
    ):
        code, out, _ = self.cli("summary", MINIMAL)
        self.assertEqual(0, code)
        got = json.loads(out)
        self.assertEqual({"claim": 2, "kept_output": 0}, got["runs"])
        self.assertEqual("applicable", got["sections"]["laws@shared"])
        with tempfile.TemporaryDirectory() as tmp:
            broken = os.path.join(tmp, "g10.json")
            open(broken, "w").write("{")
            for cmd in ("summary", "render", "check", "prompt"):
                extra = ("--role", "atd") if cmd == "prompt" else ()
                code, out, _ = self.cli(cmd, broken, *extra)
                self.assertEqual(1, code, cmd)
                self.assertIn("WHAT:", out, cmd)

    def test_rules_and_describe_print_what_the_code_holds(self):
        code, out, _ = self.cli("rules")
        self.assertEqual((0, RU.rules_markdown().strip()), (code, out.strip()))
        code, out, _ = self.cli("describe")
        self.assertEqual((0, P.describe_types().strip()), (code, out.strip()))

    def test_render_prints_the_scenarios_or_writes_a_page_and_says_where(self):
        code, out, _ = self.cli(
            "render",
            os.path.join(V9_DIR, "g10.json"),
            os.path.join(V9_DIR, "g10.receipts.json"),
            "--dir",
            V9_DIR,
        )
        self.assertEqual(0, code)
        self.assertIn(
            "The second page is empty when the end bound is the limit [mutant; run K-M1-pageMatchesSpec",
            out,
        )
        with tempfile.TemporaryDirectory() as tmp:
            page = os.path.join(tmp, "page.html")
            code, out, _ = self.cli(
                "render",
                os.path.join(V9_DIR, "g10.json"),
                os.path.join(V9_DIR, "g10.receipts.json"),
                "--dir",
                V9_DIR,
                "--html",
                page,
            )
            self.assertEqual((0, f"wrote {page}"), (code, out.strip()))
            self.assertIn("<html", open(page, encoding="utf-8").read())

    def test_run_and_record_say_what_they_recorded_and_refuse_what_they_cannot(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = ("--dir", tmp, "--target", "prototype", "--variant", "fixed")
            run = (
                "run",
                *base,
                "--tool",
                "script",
                "--version-argv",
                f"{PY} --version",
                "--id",
                "R1",
                "--",
                PY,
                "-c",
                "print(1)",
            )
            code, out, _ = self.cli(*run)
            self.assertEqual(0, code, out)
            self.assertIn("recorded R1: exit 0 ok", out)
            self.assertIn("artifacts/R1.out", out)
            code, out, _ = self.cli(*run)  # the same id again
            self.assertEqual(1, code)
            self.assertIn("RUN2", out)
            code, out, _ = self.cli(
                "run",
                *base,
                "--tool",
                "quint_run",
                "--id",
                "Q",
                "--",
                PY,
                "-c",
                "print(1)",
            )  # a tool that is not quint
            self.assertEqual(1, code)
            self.assertIn("RUN7", out)
            code, _, err = self.cli(
                "run",
                *base,
                "--tool",
                "quint_run",
                "--violation-exit",
                "1",
                "--id",
                "Q2",
                "--",
                "quint",
                "--version",
            )
            self.assertEqual(2, code)
            self.assertIn("--violation-exit", err)
            claim = (
                "record",
                *base,
                "--tool",
                "quint_verify",
                "--tool-version",
                "quint 0.32.0",
                "--exit",
                "0",
                "--result",
                "ok",
                "--id",
                "C1",
                "--",
                "quint",
                "verify",
                "m.qnt",
            )
            code, out, _ = self.cli(*claim)
            self.assertEqual(0, code, out)
            self.assertIn("recorded the CLAIM C1: exit 0 ok (not executed here)", out)
            code, out, _ = self.cli(*claim)
            self.assertEqual(1, code)
            self.assertIn("RUN2", out)

    def test_a_timeout_is_1_to_86400_seconds_and_a_measure_is_a_kind_and_1_to_15_digits(
        self,
    ):
        import argparse

        for ok in ("1", "600", "86400"):
            self.assertEqual(int(ok), G._timeout(ok))
        for bad in ("0", "-1", "86401", "abc", "", "1.5", "\u00b2"):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                G._timeout(bad)
        self.assertIsNone(G._measure(None))
        self.assertEqual(("cases", 1), G._measure("cases=1"))
        self.assertEqual(("states", 10**15 - 1), G._measure("states=" + "9" * 15))
        self.assertEqual(("samples", 7), G._measure("samples=007"))
        for bad in (
            "cases=0",
            "cases=",
            "cases",
            "cases=-1",
            "cases=" + "9" * 16,
            "bytes=1",
            "=1",
            "cases=1.5",
            "cases=\u00b2",
            "cases=\uff11",
        ):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                G._measure(bad)


if __name__ == "__main__":
    unittest.main()
