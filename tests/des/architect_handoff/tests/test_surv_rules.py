"""What the rule engine says and in which order: the facts a first tool-chosen mutation run showed no test was reading.

Rules ids were already tested one by one (tests/test_g10.py EveryRuleFires). These tests read the REST of what a consumer sees:
the order of the defects, the numbers and ids inside a message, and the list of checks that could not run.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_rules
"""

from __future__ import annotations

import copy
import random
import re
import unittest
from pathlib import Path

from tests.des.architect_handoff.tests.test_g10 import (
    CASES,
    V9_TARGETS,
    atom_,
    authored_run,
    base_doc,
    closure,
    decode,
    defects,
    fixture_catalog,
    fresh_copy,
    law,
    model_,
    run_,
    scn,
    section,
    shuffled,
)

from des.application.architect_handoff import g10_rules as RU


def facts(ds) -> list[tuple[str, str, str]]:
    return [(x.rule, x.where, x.what) for x in ds]


def of(ds, rule: str) -> list:
    return [x for x in ds if x.rule == rule]


def check(doc: dict, d: str | None, mode: str = "auto", targets=V9_TARGETS):
    return RU.check(decode(doc), targets, mode, d, fixture_catalog(doc))


def receipts_in(scope: str, *runs: dict) -> dict:
    return {
        "kind": "receipts",
        "scope": scope,
        "status": {"tag": "applicable", "payload": {"runs": list(runs)}},
    }


class OrderOfDefects(unittest.TestCase):
    def test_the_defects_of_every_rule_case_come_out_in_one_order_whatever_the_order_of_the_document(
        self,
    ):
        for rid, (mutate, kw) in CASES.items():
            with fresh_copy() as d:
                doc = base_doc(d)
                mutate(doc, d)
                mode = kw.get("mode", "auto")
                reference = facts(defects(doc, V9_TARGETS, mode, d))
                for seed in (1, 2, 3):
                    other = shuffled(copy.deepcopy(doc), random.Random(seed))
                    self.assertEqual(
                        reference,
                        facts(defects(other, V9_TARGETS, mode, d)),
                        f"rule {rid}, shuffle {seed}",
                    )

    def test_several_repeated_atom_names_are_reported_in_name_order(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            m = model_(doc, "walk")
            for name in ("n", "lim", "offset", "count", "page"):
                twin = copy.deepcopy(atom_(m, name))
                twin["symbol"] = f"another symbol for {name}"
                m["atoms"].append(twin)
            names = [
                re.search(r"atom name (\S+) repeats", x.what).group(1)
                for x in of(defects(doc, V9_TARGETS, "auto", d), "M1")
            ]
        self.assertEqual(["count", "lim", "n", "offset", "page"], names)

    def test_several_clashing_ids_in_the_laws_section_are_reported_in_id_order(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            for law_id, taken in (("L2", "O2"), ("L3", "G-CLI"), ("L4", "paginate")):
                law(doc, law_id)["id"] = taken
            where = [x.where for x in of(defects(doc, V9_TARGETS, "auto", d), "L1")]
        self.assertEqual(["laws:G-CLI", "laws:O2", "laws:paginate"], where)

    def test_defects_of_two_values_are_reported_value_one_first_whatever_the_order_of_the_sections(
        self,
    ):
        def bad_run(rid: str) -> dict:
            return authored_run(
                rid, exit_status=1
            )  # result_class ok with exit 1: rule R2

        for order in (("value:2", "value:1"), ("value:1", "value:2")):
            with fresh_copy() as d:
                doc = base_doc(d)
                for scope in order:
                    doc["sections"].append(receipts_in(scope, bad_run("V" + scope[-1])))
                where = [x.where for x in of(defects(doc, V9_TARGETS, "auto", d), "R2")]
            self.assertEqual(["receipts:V1", "receipts:V2"], where, order)

    def test_check_reads_a_handoff_as_a_value_whatever_the_order_of_its_sections_in_memory(
        self,
    ):
        for rid in ("R2", "L1", "S3"):
            mutate, kw = CASES[rid]
            with fresh_copy() as d:
                doc = base_doc(d)
                mutate(doc, d)
                for scope in ("value:2", "value:1"):
                    doc["sections"].append(
                        receipts_in(scope, authored_run("V" + scope[-1], exit_status=1))
                    )
                h = decode(doc)
                flipped = dict(reversed(list(h.items())))
                self.assertEqual(list(reversed(list(h))), list(flipped))
                self.assertEqual(
                    RU.check(
                        h, V9_TARGETS, kw.get("mode", "auto"), d, fixture_catalog(doc)
                    ),
                    RU.check(
                        flipped,
                        V9_TARGETS,
                        kw.get("mode", "auto"),
                        d,
                        fixture_catalog(doc),
                    ),
                    rid,
                )


class ScopedArtifactIdentity(unittest.TestCase):
    def test_same_run_id_in_distinct_scopes_cannot_share_an_output_artifact(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            output = Path(d) / "artifacts/VR.out"
            output.write_bytes(b"scoped output\n")
            import hashlib

            artifact = {
                "role": "output",
                "path": "artifacts/VR.out",
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
            for scope in ("value:1", "value:2"):
                doc["sections"].append(
                    receipts_in(
                        scope, authored_run("VR", artifacts=[artifact], argv=[scope])
                    )
                )
            clashes = [
                defect
                for defect in of(check(doc, d)[0], "R6")
                if "cited by runs" in defect.what
            ]
        self.assertEqual(2, len(clashes), clashes)
        self.assertTrue(
            all(
                "value:1" in defect.what and "value:2" in defect.what
                for defect in clashes
            )
        )


class ReceiptMessages(unittest.TestCase):
    def test_a_file_cited_by_two_runs_is_refused_naming_both_runs_in_id_order(self):
        for extra_ids in (("AA",), ("D3", "C2", "B1", "AA")):
            with fresh_copy() as d:
                doc = base_doc(d)
                for rid in extra_ids:
                    twin = copy.deepcopy(run_(doc, "EX1"))
                    twin["id"] = rid
                    section(doc, "receipts")["runs"].append(twin)
                shared = [
                    x
                    for x in of(defects(doc, V9_TARGETS, "auto", d), "R6")
                    if "is cited by runs" in x.what
                ]
            self.assertTrue(shared, extra_ids)
            listed = re.search(r"is cited by runs \[(.*?)\]", shared[0].what).group(1)
            self.assertEqual(
                sorted((*extra_ids, "EX1")),
                [x.strip("' ") for x in listed.split(",")],
                extra_ids,
            )

    def test_a_mutant_run_that_records_no_hash_and_one_that_records_the_unmutated_hash_are_told_apart(
        self,
    ):
        def mutant_run(sha):
            return authored_run(
                "RX",
                variant="mutant:M1",
                model_id="walk",
                exit_status=1,
                result_class="violation",
                model_sha256=sha,
            )

        with fresh_copy() as d:
            doc = base_doc(d)
            unmutated = next(
                m
                for m in decode(doc)[("model", "shared")].status.payload.models
                if m.id == "walk"
            ).sha256
            said = {}
            for label, sha in (
                ("none", None),
                ("unmutated", unmutated),
                ("mutated", "1" * 64),
            ):
                other = copy.deepcopy(doc)
                section(other, "receipts")["runs"].append(mutant_run(sha))
                said[label] = [
                    x.what
                    for x in of(defects(other, V9_TARGETS, "auto", d), "R5")
                    if x.where == "receipts:RX"
                ]
        self.assertEqual([], said["mutated"])
        self.assertEqual(1, len(said["none"]))
        self.assertIn("no model_sha256", said["none"][0])
        self.assertEqual(1, len(said["unmutated"]))
        self.assertIn("unmutated model", said["unmutated"][0])
        self.assertNotIn("no model_sha256", said["unmutated"][0])

    def test_the_closure_subject_of_a_repeated_closure_is_named_whole_even_when_it_holds_a_slash(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            closure(doc)["subject"] = "the pages and paginate/main"
            doc2 = copy.deepcopy(doc)
            section(doc2, "closure")["closures"].append(copy.deepcopy(closure(doc2)))
            repeated = of(defects(doc2, V9_TARGETS, "auto", d), "CL10")
        self.assertEqual(["closure@shared"], [x.where for x in repeated])
        self.assertIn("'the pages and paginate/main'", repeated[0].what)


class ClosureAndScenarioMessages(unittest.TestCase):
    def test_a_shared_closure_that_repeats_a_subject_cannot_inherit_from_its_own_twin(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            twin = copy.deepcopy(closure(doc))
            twin["liveness"] = {"tag": "inherited"}
            section(doc, "closure")["closures"].append(twin)
            ds = defects(doc, V9_TARGETS, "auto", d)
        self.assertEqual({"CL10", "CL8"}, {x.rule for x in ds})
        self.assertEqual(
            [
                "closure@shared[the page of items that paginate returns and the CLI prints].liveness"
            ],
            [x.where for x in of(ds, "CL8")],
        )

    def test_a_scenario_whose_run_keeps_no_trace_says_so_and_the_other_causes_do_not(
        self,
    ):
        def no_trace(doc, d):
            run = run_(doc, "EX1")
            run["artifacts"] = [a for a in run["artifacts"] if a["role"] != "trace"]

        def no_run(doc, d):
            scn(doc, "SC2")["source_run"] = "NOPE"

        def wrong_kind(doc, d):
            scn(doc, "SC2")["kind"] = "counterexample"

        said = {}
        for name, mutate in (
            ("no_trace", no_trace),
            ("no_run", no_run),
            ("wrong_kind", wrong_kind),
        ):
            with fresh_copy() as d:
                doc = base_doc(d)
                mutate(doc, d)
                said[name] = [
                    x.what
                    for x in of(defects(doc, V9_TARGETS, "auto", d), "S2")
                    if x.where == "scenarios:SC2"
                ]
        for name, whats in said.items():
            self.assertEqual(1, len(whats), (name, whats))
        self.assertIn("the run keeps no trace", said["no_trace"][0])
        self.assertNotIn("; the run keeps no trace", said["no_run"][0])
        self.assertIn("source_run NOPE", said["no_run"][0])
        self.assertNotIn("; the run keeps no trace", said["wrong_kind"][0])
        self.assertIn("kind counterexample", said["wrong_kind"][0])


class ChecksThatCouldNotRun(unittest.TestCase):
    """`check` returns, next to the defects, the checks it could not run and why; a consumer reads them as INDETERMINATE."""

    def test_without_the_sidecar_directory_the_kept_files_cannot_be_checked_and_the_report_says_so(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            without_dir = check(doc, None)[1]
            with_dir = check(doc, d)[1]
        self.assertEqual(
            1, len([x for x in without_dir if x.startswith("R6 and S3")]), without_dir
        )
        self.assertEqual([], with_dir)

    def test_no_kept_file_means_nothing_waits_for_the_sidecar_directory(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            for r in section(doc, "receipts")["runs"]:
                r["artifacts"] = []
            skipped = check(doc, None)[1]
        self.assertEqual([], [x for x in skipped if x.startswith("R6 and S3")], skipped)

    def test_two_scenarios_on_one_missing_trace_give_one_note_and_only_when_the_directory_is_given(
        self,
    ):
        def twin_scenario(doc):
            section(doc, "scenarios")["scenarios"].append(
                {
                    "id": "SC3",
                    "title": "The same walk, a second time",
                    "source_run": "EX1",
                    "kind": "example",
                    "review": {"tag": "pending"},
                }
            )

        with fresh_copy() as d:
            doc = base_doc(d)
            twin_scenario(doc)
            trace = next(
                a["path"] for a in run_(doc, "EX1")["artifacts"] if a["role"] == "trace"
            )
            (Path(d) / trace).unlink()
            notes = [x for x in check(doc, d)[1] if x.startswith("S3 for a scenario")]
            blind = [
                x for x in check(doc, None)[1] if x.startswith("S3 for a scenario")
            ]
        self.assertEqual(1, len(notes), notes)
        self.assertIn(trace, notes[0])
        self.assertIn("is not there", notes[0])
        self.assertEqual([], blind)

    def test_the_trace_of_each_missing_run_gets_its_own_note(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            traces = [
                a["path"]
                for rid in ("EX1", "K-M1-pageMatchesSpec")
                for a in run_(doc, rid)["artifacts"]
                if a["role"] == "trace"
            ]
            for p in traces:
                (Path(d) / p).unlink()
            notes = [x for x in check(doc, d)[1] if x.startswith("S3 for a scenario")]
        self.assertEqual(2, len(notes), notes)
        for p in traces:
            self.assertEqual(1, len([x for x in notes if p in x]), (p, notes))


if __name__ == "__main__":
    unittest.main()
