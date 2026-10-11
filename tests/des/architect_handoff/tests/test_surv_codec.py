"""What the decoder says about a value it refuses, and what the canonical form is.

A first tool-chosen mutation run showed that no test read these facts: every refusal needs its defect (a refusal without one lets a
malformed section vanish), a value with a defect is never returned as valid, the bounds of numbers, the order and bytes of the
canonical form, the identity of a handoff and the words of a merge conflict.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_codec
"""

from __future__ import annotations

import copy
import dataclasses as dc
import json
import os
import random
import tempfile
import typing as t
import unittest
from pathlib import Path

from tests.des.architect_handoff.tests.test_g10 import (
    base_doc,
    decode,
    fresh_copy,
)

from des.application.architect_handoff import g10_codec as C
from des.application.architect_handoff import g10_types as T


MAX = 10**15
RUN = {
    "id": "R1",
    "tool": "script",
    "tool_version": "tool 1.0",
    "target": "prototype",
    "variant": "fixed",
    "argv": ["x"],
    "exit_status": 0,
    "result_class": "ok",
    "checks": [],
}
SCENARIO = {
    "id": "S1",
    "title": "A walk",
    "source_run": "R1",
    "kind": "example",
    "review": {"tag": "pending"},
}


def read(tp, value, path="$"):
    ds: list = []
    out = C.dec(tp, value, path, ds)
    return out, ds


def run_with(**over) -> dict:
    return {**RUN, **over}


def rules(ds) -> list[str]:
    return [d.rule for d in ds]


def section_doc(*sections) -> dict:
    return {"sections": list(sections)}


def sec(kind="laws", scope="shared", status=None) -> dict:
    return {
        "kind": kind,
        "scope": scope,
        "status": {"tag": "not_applicable", "reason": "none"}
        if status is None
        else status,
    }


def collect(o, path: list, out: list) -> None:
    """Every object inside a JSON value, with the path that leads to it."""
    if isinstance(o, dict):
        out.append((path, o))
        for k, v in o.items():
            collect(v, [*path, k], out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            collect(v, [*path, i], out)


class NumberBounds(unittest.TestCase):
    def test_an_integer_may_be_as_large_as_ten_to_the_fifteenth_and_no_larger(self):
        for n in (MAX, -MAX, 0, 1):
            out, ds = read(T.Run, run_with(exit_status=n))
            self.assertEqual([], ds, n)
            self.assertEqual(n, out.exit_status)
        for n in (MAX + 1, -MAX - 1):
            out, ds = read(T.Run, run_with(exit_status=n), "$.run")
            self.assertIs(C.BAD, out)
            self.assertEqual(["G9"], rules(ds), n)
            self.assertEqual("$.run.exit_status", ds[0].where)
            self.assertIn("larger than 10^15", ds[0].what)

    def test_a_count_must_be_positive_and_a_boolean_is_not_an_integer(self):
        self.assertEqual([], read(T.Measure, {"kind": "states", "value": 1})[1])
        for bad in (0, -3):
            out, ds = read(T.Measure, {"kind": "states", "value": bad})
            self.assertIs(C.BAD, out)
            self.assertEqual(["G9"], rules(ds))
            self.assertIn(f"{bad} is not positive", ds[0].what)
        for bad in (True, "1", 1.0, None, [1]):
            out, ds = read(T.Measure, {"kind": "states", "value": bad})
            self.assertIs(C.BAD, out, repr(bad))
            self.assertEqual(["G3"], rules(ds), repr(bad))
            self.assertIn("expected an integer", ds[0].what)

    def test_a_duration_is_a_finite_number_from_zero_to_ten_to_the_fifteenth(self):
        for good in (0, 0.0, 1, 2.5, MAX):
            out, ds = read(T.Run, run_with(duration_s=good))
            self.assertEqual([], ds, good)
            self.assertEqual(float(good), out.duration_s)
            self.assertIsInstance(out.duration_s, float)
        for bad, rule, said in (
            (MAX + 1, "G9", "larger than 10^15"),
            (-1, "G9", "finite number >= 0"),
            (-0.001, "G9", "finite number >= 0"),
            (float("inf"), "G9", "finite number >= 0"),
            (float("nan"), "G9", "finite number >= 0"),
            (True, "G3", "expected a number"),
            ("1", "G3", "expected a number"),
            ([1], "G3", "expected a number"),
        ):
            out, ds = read(T.Run, run_with(duration_s=bad), "$.run")
            self.assertIs(C.BAD, out, repr(bad))
            self.assertEqual([rule], rules(ds), repr(bad))
            self.assertIn(said, ds[0].what, repr(bad))
            self.assertEqual("$.run.duration_s", ds[0].where)


class EveryRefusalSaysWhy(unittest.TestCase):
    """A refusal without a defect lets a malformed section disappear without a word: each shape error has its own message."""

    def test_a_variant_needs_a_known_tag(self):
        for bad, what in (
            ({"tag": "nope"}, "unknown tag 'nope'"),
            ({}, "a variant without a `tag`"),
            ("pending", "a variant without a `tag`"),
        ):
            out, ds = read(T.Scenario, {**SCENARIO, "review": bad}, "$.s")
            self.assertIs(C.BAD, out)
            self.assertEqual(["G1"], rules(ds))
            self.assertEqual("$.s.review", ds[0].where)
            self.assertIn(what, ds[0].what)
            self.assertIn("pending, judged", ds[0].how)

    def test_a_record_is_an_object_and_a_collection_is_a_list_and_a_closed_word_is_one_of_its_words(
        self,
    ):
        out, ds = read(T.Scenario, [], "$.s")
        self.assertEqual((C.BAD, ["G3"]), (out, rules(ds)))
        self.assertIn("expected an object for Scenario", ds[0].what)
        out, ds = read(T.Receipts, {"runs": "x"}, "$.r")
        self.assertEqual((C.BAD, ["G3"], "$.r.runs"), (out, rules(ds), ds[0].where))
        self.assertIn("expected a list", ds[0].what)
        out, ds = read(T.Receipts, {"runs": []}, "$.r")
        self.assertEqual((C.BAD, ["G8"]), (out, rules(ds)))
        out, ds = read(T.Scenario, {**SCENARIO, "kind": "bogus"}, "$.s")
        self.assertEqual((C.BAD, ["G2"], "$.s.kind"), (out, rules(ds), ds[0].where))
        self.assertIn("example", ds[0].how)

    def test_a_wrong_tag_an_unknown_field_and_a_missing_field_are_each_one_defect_and_never_a_valid_value(
        self,
    ):
        out, ds = read(T.Pending, {"tag": "judged"}, "$.p")
        self.assertEqual(
            (C.BAD, ["G1"], "$.p.tag"), (out, rules(ds), ds[0].where)
        )  # one defect: the tag is not also "not allowed" a second time
        self.assertIn("tag 'judged' is not allowed here", ds[0].what)
        self.assertIn("'pending'", ds[0].how)
        self.assertIsInstance(read(T.Pending, {"tag": "pending"})[0], T.Pending)
        self.assertIsInstance(read(T.Pending, {})[0], T.Pending)
        out, ds = read(T.Pending, {"tag": "pending", "extra": 1}, "$.p")
        self.assertEqual((C.BAD, ["G4"], "$.p.extra"), (out, rules(ds), ds[0].where))
        out, ds = read(
            T.Scenario, {k: v for k, v in SCENARIO.items() if k != "title"}, "$.s"
        )
        self.assertEqual((C.BAD, ["G5"], "$.s.title"), (out, rules(ds), ds[0].where))
        self.assertIn("`title`", ds[0].how)

    def test_a_defect_always_comes_with_a_refusal_and_a_refusal_always_with_a_defect(
        self,
    ):
        rng = random.Random(7)
        with fresh_copy() as d:
            doc = base_doc(d)
        wrong = (
            None,
            0,
            -1,
            "",
            "x",
            True,
            [],
            {},
            [None],
            {"tag": "nope"},
            10**16,
            1.5,
        )
        looked = 0
        for s in doc["sections"]:
            payload = s["status"]["payload"]
            kind = s["kind"]
            nodes: list = []
            collect(payload, [], nodes)
            for _ in range(60):
                bad = copy.deepcopy(payload)
                path, _node = rng.choice(nodes)
                target = bad
                for step in path:
                    target = target[step]
                how = rng.choice(("drop", "extra", "replace", "tag"))
                if how == "drop" and target:
                    del target[rng.choice(sorted(target))]
                elif how == "extra":
                    target["zz_extra"] = 1
                elif how == "tag" and "tag" in target:
                    target["tag"] = "other"
                elif path:
                    parent = bad
                    for step in path[:-1]:
                        parent = parent[step]
                    parent[path[-1]] = rng.choice(wrong)
                else:
                    bad = rng.choice(wrong)
                out, ds = read(T.PAYLOAD[kind], bad)
                self.assertEqual(
                    out is C.BAD, bool(ds), (kind, path, how, [x.what for x in ds])
                )
                looked += 1
        self.assertGreater(looked, 250)


class DecodeOfSections(unittest.TestCase):
    def test_a_section_without_a_proper_status_says_which_status_and_why(self):
        for status in ({}, {"tag": "maybe"}, "applicable"):
            out, ds = C.decode_handoff(section_doc(sec(status=status)))
            self.assertIsNone(out)
            self.assertEqual(["G1"], rules(ds), status)
            self.assertEqual("$.sections[0].status", ds[0].where)
            self.assertIn("status needs tag", ds[0].what)

    def test_an_applicable_status_is_exactly_a_tag_and_a_payload(self):
        out, ds = C.decode_handoff(
            section_doc(
                sec(status={"tag": "applicable", "payload": {}, "extra": 1}),
                sec(kind="model", status={"tag": "applicable"}),
            )
        )
        self.assertIsNone(out)
        self.assertEqual(["G4", "G4"], rules(ds))
        self.assertEqual(
            ["$.sections[0].status", "$.sections[1].status"], [x.where for x in ds]
        )
        self.assertIn("applicable is exactly {tag, payload}", ds[0].what)

    def test_a_malformed_payload_is_reported_at_its_path_and_an_unknown_kind_never_reaches_the_payload_decoder(
        self,
    ):
        out, ds = C.decode_handoff(
            section_doc(
                sec(
                    "laws",
                    status={"tag": "applicable", "payload": {"observations": "x"}},
                )
            )
        )
        self.assertIsNone(out)
        self.assertTrue(ds)
        self.assertTrue(
            all(x.where.startswith("$.sections[0].status.payload") for x in ds),
            [x.where for x in ds],
        )
        self.assertIn(
            "$.sections[0].status.payload.observations", [x.where for x in ds]
        )
        out, ds = C.decode_handoff(
            section_doc(sec("nope", status={"tag": "applicable", "payload": {}}))
        )
        self.assertEqual(
            (None, ["G2"], "$.sections[0].kind"), (out, rules(ds), ds[0].where)
        )
        self.assertIn("'nope'", ds[0].what)

    def test_a_section_that_cannot_be_read_is_never_counted_as_a_second_copy_of_another(
        self,
    ):
        bad_scope = C.decode_handoff(
            section_doc(sec(scope="nowhere"), sec(scope="nowhere"))
        )[1]
        self.assertEqual(["G10", "G10"], rules(bad_scope))
        self.assertEqual(
            ["$.sections[0].scope", "$.sections[1].scope"], [x.where for x in bad_scope]
        )
        bad_kind = C.decode_handoff(section_doc(sec(kind="nope"), sec(kind="nope")))[1]
        self.assertEqual(["G2", "G2"], rules(bad_kind))
        bad_status = C.decode_handoff(
            section_doc(
                sec(status={"tag": "not_applicable"}),
                sec(status={"tag": "not_applicable"}),
            )
        )[1]
        self.assertEqual(["G5", "G5"], rules(bad_status))
        twice = C.decode_handoff(section_doc(sec(), sec()))[1]
        self.assertEqual(["G6"], rules(twice))
        self.assertEqual("$.sections[1]", twice[0].where)
        self.assertIn("laws@shared appears twice", twice[0].what)

    def test_only_a_document_of_sections_is_a_document(self):
        for bad in (None, [], {}, {"sections": {}}, {"sections": [], "extra": 1}):
            out, ds = C.decode_handoff(bad)
            self.assertEqual((None, ["G4"]), (out, rules(ds)), bad)
        self.assertEqual(["G4"], rules(C.decode_handoff(section_doc(5))[1]))
        self.assertEqual(
            ["G4"], rules(C.decode_handoff(section_doc({"kind": "laws"}))[1])
        )


class AuthoringOfModels(unittest.TestCase):
    def doc_with(self, *models) -> dict:
        return {
            "sections": [
                {
                    "kind": "model",
                    "scope": "shared",
                    "status": {
                        "tag": "applicable",
                        "payload": {"models": list(models)},
                    },
                }
            ]
        }

    def test_a_model_is_read_from_its_file_and_a_model_that_has_its_text_is_left_alone(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "m.qnt"), "wb") as fh:
                fh.write(b"module M {}\n")
            doc = self.doc_with(
                {"id": "a", "text_file": "m.qnt"},
                {"id": "b", "text": "inline"},
                {"id": "c", "text": "kept", "text_file": "m.qnt"},
                "not a model",
            )
            self.assertEqual([], C.resolve_authoring(doc, d))
        models = doc["sections"][0]["status"]["payload"]["models"]
        self.assertEqual({"id": "a", "text": "module M {}\n"}, models[0])
        self.assertEqual({"id": "b", "text": "inline"}, models[1])
        self.assertEqual({"id": "c", "text": "kept", "text_file": "m.qnt"}, models[2])

    def test_a_model_file_that_cannot_be_read_says_what_went_wrong(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "binary.qnt"), "wb") as fh:
                fh.write(b"\xff\xfe\x00")
            (Path(d) / "dir.qnt").mkdir()
            said = {}
            for name in ("absent.qnt", "binary.qnt", "dir.qnt", "../escape.qnt", 5):
                doc = self.doc_with({"id": "a", "text_file": name})
                ds = C.resolve_authoring(doc, d)
                self.assertEqual(["G11"], rules(ds), name)
                said[name] = ds[0].what
        self.assertEqual(
            "cannot read absent.qnt: No such file or directory", said["absent.qnt"]
        )
        self.assertEqual("cannot read binary.qnt: not UTF-8 text", said["binary.qnt"])
        self.assertIn("cannot read dir.qnt: Is a directory", said["dir.qnt"])
        self.assertIn("is not a file inside the directory", said["../escape.qnt"])
        self.assertIn("is not a file inside the directory", said[5])


class CanonicalForm(unittest.TestCase):
    def test_the_canonical_text_is_compact_json_with_sorted_keys_and_real_characters(
        self,
    ):
        run = read(T.Run, run_with(argv=["caf\u00e9"], duration_s=1.5))[0]
        text = C.canon(run)
        self.assertEqual(
            text,
            json.dumps(
                json.loads(text),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
        )
        self.assertNotEqual(
            list(RUN),
            sorted(RUN),
            "the field order of a run is not the sorted one, so the bytes show that keys are sorted",
        )
        self.assertIn("caf\u00e9", text)
        self.assertNotIn("\\u00e9", text)

    def test_a_set_is_written_in_the_order_of_the_text_of_its_items_and_a_sequence_keeps_its_order(
        self,
    ):
        self.assertEqual(
            ["z", "\u00e9"], C.enc(("\u00e9", "z"))
        )  # by code point, not by escape
        self.assertEqual(["b", "a", "b"], C.enc(("b", "a", "b"), "argv"))
        self.assertEqual(["a", "b"], C.enc(("b", "a", "b")))

    def test_a_decoded_value_holds_every_set_in_canonical_order_and_every_sequence_in_its_own(
        self,
    ):
        raw = run_with(argv=["b", "a", "b"], checks=["z", "y", "z", "\u00e9", "a"])
        run = read(T.Run, raw)[0]
        self.assertEqual(("b", "a", "b"), run.argv)
        self.assertEqual(("z", "y", "z", "\u00e9", "a"), run.checks)
        ordered = C.canonical(run)
        self.assertEqual(("b", "a", "b"), ordered.argv)  # argv is a sequence
        self.assertEqual(
            ("a", "y", "z", "z", "\u00e9"), ordered.checks
        )  # a set: by canonical text, a repeat stays
        self.assertIsInstance(ordered, T.Run)
        self.assertEqual(ordered, C.canonical(ordered))
        self.assertEqual(run.id, ordered.id)

    def test_a_decoded_document_lists_its_sections_and_its_sets_in_one_order_whatever_the_order_written(
        self,
    ):
        sections = [
            sec("model", "value:2"),
            sec("laws", "shared"),
            sec("model", "shared"),
            sec("laws", "value:1"),
        ]
        forward = C.decode_handoff(section_doc(*sections))[0]
        backward = C.decode_handoff(section_doc(*reversed(sections)))[0]
        self.assertEqual(sorted(forward), list(forward))
        self.assertEqual(list(forward), list(backward))
        self.assertEqual(forward, backward)
        flipped = dict(reversed(list(forward.items())))
        order = [(s["kind"], s["scope"]) for s in C.to_json(flipped)["sections"]]
        self.assertEqual(sorted(order), order)
        self.assertEqual(C.to_json(forward), C.to_json(flipped))

    def test_the_order_a_decoded_value_holds_is_the_order_it_is_written_in_for_every_set_of_the_fixture(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        seen: list[tuple[str | None, list, list]] = []

        def walk(o, field=None):
            if dc.is_dataclass(o) and not isinstance(o, type):
                for f in dc.fields(o):
                    walk(getattr(o, f.name), f.name)
            elif isinstance(o, tuple):
                if field not in T.SEQUENCE_FIELDS:
                    held: list = []
                    for x in o:
                        e = C.enc(x)
                        if (
                            not held or held[-1] != e
                        ):  # equal items are adjacent in canonical order; `enc` writes a repeat once
                            held.append(e)
                    seen.append((field, held, C.enc(o, field)))
                for x in o:
                    walk(x)

        for entry in h.values():
            walk(entry)
        self.assertGreater(len(seen), 50)
        self.assertTrue(
            any(
                len(held) > 1 and all(isinstance(x, dict) for x in held)
                for _, held, _ in seen
            ),
            "the fixture has sets of records",
        )
        for field, held, written in seen:
            self.assertEqual(held, written, field)

    def test_an_optional_field_and_an_either_of_two_records_are_both_unions_and_nothing_else_is(
        self,
    ):
        self.assertTrue(C.is_union(t.get_origin(t.get_type_hints(T.Run)["measure"])))
        self.assertTrue(C.is_union(t.get_origin(t.Optional[int])))  # noqa: UP045 - the legacy typing.Union origin is a distinct decoder contract
        self.assertTrue(C.is_union(t.get_origin(int | str)))
        for not_a_union in (
            None,
            int,
            tuple,
            t.get_origin(tuple[int, ...]),
            t.get_origin(t.Literal["a"]),
        ):
            self.assertFalse(C.is_union(not_a_union), not_a_union)

    def test_when_two_items_share_a_key_the_one_with_the_greatest_canonical_text_is_found_whatever_the_order(
        self,
    ):
        items = [
            {"id": "x", "note": "a"},
            {"id": "x", "note": "b"},
            {"id": "y", "note": "c"},
        ]
        for order in (
            items,
            list(reversed(items)),
            [items[2], items[0], items[1]],
            [items[1], items[2], items[0]],
        ):
            found = C.index_by(order, lambda o: o["id"])
            self.assertEqual(["x", "y"], sorted(found))
            self.assertEqual("b", found["x"]["note"])


class Strings(unittest.TestCase):
    def test_a_string_must_be_text_that_is_not_blank_and_has_the_shape_its_field_asks_for(
        self,
    ):
        cases = (
            ("title", 5, "G3", "expected a string"),
            ("title", None, "G3", "expected a string"),
            ("title", "\ud800", "G13", "unpaired surrogate"),
            ("title", "", "G7", "the string is blank"),
            ("title", " \t\n", "G7", "the string is blank"),
            ("id", "1 bad", "G10", "is not a valid ID"),
            ("id", 7, "G10", "is not a valid ID"),
            ("source_run", "bad id", "G10", "is not a valid ID"),
        )
        for field, value, rule, said in cases:
            out, ds = read(T.Scenario, {**SCENARIO, field: value}, "$.s")
            self.assertIs(C.BAD, out, (field, value))
            self.assertEqual([rule], rules(ds), (field, value))
            self.assertIn(said, ds[0].what)
            self.assertEqual(f"$.s.{field}", ds[0].where)
        out, ds = read(T.Run, run_with(variant="mutant 1"), "$.r")
        self.assertEqual((C.BAD, ["G10"], "$.r.variant"), (out, rules(ds), ds[0].where))
        self.assertIn("does not match", ds[0].what)
        self.assertEqual([], read(T.Scenario, {**SCENARIO, "title": " a "})[1])

    def test_an_optional_field_may_be_written_as_null_and_a_required_one_may_not(self):
        out, ds = read(
            T.Run,
            run_with(
                model_id=None,
                seed=None,
                duration_s=None,
                measure=None,
                model_sha256=None,
            ),
        )
        self.assertEqual([], ds)
        self.assertEqual(
            (None, None, None, None, None),
            (out.model_id, out.seed, out.duration_s, out.measure, out.model_sha256),
        )
        out, ds = read(T.Run, run_with(variant=None), "$.r")
        self.assertEqual((C.BAD, ["G3"]), (out, rules(ds)))

    def test_a_text_is_unicode_text_when_it_can_be_written_as_utf8(self):
        self.assertTrue(C._is_text("caf\u00e9 \U0001f600"))
        self.assertFalse(C._is_text("\ud800"))


class AuthoringInput(unittest.TestCase):
    def test_what_is_not_a_document_of_sections_has_nothing_to_resolve_and_no_defect(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            for doc in (
                None,
                [],
                "x",
                {},
                {"sections": 5},
                {
                    "sections": [
                        None,
                        5,
                        {"status": 3},
                        {"status": {"payload": []}},
                        {"status": {"payload": {"models": 5}}},
                    ]
                },
            ):
                self.assertEqual([], C.resolve_authoring(doc, d), doc)


class Merge(unittest.TestCase):
    def test_two_different_contents_under_one_key_are_refused_and_the_message_names_the_key(
        self,
    ):
        a = C.decode_handoff(
            section_doc(sec(status={"tag": "not_applicable", "reason": "one"}))
        )[0]
        b = C.decode_handoff(
            section_doc(sec(status={"tag": "not_applicable", "reason": "another"}))
        )[0]
        with self.assertRaises(C.MergeConflict) as cm:
            C.merge(a, b)
        self.assertEqual("laws@shared", cm.exception.defect.where)
        self.assertIn(
            "section laws@shared has two different contents", cm.exception.defect.what
        )
        self.assertIn(
            "WHAT: section laws@shared has two different contents", str(cm.exception)
        )
        self.assertEqual(a, C.merge(a, a))
        both = C.merge(a, C.decode_handoff(section_doc(sec("model")))[0])
        self.assertEqual([("laws", "shared"), ("model", "shared")], sorted(both))


if __name__ == "__main__":
    unittest.main()
