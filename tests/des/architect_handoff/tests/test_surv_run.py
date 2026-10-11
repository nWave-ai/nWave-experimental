"""What `g10 run` and `g10 record` leave behind and tell, beyond the cases of tests/test_run.py.

A first tool-chosen mutation run showed that no test read these facts: the exit status and hash a refusal reports, the bounds of the
timeout, the file modes, the order of the preflight, the lock being released, the evidence rules on a trace that is not a violation.
The commands are small python scripts and a fake `quint`, so nothing here needs quint, a network or more than a second.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_run
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from des.application.architect_handoff import g10_run as RUN


ROOT = str(Path(RUN.__file__).resolve().parents[3])

PY = sys.executable
VERSION = [PY, "-c", "print('tool 1.0')"]
KEPT_EMPTY = b"\n--- stderr ---\n"  # what an output artifact holds for a command that printed nothing


def script(body: str) -> list[str]:
    return [PY, "-c", body]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Sidecar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="g10-surv-run-")
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    # This helper exposes the original receipt writer's distinct metadata inputs
    # so every retained refusal/observation case can vary its declared stimulus.
    def go(  # noqa: PLR0913, PLR0917
        self,
        run_id: str = "R1",
        argv=None,
        tool: str = "script",
        target: str = "prototype",
        variant: str = "fixed",
        directory=None,
        **kw,
    ):
        kw.setdefault("version_argv", VERSION)
        return RUN.execute(
            directory or self.dir,
            run_id,
            tool,
            target,
            variant,
            argv or script("pass"),
            **kw,
        )

    def note(self, run_id: str = "A1", directory=None, **kw):
        return RUN.record_authored(
            directory or self.dir,
            run_id,
            "script",
            "tool 1.0",
            "prototype",
            "fixed",
            ["x"],
            0,
            "ok",
            **kw,
        )

    def refused(self, rule: str, call, *args, **kw):
        with self.assertRaises(RUN.RunError) as cm:
            call(*args, **kw)
        self.assertEqual(rule, cm.exception.defect.rule, cm.exception.defect.what)
        return cm.exception.defect

    def receipts_path(self) -> str:
        return os.path.join(self.dir, RUN.RECEIPTS_FILE)

    def recorded_ids(self) -> list[str]:
        with open(self.receipts_path(), encoding="utf-8") as fh:
            return sorted(
                r["id"]
                for r in json.load(fh)["sections"][0]["status"]["payload"]["runs"]
            )

    def marker(self) -> str:
        return os.path.join(self.dir, "ran.marker")

    def marking(self, extra: str = "") -> list[str]:
        return script(f"open({self.marker()!r}, 'w').close(); {extra}")


class Timeout(Sidecar):
    def test_a_timeout_is_a_whole_number_of_seconds_from_one_to_a_day_and_is_checked_before_anything_runs(
        self,
    ):
        for bad in (0, -5, 86401, 1.5, "5", None):
            d = self.refused("RUN6", self.go, argv=self.marking(), timeout_s=bad)
            self.assertIn("1..86400", d.what)
            self.assertIn(repr(bad), d.what)
        self.assertFalse(
            os.path.exists(self.marker()), "a refused timeout must not run the command"
        )
        self.assertFalse(os.path.exists(self.receipts_path()))
        for good in (1, 86400):
            self.assertEqual("ok", self.go(f"T{good}", timeout_s=good).result_class)

    def test_the_error_of_a_refusal_carries_the_same_words_as_its_defect(self):
        with self.assertRaises(RUN.RunError) as cm:
            self.go(timeout_s=0)
        self.assertEqual(cm.exception.defect.what, str(cm.exception))


class VersionAndClass(Sidecar):
    def test_a_version_command_that_exits_non_zero_still_tells_its_version(self):
        run = self.go(version_argv=script("import sys; print('v9.9'); sys.exit(3)"))
        self.assertEqual("v9.9", run.tool_version)

    def test_the_class_of_a_result_comes_from_evidence_and_the_default_is_no_evidence(
        self,
    ):
        self.assertEqual("error", RUN.result_class("quint_run", 1, False))
        self.assertEqual(
            "violation", RUN.result_class("quint_verify", 1, False, evidence=True)
        )
        self.assertEqual("ok", RUN.result_class("quint_run", 0, False, evidence=True))
        self.assertEqual(
            "timeout", RUN.result_class("tlc", 124, True, violation_exit=124)
        )
        self.assertEqual(
            "violation", RUN.result_class("tlc", 7, False, violation_exit=7)
        )
        self.assertEqual("error", RUN.result_class("tlc", 8, False, violation_exit=7))
        self.assertEqual("error", RUN.result_class("tlc", 7, False))
        self.assertEqual(
            "error", RUN.result_class("quint_typecheck", 1, False, evidence=True)
        )


class QuintTrace(Sidecar):
    """With a kept trace, `violation` is what `#meta.status` says and nothing else (a fake `quint` writes the trace it is told to)."""

    def fake_quint(self, trace: str | None, code: int) -> str:
        bin_dir = os.path.join(self.dir, "bin")
        Path(bin_dir).mkdir(parents=True, exist_ok=True)
        path = os.path.join(bin_dir, "quint")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                f"#!{PY}\nimport os, sys\n"
                "if '--version' in sys.argv:\n    print('quint 9.9.9')\n    sys.exit(0)\n"
                "for a in sys.argv:\n    if a.startswith('--out-itf='):\n"
                f"        os.makedirs(os.path.dirname(a[10:]) or '.', exist_ok=True)\n        open(a[10:], 'w').write({trace!r})\n"
                f"sys.exit({code})\n"
            )
        Path(path).chmod(0o755)
        return path

    def quint_run(self, run_id: str, trace_body: str | None, code: int):
        quint = self.fake_quint(trace_body, code)
        return self.go(
            run_id,
            argv=[quint, "run", "m.qnt", f"--out-itf=traces/{run_id}.json"],
            tool="quint_run",
            target="model",
            variant="base",
            trace=f"traces/{run_id}.json",
            version_argv=None,
        )

    def test_only_a_trace_that_says_violation_makes_a_failing_run_a_violation(self):
        said = {}
        for name, body in (
            ("garbage", "not json"),
            ("list", "[1, 2]"),
            ("no_meta", '{"states": []}'),
            ("meta_is_text", '{"#meta": "x"}'),
            ("ok", '{"#meta": {"status": "ok"}}'),
            ("violation", '{"#meta": {"status": "violation"}}'),
        ):
            said[name] = self.quint_run(name.replace("_", "-"), body, 1).result_class
        self.assertEqual(
            {
                "garbage": "error",
                "list": "error",
                "no_meta": "error",
                "meta_is_text": "error",
                "ok": "error",
                "violation": "violation",
            },
            said,
        )

    def test_the_version_of_quint_is_the_one_its_own_binary_prints(self):
        self.assertEqual(
            "quint 9.9.9",
            self.quint_run("v", '{"#meta": {"status": "ok"}}', 0).tool_version,
        )


class WhatARefusalReports(Sidecar):
    def test_a_command_that_did_not_write_its_trace_reports_its_exit_and_the_hash_of_its_output(
        self,
    ):
        d = self.refused(
            "RUN3",
            self.go,
            "K",
            argv=script("import sys; print('hello'); sys.exit(3)"),
            trace="never.json",
        )
        self.assertIn("exit 3", d.what)
        self.assertIn(sha(b"hello\n" + KEPT_EMPTY), d.what)
        self.assertIn("never.json", d.what)
        self.assertFalse(os.path.exists(self.receipts_path()))

    def test_an_output_that_cannot_be_kept_reports_the_exit_and_the_hash_of_what_the_command_printed(
        self,
    ):
        trick = script(
            "import shutil; shutil.rmtree('artifacts'); open('artifacts', 'w').write('x'); print('out')"
        )
        d = self.refused("RUN5", self.go, "W", argv=trick)
        self.assertIn("the command ran (exit 0", d.what)
        self.assertIn(sha(b"out\n" + KEPT_EMPTY), d.what)
        self.assertIn("cannot write the output artifact", d.what)
        self.assertFalse(os.path.exists(self.receipts_path()))

    def test_a_lock_that_cannot_be_opened_says_whether_a_command_had_run(self):
        (Path(self.dir) / ".g10.lock").mkdir()
        ran = self.refused("RUN5", self.go, "L", argv=script("print('x')"))
        self.assertIn("the command ran (exit 0", ran.what)
        self.assertIn(sha(b"x\n" + KEPT_EMPTY), ran.what)
        self.assertIn("cannot open the lock file", ran.what)
        claim = self.refused("RUN5", self.note, "C1")
        self.assertTrue(claim.what.startswith("cannot open the lock file"), claim.what)
        self.assertNotIn("the command ran", claim.what)

    def test_an_id_taken_by_another_writer_while_the_command_ran_reports_what_the_command_did(
        self,
    ):
        other = (
            f"import sys; sys.path.insert(0, {ROOT!r}); from des.application.architect_handoff import g10_run as R; "
            f"R.record_authored({self.dir!r}, 'RACE', 'script', 'v', 'prototype', 'fixed', ['x'], 0, 'ok'); print('mine')"
        )
        d = self.refused("RUN2", self.go, "RACE", argv=script(other))
        self.assertIn("already recorded", d.what)
        self.assertIn("the command ran (exit 0", d.what)
        self.assertIn(sha(b"mine\n" + KEPT_EMPTY), d.what)
        self.assertIn("NOTHING was recorded", d.what)
        self.assertEqual(["RACE"], self.recorded_ids())

    def test_a_claim_under_a_taken_id_is_refused_without_talking_about_a_command_and_replace_takes_the_place(
        self,
    ):
        self.note("A1")
        d = self.refused("RUN2", self.note, "A1")
        self.assertIn("already recorded", d.what)
        self.assertNotIn("the command ran", d.what)
        self.assertEqual("ok", self.note("A1", replace=True).result_class)
        self.assertEqual(["A1"], self.recorded_ids())

    def test_a_receipts_file_that_cannot_be_read_is_reported_by_its_first_defect(self):
        with open(self.receipts_path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual("G12", self.refused("G12", self.note).rule)
        with open(self.receipts_path(), "w", encoding="utf-8") as fh:
            json.dump({"sections": [{"kind": "x"}, {"kind": "y"}]}, fh)
        d = self.refused("G4", self.note)
        self.assertIn("$.sections[0]", d.where + d.what)  # the FIRST defect of two


class WhatIsLeftBehind(Sidecar):
    def test_the_files_are_world_readable_whatever_the_umask(self):
        old = os.umask(0o077)
        try:
            self.go("M1", argv=script("print('x')"))
        finally:
            os.umask(old)
        for name in (os.path.join("artifacts", "M1.out"), RUN.RECEIPTS_FILE):
            self.assertEqual(
                0o644, stat.S_IMODE((Path(self.dir) / name).stat().st_mode), name
            )

    def test_the_receipts_file_is_readable_json_with_sorted_keys_that_ends_with_a_newline(
        self,
    ):
        RUN.record_authored(
            self.dir,
            "A1",
            "script",
            "tool 1.0",
            "prototype",
            "fixed",
            ["caf\u00e9"],
            0,
            "ok",
        )
        with open(self.receipts_path(), "rb") as fh:
            raw = fh.read()
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertIn(
            "caf\u00e9".encode(), raw
        )  # a person reading the file sees the text, not an escape
        run = json.loads(raw)["sections"][0]["status"]["payload"]["runs"][0]
        self.assertEqual(sorted(run), list(run))

    def test_the_receipts_are_written_beside_themselves_even_when_the_working_directory_is_gone(
        self,
    ):
        gone, here = tempfile.mkdtemp(), os.getcwd()
        os.chdir(gone)
        Path(gone).rmdir()
        try:
            self.note("G1")
        finally:
            os.chdir(here)
        self.assertEqual(["G1"], self.recorded_ids())

    def test_the_probe_of_the_preflight_leaves_no_file_and_no_descriptor(self):
        self.go("P0")
        before = (
            len(list(Path("/proc/self/fd").iterdir()))
            if Path("/proc/self/fd").is_dir()
            else None
        )
        for i in range(8):
            self.note(f"P{i + 1}")
        self.assertEqual(
            [],
            [
                path.name
                for path in Path(self.dir).iterdir()
                if path.name.startswith(".g10-probe-") or path.name.endswith(".tmp")
            ],
        )
        if before is not None:
            self.assertEqual(before, len(list(Path("/proc/self/fd").iterdir())))

    def test_the_lock_is_released_after_every_write(self):
        code = (
            f"import sys; sys.path.insert(0, {ROOT!r}); from des.application.architect_handoff import g10_run as R; "
            f"[R.record_authored({self.dir!r}, i, 'script', 'v', 'prototype', 'fixed', ['x'], 0, 'ok') for i in ('A1', 'A2', 'A3')]"
        )
        subprocess.run(
            [PY, "-c", code], timeout=20, check=True
        )  # a leaked lock would block the second write forever: the timeout fails the test
        self.assertEqual(["A1", "A2", "A3"], self.recorded_ids())

    def test_the_duration_is_the_measured_time_in_milliseconds(self):
        durations = [
            self.go(f"D{i}", argv=script("import time; time.sleep(0.3)")).duration_s
            for i in range(3)
        ]
        for dur in durations:
            self.assertTrue(0.25 <= dur < 30, dur)
            self.assertEqual(dur, round(dur, 3))


class SidecarDirectory(Sidecar):
    def test_a_directory_that_does_not_exist_is_created_when_its_parent_does(self):
        made = os.path.join(self.dir, "side")
        self.go("N1", directory=made)
        self.note("N2", directory=os.path.join(self.dir, "side2"))
        self.assertTrue(os.path.isdir(made))
        self.assertTrue(
            os.path.isfile(os.path.join(self.dir, "side2", RUN.RECEIPTS_FILE))
        )

    def test_a_directory_whose_parent_does_not_exist_is_refused_and_the_command_does_not_run(
        self,
    ):
        d = self.refused(
            "RUN5",
            self.go,
            "N3",
            argv=self.marking(),
            directory=os.path.join(self.dir, "a", "b"),
        )
        self.assertIn("its parent", d.what)
        self.assertFalse(os.path.exists(self.marker()))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "a")))

    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0, "root writes anywhere"
    )
    def test_a_directory_that_cannot_be_written_is_refused_even_when_artifacts_is_already_there(
        self,
    ):
        (Path(self.dir) / "artifacts").mkdir()
        Path(self.dir).chmod(0o555)
        self.addCleanup(Path(self.dir).chmod, 0o755)
        d = self.refused("RUN5", self.go, "N4", argv=self.marking())
        self.assertIn("not writable", d.what)
        self.assertFalse(os.path.exists(self.marker()))


class TraceFreshnessCases(Sidecar):
    """A trace file that exists before the command runs is stale, unless the run being replaced cites exactly it."""

    def writes(self, name: str) -> list[str]:
        return script(
            f"import os, time; os.makedirs(os.path.dirname({name!r}) or '.', exist_ok=True); open({name!r}, 'w').write(str(time.time_ns()))"
        )

    def test_which_runs_may_refresh_an_existing_trace_in_place(self):
        self.go(
            "D0", argv=self.writes("d.json"), trace="d.json"
        )  # a decoy that comes first
        self.go("R1", argv=self.writes("t.json"), trace="t.json")
        self.go("R2", argv=self.writes("u.json"), trace="u.json")
        stale = lambda *a, **k: self.refused("RUN3", self.go, *a, **k)  # noqa: E731
        self.assertIn(
            "already exists",
            stale("R3", argv=self.writes("t.json"), trace="t.json").what,
        )  # another id, no replace
        stale(
            "R3", argv=self.writes("t.json"), trace="t.json", replace=True
        )  # replace of a run that does not exist
        stale(
            "R2", argv=self.writes("t.json"), trace="t.json", replace=True
        )  # the run replaced cites another file
        self.refused(
            "RUN2", self.go, "R1", argv=self.writes("t.json"), trace="t.json"
        )  # the same id, no replace
        self.assertEqual(
            "ok",
            self.go(
                "R1", argv=self.writes("t.json"), trace="t.json", replace=True
            ).result_class,
        )  # exactly its own file
        self.assertEqual(["D0", "R1", "R2"], self.recorded_ids())

    def test_a_trace_cited_by_two_runs_is_never_refreshed(self):
        self.go("R1", argv=self.writes("t.json"), trace="t.json")
        with open(self.receipts_path(), encoding="utf-8") as fh:
            doc = json.load(fh)
        runs = doc["sections"][0]["status"]["payload"]["runs"]
        twin = copy.deepcopy(runs[0])
        twin["id"] = "R9"
        runs.append(twin)
        with open(self.receipts_path(), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        self.refused(
            "RUN3",
            self.go,
            "R1",
            argv=self.writes("t.json"),
            trace="t.json",
            replace=True,
        )


class BeforeTheCommandRuns(Sidecar):
    def test_a_declared_model_id_that_is_not_an_id_is_refused_before_the_command_runs(
        self,
    ):
        self.refused("G10", self.go, argv=self.marking(), model_id="1 bad id")
        self.assertFalse(os.path.exists(self.marker()))

    def test_what_the_caller_declares_is_recorded_as_declared(self):
        run = self.go("S1", model_id="walk", seed="s7", measure=("states", 42))
        self.assertEqual(
            ("walk", "s7", "states", 42),
            (run.model_id, run.seed, run.measure.kind, run.measure.value),
        )
        bare = self.go("S2")
        self.assertEqual((None, None, None), (bare.model_id, bare.seed, bare.measure))

    def test_a_claim_records_what_it_is_given_and_nothing_else(self):
        run = self.note(
            "C1",
            model_id="walk",
            model_sha256="a" * 64,
            seed="s",
            duration_s=1.5,
            measure=("cases", 3),
        )
        self.assertEqual(
            ("walk", "a" * 64, "s", 1.5, "cases", 3, ()),
            (
                run.model_id,
                run.model_sha256,
                run.seed,
                run.duration_s,
                run.measure.kind,
                run.measure.value,
                run.artifacts,
            ),
        )
        bare = self.note("C2")
        self.assertEqual(
            (None, None, None, None, None),
            (
                bare.model_id,
                bare.model_sha256,
                bare.seed,
                bare.duration_s,
                bare.measure,
            ),
        )

    def test_the_hash_of_a_model_file_is_recorded_and_a_path_that_leaves_the_sidecar_is_refused_before_the_command_runs(
        self,
    ):
        with open(os.path.join(self.dir, "m.qnt"), "wb") as fh:
            fh.write(b"module M {}\n")
        self.assertEqual(
            sha(b"module M {}\n"), self.go("H1", model_file="m.qnt").model_sha256
        )
        self.assertIsNone(self.go("H2").model_sha256)
        parent = str(Path(self.dir).parent)
        outside = os.path.join(parent, f"outside-{os.path.basename(self.dir)}.qnt")
        with open(outside, "wb") as fh:
            fh.write(b"module Outside {}\n")
        self.addCleanup(Path(outside).unlink)
        for kw in (
            {"model_file": "../" + os.path.basename(outside)},
            {"model_file": outside},
            {"trace": "../escape.json"},
            {"trace": "/tmp/escape.json"},
        ):
            d = self.refused("RUN3", self.go, "H3", argv=self.marking(), **kw)
            self.assertIn("not a relative path", d.what)
            self.assertFalse(os.path.exists(self.marker()), kw)
        d = self.refused("RUN3", self.go, "H4", model_file="nothing-here.qnt")
        self.assertIn("cannot read the model file", d.what)


if __name__ == "__main__":
    unittest.main()
