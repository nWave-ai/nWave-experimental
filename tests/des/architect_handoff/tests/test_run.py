"""Regression tests for the receipts writer (review round 2: record only what was OBSERVED).

Each test fails on the old writer: exit 1 was blindly a `violation`, the tool version came from a PATH
lookup, a stale trace was hashed, half state was left behind on failure and parallel runs lost receipts.
Run: python3 -W ignore -m unittest tests.test_run"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = str(Path(__file__).resolve().parent)
G10 = "des.application.architect_handoff.g10"
PY = sys.executable
NODE_BIN = str(Path.home() / ".local/share/mise/installs/node/24/bin")
QUINT = shutil.which("quint", path=NODE_BIN + os.pathsep + os.environ.get("PATH", ""))

# a model whose invariant `positive` is violated after one step: quint exits 1 and prints `[violation] ...`
MODEL = """module M {
  var x: int

  action init = x' = 1

  action step = x' = x - 1

  val positive = x > 0
}
"""


def g10_env() -> dict:
    e = dict(os.environ)
    e["PATH"] = NODE_BIN + os.pathsep + e.get("PATH", "")
    return e


def g10(*args: str) -> subprocess.CompletedProcess:
    p = subprocess.run(
        [PY, "-W", "ignore", "-m", G10, *args],
        capture_output=True,
        text=True,
        env=g10_env(),
        timeout=60,
    )
    assert "Traceback" not in p.stderr, p.stderr
    return p


def receipts_of(directory: str) -> dict:
    with open(os.path.join(directory, "g10.receipts.json"), encoding="utf-8") as fh:
        return {
            r["id"]: r
            for r in json.load(fh)["sections"][0]["status"]["payload"]["runs"]
        }


class Side(unittest.TestCase):
    """A temp sidecar directory and the CLI helpers."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="g10-test-")
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def g10(self, *args: str) -> subprocess.CompletedProcess:
        return g10(*args)

    def receipts(self) -> dict:
        return receipts_of(self.dir)


@unittest.skipUnless(QUINT, "quint is not on PATH")
class QuintEvidence(Side):
    """`violation` is read from the output, never inferred from exit 1."""

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, "m.qnt"), "w", encoding="utf-8") as fh:
            fh.write(MODEL)

    def test_a_missing_file_is_an_error_not_a_violation(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "MISS",
            "--tool",
            "quint_run",
            "--target",
            "model",
            "--variant",
            "base",
            "--",
            "quint",
            "run",
            "does_not_exist.qnt",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertEqual(
            ("error", 1),
            (
                self.receipts()["MISS"]["result_class"],
                self.receipts()["MISS"]["exit_status"],
            ),
        )

    def test_a_real_violation_with_a_trace_comes_from_the_trace_meta(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "V",
            "--tool",
            "quint_run",
            "--target",
            "model",
            "--variant",
            "base",
            "--model-file",
            "m.qnt",
            "--trace",
            "tr.json",
            "--",
            "quint",
            "run",
            "m.qnt",
            "--invariant=positive",
            "--mbt",
            "--max-samples=50",
            "--max-steps=5",
            "--out-itf=tr.json",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertEqual("violation", self.receipts()["V"]["result_class"])

    def test_a_real_violation_without_a_trace_comes_from_the_violation_line(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "V2",
            "--tool",
            "quint_run",
            "--target",
            "model",
            "--variant",
            "base",
            "--model-file",
            "m.qnt",
            "--",
            "quint",
            "run",
            "m.qnt",
            "--invariant=positive",
            "--mbt",
            "--max-samples=50",
            "--max-steps=5",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertEqual("violation", self.receipts()["V2"]["result_class"])


@unittest.skipUnless(QUINT, "quint is not on PATH")
class ToolIdentity(Side):
    def setUp(self):
        super().setUp()

    def test_a_non_quint_command_is_refused_before_it_runs(self):
        marker = os.path.join(self.dir, "ran")
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "X",
            "--tool",
            "quint_run",
            "--target",
            "model",
            "--variant",
            "base",
            "--",
            "echo",
            "hi",
        )
        self.assertEqual(1, p.returncode)
        self.assertFalse(
            os.path.exists(marker), "the command ran although the receipt was refused"
        )
        self.assertFalse(os.path.exists(os.path.join(self.dir, "g10.receipts.json")))

    def test_the_quint_version_is_printed_by_argv0_not_by_a_path_lookup(self):
        # a decoy `quint` earlier on PATH must not be what the receipt cites
        decoy = os.path.join(self.dir, "bin")
        Path(decoy).mkdir()
        with open(os.path.join(decoy, "quint"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\necho decoy 0.0.0\n")
        (Path(decoy) / "quint").chmod(0o755)
        with open(os.path.join(self.dir, "m.qnt"), "w", encoding="utf-8") as fh:
            fh.write(MODEL)
        env = g10_env()
        env["PATH"] = decoy + os.pathsep + env["PATH"]
        p = subprocess.run(
            [
                PY,
                "-W",
                "ignore",
                "-m",
                G10,
                "run",
                "--dir",
                self.dir,
                "--id",
                "Q",
                "--tool",
                "quint_run",
                "--target",
                "model",
                "--variant",
                "base",
                "--model-file",
                "m.qnt",
                "--",
                QUINT,
                "run",
                "m.qnt",
                "--invariant=positive",
                "--mbt",
                "--max-samples=50",
                "--max-steps=5",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        with open(os.path.join(self.dir, "g10.receipts.json"), encoding="utf-8") as fh:
            got = {
                r["id"]: r
                for r in json.load(fh)["sections"][0]["status"]["payload"]["runs"]
            }["Q"]
        real = (
            subprocess.run(
                [QUINT, "--version"], capture_output=True, text=True, timeout=60
            )
            .stdout.strip()
            .splitlines()[0]
        )
        self.assertEqual(real, got["tool_version"])
        self.assertNotIn("decoy", got["tool_version"])


class TraceFreshness(Side):
    def test_a_stale_trace_is_refused_before_the_command_runs(self):
        with open(os.path.join(self.dir, "tr.json"), "w", encoding="utf-8") as fh:
            fh.write('{"#meta": {"status": "violation"}}')
        marker = os.path.join(self.dir, "ran")
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "S",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--trace",
            "tr.json",
            "--",
            PY,
            "-c",
            f"open({marker!r}, 'w')",
        )
        self.assertEqual(1, p.returncode)
        self.assertIn("already exists", p.stdout)
        self.assertFalse(
            os.path.exists(marker), "the command ran although the trace was stale"
        )

    def test_a_trace_the_command_did_not_write_records_nothing_and_changes_nothing(
        self,
    ):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "R",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--",
            PY,
            "-c",
            "print('first')",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        before = (
            self.receipts()["R"],
            open(os.path.join(self.dir, "artifacts", "R.out"), "rb").read(),
        )
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "R",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--trace",
            "tr.json",
            "--replace",
            "--",
            PY,
            "-c",
            "print('second')",
        )
        self.assertEqual(1, p.returncode)
        self.assertIn("NOTHING was recorded", p.stdout)
        after = (
            self.receipts()["R"],
            open(os.path.join(self.dir, "artifacts", "R.out"), "rb").read(),
        )
        self.assertEqual(before, after, "a failed run changed the recorded state")

    def test_a_replaced_run_keeps_its_old_trace_until_the_command_rewrites_it(self):
        def go(code, *extra):
            return self.g10(
                "run",
                "--dir",
                self.dir,
                "--id",
                "T",
                "--tool",
                "script",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--version-argv",
                f"{PY} --version",
                "--trace",
                "tr.json",
                *extra,
                "--",
                PY,
                "-c",
                code,
            )

        trace = os.path.join(self.dir, "tr.json")
        self.assertEqual(0, go("open('tr.json', 'w').write('{\"v\": 1}')").returncode)
        kept = (
            self.receipts()["T"],
            open(trace, "rb").read(),
            open(os.path.join(self.dir, "artifacts", "T.out"), "rb").read(),
        )
        p = go("print('does not touch the trace')", "--replace")
        self.assertEqual(1, p.returncode, p.stdout + p.stderr)
        self.assertIn("was not rewritten by the command", p.stdout)
        self.assertEqual(
            kept,
            (
                self.receipts()["T"],
                open(trace, "rb").read(),
                open(os.path.join(self.dir, "artifacts", "T.out"), "rb").read(),
            ),
            "a failed replacement changed the recorded state or deleted the old trace",
        )
        p = go(
            "open('tr.json', 'w').write('{\"v\": 1}')", "--replace"
        )  # the same bytes, written again by this command, are a fresh trace
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        p = go("open('tr.json', 'w').write('{\"v\": 2}')", "--replace")
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertEqual(b'{"v": 2}', open(trace, "rb").read())
        cited = next(
            a for a in self.receipts()["T"]["artifacts"] if a["role"] == "trace"
        )
        import hashlib

        self.assertEqual(hashlib.sha256(b'{"v": 2}').hexdigest(), cited["sha256"])


class UsageErrors(unittest.TestCase):
    """Bad --timeout / --measure values are usage errors (exit 2), never a traceback."""

    def test_bad_values_exit_two_without_a_traceback(self):
        for bad in (
            ["--timeout", "0"],
            ["--timeout", "-3"],
            ["--timeout", "99999999999999999999"],
            ["--measure", "states=\u00b2"],
            ["--measure", "states=\uff11\uff12\uff13"],
            ["--measure", "states=0"],
        ):
            with tempfile.TemporaryDirectory(prefix="g10-test-arg-") as d:
                with self.subTest(bad=bad):
                    p = subprocess.run(
                        [
                            PY,
                            "-W",
                            "ignore",
                            "-m",
                            G10,
                            "run",
                            "--dir",
                            d,
                            "--id",
                            "A",
                            "--tool",
                            "script",
                            "--target",
                            "prototype",
                            "--variant",
                            "fixed",
                            "--version-argv",
                            f"{PY} --version",
                            *bad,
                            "--",
                            PY,
                            "-c",
                            "print(1)",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertEqual(2, p.returncode, p.stdout + p.stderr)
                    self.assertNotIn("Traceback", p.stderr)
                    self.assertFalse(
                        os.path.exists(os.path.join(d, "g10.receipts.json"))
                    )


class RecordedFields(Side):
    """What the writer records beyond the result class: declarations echoed exactly, observations measured."""

    def test_seed_model_measure_and_duration_are_recorded(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "F",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--seed",
            "s7",
            "--model",
            "mm",
            "--measure",
            "states=42",
            "--",
            PY,
            "-c",
            "import time; time.sleep(0.05)",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        got = self.receipts()["F"]
        self.assertEqual("s7", got["seed"])
        self.assertEqual("mm", got["model_id"])
        self.assertEqual({"kind": "states", "value": 42}, got["measure"])
        self.assertIsInstance(got["duration_s"], (int, float))
        self.assertGreaterEqual(
            got["duration_s"], 0.05, "duration is measured, not echoed"
        )

    def test_a_declared_version_argv_is_honored_for_other_kinds(self):
        ver = os.path.join(self.dir, "ver.sh")
        with open(ver, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\necho mytool 9.9\n")
        Path(ver).chmod(0o755)
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "V",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            ver,
            "--",
            PY,
            "-c",
            "print(1)",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertEqual("mytool 9.9", self.receipts()["V"]["tool_version"])

    def test_a_version_command_that_prints_nothing_is_refused_with_no_receipt(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "N",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} -c pass",
            "--",
            PY,
            "-c",
            "print(1)",
        )
        self.assertEqual(1, p.returncode)
        self.assertIn("RUN1", p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "g10.receipts.json")))

    def test_a_timed_out_command_records_124_timeout_and_keeps_the_partial_output(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "TO",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--timeout",
            "4",
            "--",
            PY,
            "-c",
            "print('partial', flush=True); import time; time.sleep(60)",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        got = self.receipts()["TO"]
        self.assertEqual((124, "timeout"), (got["exit_status"], got["result_class"]))
        with open(os.path.join(self.dir, "artifacts", "TO.out"), "rb") as fh:
            self.assertIn(b"partial", fh.read())

    def test_the_kept_output_is_capped_at_four_million_bytes_per_stream(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "BIG",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--",
            PY,
            "-c",
            "import sys; sys.stdout.write('x'*4100000)",
        )
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        kept = os.path.join(self.dir, "artifacts", "BIG.out")
        with open(kept, "rb") as fh:
            raw = fh.read()
        self.assertEqual(4_000_000 + len(b"\n--- stderr ---\n"), len(raw))
        self.assertEqual(b"x" * 4_000_000, raw[:4_000_000])


class CheckMode(unittest.TestCase):
    def test_check_mode_accepts_only_auto_or_interactive(self):
        with tempfile.TemporaryDirectory(prefix="g10-test-mode-") as d:
            f = os.path.join(d, "g10.json")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write('{"sections": []}')
            p = subprocess.run(
                [PY, "-W", "ignore", "-m", G10, "check", "--mode", "bogus", f],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(2, p.returncode, p.stdout + p.stderr)
            self.assertNotIn("Traceback", p.stderr)


class FailureLeavesNoTrace(Side):
    def test_a_read_only_directory_is_refused_before_the_command_runs(self):
        if os.geteuid() == 0:
            self.skipTest("root writes through mode 0o555")
        ro = os.path.join(self._tmp.name, "ro")
        Path(ro).mkdir()
        Path(ro).chmod(0o555)
        self.addCleanup(Path(ro).chmod, 0o755)
        marker = os.path.join(ro, "ran")
        p = self.g10(
            "run",
            "--dir",
            ro,
            "--id",
            "A",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--",
            PY,
            "-c",
            f"open({marker!r}, 'w')",
        )
        self.assertEqual(1, p.returncode)
        self.assertFalse(
            os.path.exists(marker), "the command ran although nothing could be recorded"
        )
        p = self.g10(
            "record",
            "--dir",
            ro,
            "--id",
            "C",
            "--tool",
            "script",
            "--tool-version",
            "v",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--exit",
            "0",
            "--result",
            "ok",
            "--",
            PY,
            "-c",
            "pass",
        )
        self.assertEqual(1, p.returncode)

    def test_a_directory_without_a_parent_is_refused_without_a_traceback(self):
        p = self.g10(
            "run",
            "--dir",
            "/nonexistent/g10/x",
            "--id",
            "A",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--",
            PY,
            "-c",
            "print(1)",
        )
        self.assertEqual(1, p.returncode)
        p = self.g10(
            "record",
            "--dir",
            "/nonexistent/g10/x",
            "--id",
            "C",
            "--tool",
            "script",
            "--tool-version",
            "v",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--exit",
            "0",
            "--result",
            "ok",
            "--",
            PY,
            "-c",
            "pass",
        )
        self.assertEqual(1, p.returncode)

    def test_a_symlinked_artifacts_directory_is_refused_before_the_command_runs(self):
        victim_dir = os.path.join(self._tmp.name, "elsewhere")
        Path(victim_dir).mkdir()
        (Path(self.dir) / "artifacts").symlink_to(victim_dir)
        marker = os.path.join(self.dir, "ran")
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "A",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--",
            PY,
            "-c",
            f"open({marker!r}, 'w')",
        )
        self.assertEqual(1, p.returncode)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual([], list(Path(victim_dir).iterdir()))

    def test_a_symlinked_output_artifact_is_refused_and_the_victim_stays_identical(
        self,
    ):
        (Path(self.dir) / "artifacts").mkdir(parents=True)
        victim = os.path.join(self._tmp.name, "victim.txt")
        with open(victim, "wb") as fh:
            fh.write(b"do not touch\n")
        (Path(self.dir) / "artifacts/A.out").symlink_to(victim)
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "A",
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            "--",
            PY,
            "-c",
            "print('new')",
        )
        self.assertEqual(1, p.returncode)
        self.assertEqual(b"do not touch\n", open(victim, "rb").read())


class ParallelWriters(unittest.TestCase):
    def test_sixteen_parallel_runs_leave_sixteen_receipts(self):
        with tempfile.TemporaryDirectory(prefix="g10-test-par-") as d:
            procs = [
                subprocess.Popen(
                    [
                        PY,
                        "-W",
                        "ignore",
                        "-m",
                        G10,
                        "run",
                        "--dir",
                        d,
                        "--id",
                        f"P{i}",
                        "--tool",
                        "script",
                        "--target",
                        "prototype",
                        "--variant",
                        "fixed",
                        "--version-argv",
                        f"{PY} --version",
                        "--",
                        PY,
                        "-c",
                        f"print({i})",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=g10_env(),
                )
                for i in range(16)
            ]
            for p in procs:
                out, err = p.communicate(timeout=120)
                self.assertNotIn("Traceback", err, err)
                self.assertEqual(0, p.returncode, out + err)
            with open(os.path.join(d, "g10.receipts.json"), encoding="utf-8") as fh:
                runs = json.load(fh)["sections"][0]["status"]["payload"]["runs"]
            self.assertEqual(16, len(runs), f"lost receipts: {[r['id'] for r in runs]}")
            self.assertEqual({f"P{i}" for i in range(16)}, {r["id"] for r in runs})


class DeclaredViolationExit(Side):
    def _run(self, rid: str, *extra: str) -> subprocess.CompletedProcess:
        return self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            rid,
            "--tool",
            "script",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--version-argv",
            f"{PY} --version",
            *extra,
            "--",
            PY,
            "-c",
            "raise SystemExit(3)",
        )

    def test_a_declared_violation_exit_is_a_violation_and_without_it_an_error(self):
        p = self._run("D", "--violation-exit", "3")
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        p = self._run("U")
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        got = self.receipts()
        self.assertEqual("violation", got["D"]["result_class"])
        self.assertEqual("error", got["U"]["result_class"])

    def test_a_violation_exit_is_refused_for_quint_tools(self):
        p = self.g10(
            "run",
            "--dir",
            self.dir,
            "--id",
            "Q",
            "--tool",
            "quint_run",
            "--target",
            "model",
            "--variant",
            "base",
            "--violation-exit",
            "3",
            "--",
            "quint",
            "run",
            "m.qnt",
        )
        self.assertEqual(2, p.returncode)
        self.assertNotIn("Traceback", p.stderr)


if __name__ == "__main__":
    unittest.main()
