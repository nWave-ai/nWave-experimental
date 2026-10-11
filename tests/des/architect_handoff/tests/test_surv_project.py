"""What a role receives, what the architect reads and what a person sees, beyond the cases of tests/test_g10.py.

A first tool-chosen mutation run showed that no test read these facts: which observations and constructors an owned view keeps, the
atoms and mutants of the model views, the notes and assumptions of the closure views, the markers of a missing section, the order of
the sections, the words of the grammar description, the counts of the summary, the lines of the markdown and the joins of a prompt.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_project
"""

from __future__ import annotations

import collections
import copy
import json
import re
import unittest

from tests.des.architect_handoff.tests.test_g10 import (
    OO,
    V9_TARGETS,
    base_doc,
    closure,
    decode,
    fresh_copy,
    judged,
    law,
    model_,
    read,
    run_,
    section,
)

from des.application.architect_handoff import g10_codec as C
from des.application.architect_handoff import g10_project as P
from des.application.architect_handoff import g10_types as T


def payload_of(doc: dict, kind: str, scope: str = "shared"):
    return decode(doc)[(kind, scope)].status.payload


def blocks(prompt: str) -> dict[str, str]:
    """The `[H]` blocks of a prompt by `kind@scope`: header line -> content line."""
    found = {}
    for m in re.finditer(r"=== \[H\] (\S+) sha=(\S+) view=(\S+) ===\n(.*)", prompt):
        found[m.group(1)] = m.group(4)
    return found


class TheGrammarTheArchitectReads(unittest.TestCase):
    def lines(self) -> dict[str, str]:
        return {
            x.split(" ", 1)[0]: x for x in P.describe_types().splitlines() if " { " in x
        }

    def test_the_introduction_names_every_section_kind_and_the_conventions(self):
        text = P.describe_types()
        self.assertIn(
            "kind is one of "
            + "|".join(T.KINDS)
            + "; scope is `shared` or `value:<n>`.",
            text,
        )
        # The old assertion pinned an overclaim: literal argv data may be blank.
        self.assertIn(
            "Strings must be nonblank, except later elements of `Run.argv`", text
        )
        self.assertIn(
            "(command argv data arguments), which may be blank or whitespace "
            "and are kept literally; the executable (first element) must be nonblank",
            text,
        )
        self.assertIn(
            "[X]+ is a list with at least one item; a field with `?` may be left out.",
            text,
        )
        self.assertIn(
            'status is {"tag":"applicable","payload":...} or {"tag":"not_applicable","reason":...};',
            text,
        )

    def test_each_field_is_shown_with_the_type_the_decoder_enforces(self):
        lines = self.lines()
        self.assertEqual(
            "Measure { kind: states|cases|samples; value: int>=1 }", lines["Measure"]
        )
        self.assertEqual("Pending { tag='pending' }", lines["Pending"])
        self.assertEqual(
            "Artifact { role: output|trace; path: RelPath; sha256: Sha }",
            lines["Artifact"],
        )
        self.assertEqual(
            "Scenario { id: ID; title: str; source_run: ID; kind: counterexample|mutant|example; review: Pending | Judged }",
            lines["Scenario"],
        )
        self.assertEqual(
            "Judged { by: str; judgment: correct|incorrect|depends|unclear|correction; model_identity: Sha; trace_identity: Sha; note: str?; tag='judged' }",
            lines["Judged"],
        )
        self.assertEqual("Receipts { runs: [Run]+ }", lines["Receipts"])
        run = lines["Run"]
        for fact in (
            "exit_status: int;",
            "checks: [str];",
            "argv: [str]+;",
            "measure: Measure?;",
            "seed: str?;",
            "model_id: ID?;",
            "duration_s: number>=0?;",
            "artifacts: [Artifact]",
            "variant: base|fairness|no_fairness|fixed|unfixed|witness|mutant:<id>;",
        ):
            self.assertIn(fact, run)
        self.assertIn("tag='checked'", lines["Checked"])
        self.assertIn("properties: [str]+;", lines["Checked"])

    def test_every_record_reachable_from_a_section_is_described_once(self):
        names = [
            x.split(" ", 1)[0] for x in P.describe_types().splitlines() if " { " in x
        ]
        self.assertEqual(len(names), len(set(names)))
        for kind in (
            "Laws",
            "Construction",
            "Models",
            "ClosureSet",
            "Receipts",
            "Scenarios",
            "Run",
            "Law",
            "Model",
            "Claim",
            "Checked",
            "Route",
            "Argued",
            "Constructed",
        ):
            self.assertIn(kind, names)
        self.assertNotIn("Handoff", names)

    def test_the_description_agrees_with_the_decoder_on_what_may_be_left_out(self):
        text = self.lines()["Run"]
        base = {
            "id": "R1",
            "tool": "script",
            "tool_version": "v",
            "target": "prototype",
            "variant": "fixed",
            "argv": ["x"],
            "exit_status": 0,
            "result_class": "ok",
            "checks": [],
        }
        ds: list = []
        value = C.dec(T.Run, base, "$", ds)
        self.assertEqual([], ds)
        for field in base:  # leaving out a field the description does not mark with `?` is refused; a marked one is not asked for
            ds = []
            C.dec(T.Run, {k: v for k, v in base.items() if k != field}, "$", ds)
            self.assertEqual(
                re.search(rf"\b{field}: [^;]*\?", text) is not None, not ds, field
            )
        for field in ("model_id", "model_sha256", "measure", "seed", "duration_s"):
            self.assertRegex(text, rf"\b{field}: [^;]*\?")
            self.assertIsNone(getattr(value, field), field)


class TheConsumerTable(unittest.TestCase):
    def test_a_basis_names_its_class_at_the_start_and_nowhere_else(self):
        for cls in ("direct", "inferred", "hypothesis"):
            self.assertEqual(cls, P.basis_class(f"[{cls}] a line"))
        for bad in (
            "direct a line",
            " [direct] a line",
            "a [direct] line",
            "[guess] a line",
            "",
        ):
            with self.assertRaises(ValueError) as cm:
                P.basis_class(bad)
            self.assertIn(
                "starts with [direct], [inferred] or [hypothesis]", str(cm.exception)
            )
        long = "[wrong] " + "x" * 200
        with self.assertRaises(ValueError) as cm:
            P.basis_class(long)
        self.assertTrue(
            str(cm.exception).endswith(repr(long[:60])),
            "the message quotes the first 60 characters of the basis, not all of it",
        )

    def test_the_table_has_one_row_per_consumer_and_section_and_counts_each_class_once(
        self,
    ):
        lines = P.consumers_markdown().splitlines()
        rows = [
            x
            for x in lines
            if x.startswith("| ")
            and not x.startswith("| role")
            and not x.startswith("|---")
        ]
        expected = [
            (role, kind)
            for role, kinds in P.CONSUMERS.items()
            if role != "architect"
            for kind in kinds
        ]
        self.assertEqual(
            expected, [tuple(c.strip() for c in x.split("|")[1:3]) for x in rows]
        )
        self.assertFalse(any(x.startswith("| architect") for x in rows))
        for x, (role, kind) in zip(rows, expected, strict=True):
            cells = [c.strip() for c in x.split("|")[1:-1]]
            view, cls, decision, basis = (
                P.CONSUMERS[role][kind][0],
                P.basis_class(P.CONSUMERS[role][kind][2]),
                *P.CONSUMERS[role][kind][1:],
            )
            self.assertEqual([role, kind, view, cls, decision, basis], cells)
        counts = {
            c: sum(
                1
                for role, kinds in P.CONSUMERS.items()
                if role != "architect"
                for _, (_, _, b) in kinds.items()
                if P.basis_class(b) == c
            )
            for c in ("direct", "inferred", "hypothesis")
        }
        self.assertEqual(
            f"rows: {len(rows)}; direct: {counts['direct']}; inferred: {counts['inferred']}; hypothesis: {counts['hypothesis']}",
            lines[-1],
        )
        # 20 measured rows of the v9 baseline plus the two product_owner rows
        # added by the native port (finding 13); the PO rows are the porter's
        # reading of nw-product-owner.md, not part of the measured baseline.
        self.assertEqual("rows: 22; direct: 7; inferred: 13; hypothesis: 2", lines[-1])
        self.assertEqual("", lines[-2])

    def test_a_refused_projection_carries_the_same_words_as_its_defect(self):
        with fresh_copy() as d:
            payload = payload_of(base_doc(d), "laws")
        with self.assertRaises(P.ProjectionError) as cm:
            P.view_payload("laws", payload, "owned", None)
        self.assertEqual(cm.exception.defect.what, str(cm.exception))


class OwnedViews(unittest.TestCase):
    def laws_view(self, edit=None, targets=("pagination.py",)):
        with fresh_copy() as d:
            doc = base_doc(d)
            if edit:
                edit(doc)
            return P.view_payload(
                "laws", payload_of(doc, "laws"), "owned", list(targets)
            ), section(doc, "laws")

    def test_an_owned_view_without_targets_is_refused_for_laws_and_for_construction_and_not_for_the_others(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        for kind in ("laws", "construction"):
            with self.assertRaises(P.ProjectionError) as cm:
                P.view_payload(kind, h[(kind, "shared")].status.payload, "owned", None)
            self.assertEqual(
                ("P1", kind), (cm.exception.defect.rule, cm.exception.defect.where)
            )
            self.assertIn("pass the declared mutable targets", cm.exception.defect.how)
        P.view_payload("laws", h[("laws", "shared")].status.payload, "full", None)
        P.view_payload(
            "model", h[("model", "shared")].status.payload, "interface", None
        )

    def test_an_owned_laws_view_keeps_the_laws_of_its_targets_and_exactly_the_vocabulary_they_use(
        self,
    ):
        def one_law_elsewhere(doc):
            for lw in section(doc, "laws")["laws"]:
                lw["owner"] = "other.py::f"
            law(doc, "L4")["owner"] = (
                "pagination.py::paginate"  # L4 uses O7 and paginate
            )

        view, raw = self.laws_view(one_law_elsewhere)
        self.assertEqual(["L4"], [x["id"] for x in view["laws"]])
        self.assertEqual(["O7"], [o["id"] for o in view["observations"]])
        self.assertEqual(["paginate"], [c["id"] for c in view["constructors"]])
        self.assertEqual(
            [],
            view["equality"]["under"],
            "the equality names O1, which this view does not show: no dangling reference",
        )
        for gone in ("generators", "refuted"):
            self.assertNotIn(gone, view)
        for x in view["laws"]:
            self.assertNotIn("treatment", x)
            self.assertNotIn("evidence", x)
        self.assertGreater(len(raw["observations"]), 1)

    def test_the_equality_stays_when_a_shown_observation_is_among_its_terms_and_goes_when_no_law_is_owned(
        self,
    ):
        view, _ = self.laws_view()
        self.assertEqual(["O1"], view["equality"]["under"])
        self.assertEqual({"O1", "O7"} <= {o["id"] for o in view["observations"]}, True)
        view, _ = self.laws_view(targets=("nothing.py",))
        self.assertEqual(
            ([], [], []), (view["laws"], view["observations"], view["constructors"])
        )
        self.assertNotIn("equality", view)

    def test_an_observation_that_no_owned_law_uses_is_not_shown_and_one_that_is_used_always_is(
        self,
    ):
        def only_o1(doc):
            for lw in section(doc, "laws")["laws"]:
                lw["uses"] = ["O1", "paginate"]

        view, raw = self.laws_view(only_o1)
        self.assertEqual(["O1"], [o["id"] for o in view["observations"]])
        self.assertEqual(["paginate"], [c["id"] for c in view["constructors"]])
        self.assertTrue({o["id"] for o in raw["observations"]} > {"O1"})

    def test_an_owned_construction_view_keeps_the_claims_that_concern_its_targets_by_owner_constructor_or_consumer(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            payload = payload_of(doc, "construction")
            full = {c.id for c in payload.claims}
            self.assertEqual(
                full,
                {
                    c["id"]
                    for c in P.view_payload(
                        "construction", payload, "owned", ["pagination.py"]
                    )["claims"]
                },
            )
            none = P.view_payload("construction", payload, "owned", ["nothing.py"])
            self.assertEqual([], none["claims"])
            for gone in ("admitted", "excluded", "unknown"):
                self.assertNotIn(gone, none)
            kept = P.view_payload("construction", payload, "owned", ["pagination.py"])
            self.assertIn("admitted", kept)
            self.assertIn("excluded", kept)
            self.assertNotIn("unknown", kept)
            for field in (
                "constructor",
                "consumer",
            ):  # a claim whose ONLY link to the target is this field is kept
                moved = copy.deepcopy(doc)
                claim = section(moved, "construction")["claims"][0]
                claim["owner"] = "elsewhere.py::f"
                claim["constructor"] = "elsewhere.py:1"
                claim["consumer"] = "elsewhere.py:2"
                claim[field] = "only_here.py:3"
                ids = {
                    c["id"]
                    for c in P.view_payload(
                        "construction",
                        payload_of(moved, "construction"),
                        "owned",
                        ["only_here.py"],
                    )["claims"]
                }
                self.assertEqual({claim["id"]}, ids, field)


class ModelViews(unittest.TestCase):
    def test_the_interface_view_keeps_the_symbol_map_and_nothing_that_says_how_to_test(
        self,
    ):
        with fresh_copy() as d:
            payload = payload_of(base_doc(d), "model")
        view = P.view_payload("model", payload, "interface")
        self.assertEqual(["live", "walk"], [m["id"] for m in view["models"]])
        for m in view["models"]:
            self.assertEqual({"id", "language", "path", "sha256", "atoms"}, set(m))
            for a in m["atoms"]:
                self.assertTrue(
                    set(a) <= {"name", "symbol", "site", "atomicity", "tag"}, a
                )
                self.assertNotIn("template", a)
                self.assertNotIn("statement", a)
        tags = {a["tag"] for m in view["models"] for a in m["atoms"]}
        self.assertEqual({"state", "action", "property", "constant"}, tags)
        self.assertTrue(
            any(
                "atomicity" in a
                for m in view["models"]
                for a in m["atoms"]
                if a["tag"] == "action"
            )
        )
        self.assertFalse(
            any(
                "atomicity" in a
                for m in view["models"]
                for a in m["atoms"]
                if a["tag"] != "action"
            )
        )

    def test_the_falsifiers_view_adds_what_the_model_assumes_leaves_out_and_the_mutants_with_the_properties_they_kill(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            payload = payload_of(doc, "model")
            view = P.view_payload("model", payload, "falsifiers")
            walk = next(m for m in view["models"] if m["id"] == "walk")
            raw = model_(doc, "walk")
        self.assertEqual(
            set(P.view_payload("model", payload, "interface")["models"][0])
            | {"assumptions", "exclusions", "mutants"},
            set(walk),
        )
        self.assertEqual(sorted(set(raw["assumptions"])), sorted(walk["assumptions"]))
        self.assertEqual(sorted(set(raw["exclusions"])), sorted(walk["exclusions"]))
        self.assertEqual(
            sorted(m["id"] for m in raw["mutants"]), [m["id"] for m in walk["mutants"]]
        )
        for mu in walk["mutants"]:
            source = next(m for m in raw["mutants"] if m["id"] == mu["id"])
            self.assertEqual({"id", "description", "kills"}, set(mu))
            self.assertEqual(source["description"], mu["description"])
            self.assertEqual(
                sorted({k["property"] for k in source["kills"]}), mu["kills"]
            )
        self.assertTrue(any(len(mu["kills"]) > 1 for mu in walk["mutants"]))

    def test_a_view_that_is_not_one_of_the_model_views_is_the_whole_section(self):
        with fresh_copy() as d:
            payload = payload_of(base_doc(d), "model")
        self.assertEqual(C.enc(payload), P.view_payload("model", payload, "full"))
        self.assertEqual(C.enc(payload), P.view_payload("model", payload, "axes"))


class ClosureViews(unittest.TestCase):
    def doc(self, d: str) -> dict:
        doc = base_doc(d)
        c = closure(doc)
        c["safety"].update(
            design="BLOCKED",
            design_note="the argument is incomplete",
            runtime_note="not built yet",
            assumptions=["input fits in memory"],
        )
        c["safety"]["basis"].update(
            proof="indeterminate", proof_note="the checker was not run"
        )
        return doc

    def row(self, doc: dict, view: str) -> dict:
        return P.view_payload("closure", payload_of(doc, "closure"), view)["closures"][
            0
        ]

    def test_the_axes_view_has_statement_design_runtime_and_the_notes_that_exist(self):
        with fresh_copy() as d:
            doc = self.doc(d)
            axes = self.row(doc, "axes")
        safety = axes["safety"]
        self.assertEqual(
            {"statement", "design", "runtime", "design_note", "runtime_note"},
            set(safety),
        )
        self.assertEqual(
            ("BLOCKED", "the argument is incomplete", "not built yet"),
            (safety["design"], safety["design_note"], safety["runtime_note"]),
        )
        plain = axes["inhabitation"]
        self.assertEqual(
            {"statement", "design", "runtime"}
            | ({"runtime_note"} if "runtime_note" in plain else set()),
            set(plain),
        )
        self.assertFalse(
            any(
                v is None
                for c in axes.values()
                if isinstance(c, dict)
                for v in c.values()
            ),
            "an absent note is left out, never null",
        )

    def test_the_readable_view_adds_what_each_claim_rests_on_its_proof_note_and_its_assumptions_only_when_there_are_some(
        self,
    ):
        with fresh_copy() as d:
            doc = self.doc(d)
            readable = self.row(doc, "readable")
            axes = self.row(doc, "axes")
        safety = readable["safety"]
        self.assertTrue(
            safety["rests_on"].startswith("checked, proof "), safety["rests_on"]
        )
        self.assertEqual("the checker was not run", safety["proof_note"])
        self.assertEqual(["input fits in memory"], safety["assumptions"])
        for plain_view in (axes,):
            for cname in ("safety", "inhabitation", "public_reachability", "liveness"):
                self.assertTrue(
                    {"rests_on", "proof_note", "assumptions"}.isdisjoint(
                        plain_view[cname]
                    ),
                    cname,
                )
        raw = closure(doc)
        for cname in ("inhabitation", "public_reachability", "liveness"):
            c, basis = readable[cname], raw[cname]["basis"]
            self.assertEqual(
                basis["tag"]
                + (f", proof {basis['proof']}" if basis["tag"] == "checked" else ""),
                c["rests_on"],
                cname,
            )
            self.assertEqual(bool(raw[cname]["assumptions"]), "assumptions" in c, cname)
            self.assertNotIn("proof_note", c, cname)

    def test_a_claim_that_is_not_a_claim_is_shown_as_it_was_written_and_the_closures_come_out_sorted_by_subject(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            closure(doc)["liveness"] = {
                "tag": "not_applicable",
                "reason": "a one-shot function",
            }
            second = copy.deepcopy(closure(doc))
            second["subject"] = "a second subject that sorts before the first"
            second["liveness"] = {"tag": "inherited"}
            second["safety"]["statement"] = "another statement"
            section(doc, "closure")["closures"].append(second)
            view = P.view_payload("closure", payload_of(doc, "closure"), "axes")
        self.assertEqual(
            sorted(c["subject"] for c in view["closures"]),
            [c["subject"] for c in view["closures"]],
        )
        self.assertEqual({"tag": "inherited"}, view["closures"][0]["liveness"])
        self.assertEqual(
            {"tag": "not_applicable", "reason": "a one-shot function"},
            view["closures"][1]["liveness"],
        )

    def test_only_the_closure_section_has_closure_views_and_a_view_with_another_name_is_the_whole_section(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        payload = h[("closure", "shared")].status.payload
        self.assertEqual(C.enc(payload), P.view_payload("closure", payload, "full"))
        laws = h[("laws", "shared")].status.payload
        for view in ("axes", "readable"):
            self.assertEqual(C.enc(laws), P.view_payload("laws", laws, view))


class WhatARoleReceives(unittest.TestCase):
    def test_the_sections_come_out_in_kind_then_scope_order_whatever_the_order_of_the_handoff_and_a_missing_one_is_marked(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            for scope in ("value:3", "value:1", "value:2"):
                twin = copy.deepcopy(section(doc, "laws"))
                doc["sections"].append(
                    {
                        "kind": "laws",
                        "scope": scope,
                        "status": {"tag": "applicable", "payload": twin},
                    }
                )
            doc["sections"] = [s for s in doc["sections"] if s["kind"] != "closure"]
            h = decode(doc)
        for handoff in (h, dict(reversed(list(h.items())))):
            rows = P.project(handoff, "atd")
            self.assertEqual(
                [(k, s) for k, s, *_ in rows], sorted((k, s) for k, s, *_ in rows)
            )
            self.assertEqual(
                ["laws@shared", "laws@value:1", "laws@value:2", "laws@value:3"],
                [f"{k}@{s}" for k, s, *_ in rows if k == "laws"],
            )
            marker = next(r for r in rows if r[0] == "closure")
            self.assertEqual(("closure", "shared", "-", "axes"), marker[:4])
            self.assertIn("UNASSESSED", marker[4])
            self.assertIn("do not read this as not applicable", marker[4]["UNASSESSED"])
            self.assertEqual(
                [("closure", "shared"), ("construction", "shared"), ("laws", "shared")][
                    :0
                ],
                [],
            )
        self.assertEqual(
            P.project(h, "atd"), P.project(dict(reversed(list(h.items()))), "atd")
        )

    def test_the_sections_are_ordered_by_scope_and_never_by_what_they_contain(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            for i, scope in enumerate(("value:1", "value:2", "value:3", "value:4")):
                twin = copy.deepcopy(section(doc, "laws"))
                twin["laws"][0]["statement"] = (
                    f"{twin['laws'][0]['statement']} ({scope} variant {i})"
                )
                doc["sections"].append(
                    {
                        "kind": "laws",
                        "scope": scope,
                        "status": {"tag": "applicable", "payload": twin},
                    }
                )
            h = decode(doc)
        rows = [r for r in P.project(h, "atd") if r[0] == "laws"]
        self.assertEqual(
            ["shared", "value:1", "value:2", "value:3", "value:4"], [r[1] for r in rows]
        )
        shas = [r[2] for r in rows]
        self.assertNotEqual(
            sorted(shas),
            shas,
            "this example needs contents whose hashes are NOT in scope order, or it cannot tell the two orders apart",
        )

    def test_the_section_a_projection_refuses_first_is_the_same_whatever_the_order_of_the_handoff(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        for handoff in (h, dict(reversed(list(h.items())))):
            with self.assertRaises(P.ProjectionError) as cm:
                P.project(handoff, "software_crafter")
            self.assertEqual("construction", cm.exception.defect.where)

    def test_a_section_that_is_there_is_never_marked_unassessed_and_one_that_is_not_needed_is_never_shown(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        rows = P.project(h, "atd")
        self.assertEqual(
            {"laws", "construction", "model", "closure"}, {r[0] for r in rows}
        )
        self.assertFalse(any("UNASSESSED" in r[4] for r in rows))
        self.assertEqual([], P.project(h, "examiner"))
        human = P.project(h, "human", base_dir=None)
        self.assertEqual({"scenarios", "closure"}, {r[0] for r in human})

    def test_a_value_keeps_the_shared_sections_and_its_own_and_no_value_keeps_every_scope(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            for scope in ("value:1", "value:2"):
                doc["sections"].append(
                    {
                        "kind": "laws",
                        "scope": scope,
                        "status": {
                            "tag": "applicable",
                            "payload": copy.deepcopy(section(doc, "laws")),
                        },
                    }
                )
            h = decode(doc)

        def scopes(value):
            return [s for k, s, *_ in P.project(h, "atd", value=value) if k == "laws"]

        self.assertEqual(["shared", "value:1"], scopes(1))
        self.assertEqual(["shared", "value:2"], scopes(2))
        self.assertEqual(["shared"], scopes(3))
        self.assertEqual(["shared", "value:1", "value:2"], scopes(None))

    def test_a_not_applicable_section_is_shown_with_its_reason_and_the_hash_of_what_is_shown(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            for s in doc["sections"]:
                if s["kind"] == "construction":
                    s["status"] = {
                        "tag": "not_applicable",
                        "reason": "nothing is constructed here",
                    }
            h = decode(doc)
        rows = {r[0]: r for r in P.project(h, "atd")}
        self.assertEqual(
            {"not_applicable": "nothing is constructed here"}, rows["construction"][4]
        )
        for r in rows.values():
            self.assertEqual(C.sha(r[4]), r[2])

    def test_the_crafter_sees_only_what_it_owns_and_a_missing_target_list_is_refused(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        with self.assertRaises(P.ProjectionError):
            P.project(h, "software_crafter")
        rows = {
            r[0]: r for r in P.project(h, "software_crafter", targets=["pagination.py"])
        }
        self.assertEqual({"laws", "construction", "model"}, set(rows))
        self.assertEqual(
            ("owned", "owned", "interface"),
            tuple(rows[k][3] for k in ("laws", "construction", "model")),
        )

    def test_the_scenarios_a_person_judges_carry_the_run_the_model_and_what_the_mutant_does_and_say_when_they_cannot_be_rendered(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            h = decode(doc)
            rows = P.project(h, "human", base_dir=d)
            blind = P.project(h, "human", base_dir=None)
            description = next(
                m for m in model_(doc, "walk")["mutants"] if m["id"] == "M1"
            )["description"]
            run = run_(doc, "K-M1-pageMatchesSpec")
        by = {
            s["id"]: s
            for s in next(r for r in rows if r[0] == "scenarios")[4]["scenarios"]
        }
        self.assertEqual(["SC1", "SC2"], sorted(by))
        mutant, example = by["SC1"], by["SC2"]
        self.assertEqual(description, mutant["what_the_bug_does"])
        self.assertNotIn("what_the_bug_does", example)
        self.assertEqual(run["id"], mutant["run"])
        self.assertEqual(" ".join(run["argv"]), mutant["tool"]["command"])
        self.assertEqual({"name", "version", "command"}, set(mutant["tool"]))
        self.assertTrue(mutant["events"])
        self.assertNotIn("NOT_RENDERED", mutant)
        for s in next(r for r in blind if r[0] == "scenarios")[4]["scenarios"]:
            self.assertNotIn("events", s)
            self.assertIn("no directory was given", s["NOT_RENDERED"])
        self.assertEqual(
            sorted(by),
            [
                s["id"]
                for s in next(r for r in rows if r[0] == "scenarios")[4]["scenarios"]
            ],
        )

    def test_a_mutant_whose_description_is_unknown_says_nothing_rather_than_none(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            run_(doc, "K-M1-pageMatchesSpec")["variant"] = (
                "mutant:M99"  # rule R4 reports it; the projection must still print something sane
            )
            h = decode(doc)
            rows = P.project(h, "human", base_dir=d)
        by = {
            s["id"]: s
            for s in next(r for r in rows if r[0] == "scenarios")[4]["scenarios"]
        }
        self.assertEqual("", by["SC1"].get("what_the_bug_does", ""))


class ThePrompt(unittest.TestCase):
    def test_a_role_that_receives_nothing_is_told_so_and_one_that_receives_sections_is_told_each_view_and_decision(
        self,
    ):
        none = P.grammar_what("examiner")
        self.assertIn(
            "- none: this role receives no design section, by construction.", none
        )
        for role in ("atd", "software_crafter", "human"):
            text = P.grammar_what(role)
            self.assertNotIn("- none:", text, role)
            self.assertTrue(
                text.startswith(
                    "You receive these sections of the handoff and decide as follows:"
                )
            )
            for kind, (view, decision, _basis) in P.CONSUMERS[role].items():
                self.assertIn(f"- {kind} (view {view}): {decision}.", text)
        architect = P.grammar_what("architect")
        for rid in P.RU.RULES:
            self.assertEqual(1, len(re.findall(rf"^- {rid}: ", architect, re.M)), rid)
        self.assertIn("Section `construction` is optional.", architect)

    def test_the_prompt_joins_the_template_the_sections_and_the_context_in_a_fixed_shape(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            law(doc, "L1")["statement"] = "A page equals the filter \u00e9 definition"
            h = decode(doc)
            text = P.compose(
                "atd",
                h,
                "  Write the oracle.  ",
                {"b": "2", "a": "1"},
                "  Keep it short.  ",
                targets=V9_TARGETS,
            )
        self.assertTrue(
            text.startswith(
                "=== [T] WHAT (atd) ===\nWrite the oracle.\nYou receive these sections"
            )
        )
        self.assertTrue(
            text.endswith("=== [C] orchestrator ===\na: 1\nb: 2\nKeep it short.\n")
        )
        found = blocks(text)
        self.assertEqual(
            ["closure@shared", "construction@shared", "laws@shared", "model@shared"],
            list(found),
        )
        for header in re.findall(r"=== \[H\] .* ===", text):
            self.assertRegex(header, r"^=== \[H\] \S+ sha=[0-9a-f]{12} view=\S+ ===$")
        for kind, content in found.items():
            self.assertEqual(
                json.dumps(
                    json.loads(content),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
                content,
                kind,
            )
        self.assertIn("\u00e9", found["laws@shared"])
        self.assertNotIn("\\u00e9", text)
        shas = re.findall(r"sha=([0-9a-f]+) ", text)
        self.assertTrue(all(len(x) == 12 for x in shas))

    def test_the_orchestrator_part_has_exactly_the_parts_that_were_given(self):
        with fresh_copy() as d:
            h = decode(base_doc(d))

        def tail(**kw):
            return P.compose("examiner", h, "T", **kw).split(
                "=== [C] orchestrator ===\n"
            )[1]

        self.assertEqual("\n", tail())
        self.assertEqual("a: 1\n\n", tail(context={"a": "1"}))
        self.assertEqual("only this\n", tail(verbatim="  only this  "))
        self.assertEqual(
            "a: 1\nonly this\n", tail(context={"a": "1"}, verbatim="only this")
        )
        self.assertEqual("a: 1\nb: 2\n\n", tail(context={"b": "2", "a": "1"}))


class TheSummaryAndTheHumanViews(unittest.TestCase):
    def test_the_summary_counts_every_claim_proof_scenario_and_run_from_the_document(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            c = closure(doc)
            other = copy.deepcopy(c)
            other["subject"] = "another subject"
            other["liveness"] = {"tag": "inherited"}
            c["safety"].update(design="BLOCKED", design_note="not closed")
            c["safety"]["basis"].update(proof="indeterminate", proof_note="not run")
            c["inhabitation"].update(design="BLOCKED", design_note="no route")
            c["liveness"] = {"tag": "not_applicable", "reason": "a one-shot function"}
            section(doc, "closure")["closures"].append(other)
            judged(doc, "SC1", judgment="correct")
            summary = P.summary(decode(doc))
            runs = section(doc, "receipts")["runs"]
            claims = [
                x[k]
                for x in section(doc, "closure")["closures"]
                for k in ("safety", "inhabitation", "public_reachability", "liveness")
            ]
            subject = c["subject"]
        design = collections.Counter(x["design"] for x in claims if x["tag"] == "claim")
        proofs = collections.Counter(
            x["basis"]["proof"]
            for x in claims
            if x["tag"] == "claim" and x["basis"]["tag"] == "checked"
        )
        self.assertEqual(
            (2, 4, 1), (design["BLOCKED"], design["PASS"], proofs["indeterminate"])
        )
        self.assertEqual(
            {
                "PASS": design["PASS"],
                "BLOCKED": design["BLOCKED"],
                "NOT_APPLICABLE": 1,
                "INHERITED": 1,
            },
            summary["claims"],
        )
        self.assertEqual(
            {
                "passed": proofs["passed"],
                "indeterminate": proofs["indeterminate"],
                "refuted": 0,
            },
            summary["proofs"],
        )
        self.assertEqual({"correct": 1, "pending": 1}, summary["scenarios"])
        self.assertEqual(
            {
                "kept_output": sum(1 for r in runs if r.get("artifacts")),
                "claim": sum(1 for r in runs if not r.get("artifacts")),
            },
            summary["runs"],
        )
        self.assertEqual(
            {"shared/" + subject, "shared/another subject"}, set(summary["closure"])
        )
        row, again = (
            summary["closure"]["shared/" + subject],
            summary["closure"]["shared/another subject"],
        )
        self.assertEqual("NOT_APPLICABLE", row["liveness"])
        self.assertEqual("INHERITED", again["liveness"])
        self.assertEqual(
            "BLOCKED/" + c["safety"]["runtime"] + " (checked, proof indeterminate)",
            row["safety"],
        )
        self.assertEqual(
            "PASS/" + other["safety"]["runtime"] + " (checked, proof passed)",
            again["safety"],
        )
        self.assertEqual(
            "PASS/" + c["public_reachability"]["runtime"] + " (path)",
            row["public_reachability"],
        )

    def test_the_summary_says_which_sections_are_applicable_which_are_not_and_which_are_missing_in_the_order_of_the_grammar(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            for s in doc["sections"]:
                if s["kind"] == "construction":
                    s["status"] = {
                        "tag": "not_applicable",
                        "reason": "nothing constructed",
                    }
            doc["sections"] = [
                s for s in doc["sections"] if s["kind"] not in ("scenarios", "closure")
            ]
            h = decode(doc)
            summary = P.summary(h)
        self.assertEqual(
            "not_applicable: nothing constructed",
            summary["sections"]["construction@shared"],
        )
        self.assertEqual("applicable", summary["sections"]["laws@shared"])
        self.assertEqual(["closure", "scenarios"], summary["missing_shared"])
        self.assertEqual(sorted(summary["sections"]), list(summary["sections"]))
        self.assertEqual(
            json.dumps(summary),
            json.dumps(P.summary(dict(reversed(list(h.items()))))),
            "the same bytes, in the same order, whatever the order of the handoff",
        )

    def test_the_markdown_has_one_block_per_section_with_the_facts_a_person_reads_and_a_blank_line_between_blocks(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            for s in doc["sections"]:
                if s["kind"] == "construction":
                    s["status"] = {
                        "tag": "not_applicable",
                        "reason": "nothing constructed",
                    }
            h = decode(doc)
            text = P.render_markdown(h, d)
            flipped = P.render_markdown(dict(reversed(list(h.items()))), d)
            raw = {
                "model": model_(doc, "walk"),
                "runs": section(doc, "receipts")["runs"],
            }
        self.assertEqual(text, flipped)
        headings = re.findall(r"^## (\w+) \((\S+)\)$", text, re.M)
        self.assertEqual(sorted(headings), headings)
        self.assertEqual(6, len(headings))
        self.assertIn(
            "## construction (shared)\nNot applicable: nothing constructed\n\n## laws (shared)",
            text,
        )
        self.assertRegex(text, r"- observation O1: .+ -> .+; cannot distinguish: ")
        self.assertRegex(text, r"- constructor paginate: ")
        self.assertRegex(
            text, r"- law L1 \[\w+, \w+\] owner pagination\.py::paginate: "
        )
        self.assertRegex(text, r"- refuted RC2 \(.+\): .+; counterexample: ")
        walk = raw["model"]
        self.assertIn(
            f"- model walk (quint) at {walk['path']}, identity {T.sha256_text(walk['text'])[:12]}; leaves out: {'; '.join(sorted(set(walk['exclusions'])))}",
            text,
        )
        for mu in walk["mutants"]:
            self.assertIn(
                f"  - mutant {mu['id']}: {mu['description']}; kills "
                + ", ".join(sorted(k["property"] for k in mu["kills"])),
                text,
            )
        self.assertRegex(
            text,
            r"- the page of items that paginate returns and the CLI prints\n  - safety: design PASS, runtime \w+ \(checked, proof passed\): ",
        )
        self.assertRegex(
            text, r"  - liveness: design \w+, runtime \w+ \(checked, proof passed\): "
        )
        kept = next(r for r in raw["runs"] if r.get("artifacts"))
        claim = next(r for r in raw["runs"] if not r.get("artifacts"))
        self.assertIn(
            f"- run {kept['id']} [{kept['tool']} {kept['tool_version']}, {kept['target']}, {kept['variant']}] exit {kept['exit_status']} {kept['result_class']} (output kept): "
            + " ".join(kept["argv"]),
            text,
        )
        self.assertIn(
            f"- run {claim['id']} [{claim['tool']} {claim['tool_version']}, {claim['target']}, {claim['variant']}] exit {claim['exit_status']} {claim['result_class']} "
            "(claim, no output): " + " ".join(claim["argv"]),
            text,
        )
        self.assertIn("[mutant; run K-M1-pageMatchesSpec; model ", text)
        self.assertIn("What this bug does: ", text)

    def test_every_block_of_the_markdown_ends_with_one_blank_line_and_the_construction_claims_are_listed_with_their_residue(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            text = P.render_markdown(decode(doc), d)
            construction = section(doc, "construction")
        self.assertEqual(6, len(text.split("\n\n## ")))
        self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))
        for c in construction["claims"]:
            self.assertIn(
                f"- {c['id']} [{c['strength']}] owner {c['owner']}: {c['proposition']}; harm: {c['harm']}",
                text,
            )
        self.assertTrue(construction["unknown"])
        for u in construction["unknown"]:
            self.assertIn(
                f"- unknown: {u['state']} (risk owner: {u['risk_owner']})", text
            )

    def test_a_model_that_leaves_nothing_out_says_so_and_a_closure_class_that_is_not_a_claim_says_what_it_is(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            for m in section(doc, "model")["models"]:
                m["exclusions"] = []
            closure(doc)["liveness"] = {
                "tag": "not_applicable",
                "reason": "a one-shot function",
            }
            second = copy.deepcopy(closure(doc))
            second["subject"] = "another subject"
            second["liveness"] = {"tag": "inherited"}
            section(doc, "closure")["closures"].append(second)
            text = P.render_markdown(decode(doc), d)
        self.assertIn("; leaves out: nothing", text)
        self.assertIn("  - liveness: not_applicable: a one-shot function", text)
        self.assertIn("  - liveness: inherited\n", text)

    def test_a_scenario_that_cannot_be_rendered_is_listed_with_its_title_its_kind_and_the_reason_in_both_views(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            h = decode(doc)
            md = P.render_markdown(h, None)
            page = P.render_html(h, None)
        titles = [s["title"] for s in section(doc, "scenarios")["scenarios"]]
        for sc in section(doc, "scenarios")["scenarios"]:
            self.assertIn(f"{sc['title']} [{sc['kind']}]: not rendered: trace ", md)
        self.assertIn("<h2>Not rendered</h2><ul>", page)
        for title in titles:
            self.assertEqual(1, page.count(f"<li>{title}: trace "), title)

    def test_the_page_lists_the_scenarios_in_id_order_whatever_the_order_of_the_handoff(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
            page = P.render_html(h, d)
            flipped = P.render_html(dict(reversed(list(h.items()))), d)
            titles = [
                s.title
                for s in sorted(
                    h[("scenarios", "shared")].status.payload.scenarios,
                    key=lambda s: s.id,
                )
            ]
        self.assertEqual(page, flipped)
        self.assertEqual(
            titles,
            re.findall(r"<h2>(.*?)</h2>", page.replace("&#x27;", "'"))[: len(titles)],
        )

    def test_the_page_lists_the_scenarios_of_every_scope_in_scope_order_and_each_scope_in_id_order(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            twin = copy.deepcopy(section(doc, "scenarios"))
            for i, sc in enumerate(twin["scenarios"]):
                sc["id"] = f"V{i}"
                sc["title"] = f"value scenario {i}"
            doc["sections"].append(
                {
                    "kind": "scenarios",
                    "scope": "value:1",
                    "status": {"tag": "applicable", "payload": twin},
                }
            )
            h = decode(doc)
            page = P.render_html(h, d)
            flipped = P.render_html(dict(reversed(list(h.items()))), d)
            shared = [
                s.title
                for s in sorted(
                    h[("scenarios", "shared")].status.payload.scenarios,
                    key=lambda s: s.id,
                )
            ]
        self.assertEqual(page, flipped)
        titles = re.findall(r"<h2>(.*?)</h2>", page.replace("&#x27;", "'"))
        self.assertEqual(shared + ["value scenario 0", "value scenario 1"], titles[:4])

    def test_the_crafters_read_the_object_oriented_fixture_through_their_own_targets_alone(
        self,
    ):
        h = decode(read(OO))
        for role in ("software_crafter", "functional_crafter"):
            rows = P.project(h, role, targets=["inventory.py"])
            self.assertEqual(
                {"laws", "construction", "model"},
                {r[0] for r in rows if "UNASSESSED" not in r[4]} | {r[0] for r in rows},
            )
            laws = next(r for r in rows if r[0] == "laws")[4]
            owners = {x["owner"].split("::")[0].split(":")[0] for x in laws["laws"]}
            self.assertEqual({"inventory.py"}, owners)


class OwnedVocabulary(unittest.TestCase):
    def test_value_owned_law_keeps_used_shared_vocabulary_without_unrelated_laws(self):
        from dataclasses import replace

        h = decode(read(OO))
        entry = h[("laws", "shared")]
        shared = entry.status.payload
        shared_obs, shared_ctor = shared.observations[0], shared.constructors[0]
        h[("laws", "shared")] = replace(
            entry,
            status=T.Applicable(
                payload=replace(
                    shared,
                    laws=tuple(replace(law, owner="other.py") for law in shared.laws),
                )
            ),
        )
        local_obs = replace(shared_obs, id="LocalObs")
        local_ctor = replace(shared_ctor, id="LocalCtor")
        owned = replace(
            shared,
            observations=(local_obs,),
            constructors=(local_ctor,),
            equality=replace(shared.equality, under=(local_obs.id,)),
            laws=(
                replace(
                    shared.laws[0],
                    id="ValueLaw",
                    owner="mine.py",
                    uses=(shared_obs.id, shared_ctor.id),
                ),
            ),
        )
        h[("laws", "value:1")] = T.Entry(
            kind="laws", scope="value:1", status=T.Applicable(payload=owned)
        )
        h[("laws", "value:2")] = T.Entry(
            kind="laws", scope="value:2", status=T.Applicable(payload=owned)
        )
        rows = P.project(h, "software_crafter", value=1, targets=["mine.py"])
        shown = next(row[4] for row in rows if row[:2] == ("laws", "value:1"))
        self.assertEqual([shared_obs.id], [o["id"] for o in shown["observations"]])
        self.assertEqual([shared_ctor.id], [c["id"] for c in shown["constructors"]])
        self.assertEqual(["ValueLaw"], [law["id"] for law in shown["laws"]])
        self.assertFalse(any(row[1] == "value:2" for row in rows))
        self.assertFalse(
            next(row[4] for row in rows if row[:2] == ("laws", "shared"))["laws"]
        )


if __name__ == "__main__":
    unittest.main()
