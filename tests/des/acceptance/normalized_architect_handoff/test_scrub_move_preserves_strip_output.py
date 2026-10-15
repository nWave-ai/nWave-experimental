"""The public strip's complete tracked-input result survives the scrub move.

Contract-shape: real-io. Driving port: scripts.release.strip_private_agents.strip.
This finite preserving-move observation is separate from installed-role wiring.
Both algorithms receive the same tracked catalog, agents and skills, not a
reconstructed fixture. The optional sibling role-skill registry is deliberately
absent in both temporary corpora, as are docs and every other unselected tree.
Private inputs and removed-report names never enter the committed expectation
or assertion diagnostics; only their aggregate identities do.
The frozen digests of original-R@5f882 and candidate-premove@aaacec7 are the
historical receipts of the one-time move proof. The permanent observation runs
the authentic frozen pre-move strip and the current strip on the current tracked
corpus and requires identical output, so lawful agent or skill edits on trunk do
not invalidate it; when the corpus equals a frozen receipt, its digests are also
checked. Original-source preservation is never feature RED.

The module's ``freeze_expectation`` is the authorized fixture-construction
surface, not a test runner. The receipt-local freezing entry point calls it.
It executes only the frozen strip to produce authentic golden data. Tests never
regenerate expectations. Observe this unchanged oracle before the move and
after the pure move, before installer behavior changes.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).parent / "fixture" / "scrub_move"
INPUT_SCOPES = (
    "nWave/framework-catalog.yaml",
    "nWave/agents",
    "nWave/skills",
)
PRIVACY_BASE = "5f882ba20da26d03312e1dc8736501cd8009488e"
GUARDS = (
    "tests/build/acceptance/test_strip_private_agents.py",
    "tests/build/acceptance/test_strip_scrubs_removed_skill_references.py",
    "tests/build/unit/test_is_public_skill_call_sites_pass_private_skills.py",
    "tests/installer/acceptance/private_skill_leak/steps/test_wheel_privacy.py",
    "tests/build/test_release_artifact_privacy_gates.py",
    "tests/plugins/unit/test_agent_catalog.py",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require(condition: bool, what: str, why: str, how: str) -> None:
    if not condition:
        raise AssertionError(f"WHAT: {what}\nWHY: {why}\nHOW: {how}")


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "the tracked input or frozen-base population could not be enumerated",
        "absence of a readable population is not evidence of preservation",
        "restore the declared Git workspace and privacy base, then rerun",
    )
    return result.stdout


@dataclass(frozen=True)
class TrackedStripInput:
    """Local private-capable bytes; only aggregate identities may leave here."""

    files: dict[str, bytes]

    @classmethod
    def read(cls, root: Path) -> TrackedStripInput:
        names = _git(root, "ls-files", "-z", "--", *INPUT_SCOPES)
        files: dict[str, bytes] = {}
        for raw in names.split(b"\0"):
            if not raw:
                continue
            relative = os.fsdecode(raw)
            path = root / relative
            _require(
                path.is_file() and not path.is_symlink(),
                "a tracked strip input is missing or is not a regular file",
                "the frozen byte census must contain every enumerated member",
                "restore the tracked candidate before freezing or observing it",
            )
            files[relative] = path.read_bytes()
        _require(
            all(
                any(name == scope or name.startswith(scope + "/") for name in files)
                for scope in INPUT_SCOPES
            ),
            "the tracked catalog/agent/skill population is incomplete",
            "an empty or incapable census cannot certify the preserving move",
            "restore all three declared tracked input scopes and rerun",
        )
        return cls(files)

    def identity(self) -> dict[str, object]:
        census = [[name, _sha(data)] for name, data in sorted(self.files.items())]
        return {
            "scopes": list(INPUT_SCOPES),
            "file_count": len(census),
            "sha256": _sha(_encoded(census)),
            "catalog_sha256": _sha(self.files[INPUT_SCOPES[0]]),
            "optional_registry": "absent",
        }

    def materialize(self, destination: Path) -> None:
        for relative, data in self.files.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def _tree(root: Path) -> dict[str, tuple[str, bytes]]:
    tree: dict[str, tuple[str, bytes]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            tree[relative] = ("symlink", os.fsencode(path.readlink()))
        elif path.is_dir():
            tree[relative] = ("directory", b"")
        elif path.is_file():
            tree[relative] = ("file", path.read_bytes())
        else:
            _require(
                False,
                "strip output contains a non-file/non-directory artifact",
                "complete output-tree preservation must not silently omit artifacts",
                "restore the declared regular-file strip output contract",
            )
    return tree


def _tree_identity(tree: dict[str, tuple[str, bytes]]) -> dict[str, object]:
    census = [[name, kind, _sha(data)] for name, (kind, data) in sorted(tree.items())]
    return {
        "entry_count": len(census),
        "file_count": sum(kind == "file" for kind, _ in tree.values()),
        "sha256": _sha(_encoded(census)),
    }


def _load_strip(path: Path, module_name: str) -> Callable:
    spec = importlib.util.spec_from_file_location(
        module_name, path, loader=SourceFileLoader(module_name, str(path))
    )
    _require(
        spec is not None and spec.loader is not None,
        "the declared strip entry point cannot be loaded",
        "an unavailable algorithm is not a preservation observation",
        "restore the frozen public code and the production strip entry point",
    )
    module = importlib.util.module_from_spec(spec)
    # Both copies deliberately use the same current shared filtering owner.
    # Golden tree/report identities catch changes in that owner only when the
    # current census equals a frozen historical vector (F-ia-vec5).
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            spec.loader.exec_module(module)
    return module.strip


def _strip_locally(strip: Callable, target: Path) -> dict[str, list[str]]:
    # Production prints removed paths. Never let private names enter pytest's
    # captured output, model-visible generation logs or a public receipt.
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                return strip(target)
            except Exception:
                raise AssertionError(
                    "WHAT: strip could not produce its complete tree/report\n"
                    "WHY: failed execution is not preserving-move evidence\n"
                    "HOW: restore the declared input and entry-point dependencies"
                ) from None


def _outside_workspace() -> tempfile.TemporaryDirectory:
    # Fixed OS temporary root, not pytest's possibly repository-local basetemp.
    temporary = tempfile.TemporaryDirectory(prefix="nwave-scrub-vector-", dir="/tmp")
    _require(
        not Path(temporary.name).resolve().is_relative_to(ROOT.resolve()),
        "strip corpus was allocated inside the repository",
        "private input copies must be transient and outside the public workspace",
        "use the declared external temporary directory",
    )
    return temporary


def _guard_identities(root: Path) -> dict[str, str]:
    return {name: _sha(_git(root, "show", f"{PRIVACY_BASE}:{name}")) for name in GUARDS}


def freeze_expectation(root: Path, frozen: Path) -> dict[str, object]:
    """Produce only digest expectations from one authentic frozen strip run."""
    source = TrackedStripInput.read(root)
    before = source.identity()
    strip = _load_strip(frozen, "frozen_pre_move_strip_for_generation")
    with _outside_workspace() as temporary:
        target = Path(temporary)
        source.materialize(target)
        report = _strip_locally(strip, target)
        output = _tree_identity(_tree(target))
        report_identity = _sha(_encoded(report))
    after = TrackedStripInput.read(root).identity()
    _require(
        after == before,
        "tracked input changed during golden-data generation",
        "the output would not identify a single immutable input candidate",
        "freeze again after the tracked input is stable",
    )
    return {
        "schema_version": 1,
        "input": before,
        "frozen_strip_sha256": _sha(frozen.read_bytes()),
        "output": output,
        "removed_report_sha256": report_identity,
        "privacy_base": PRIVACY_BASE,
        "guard_sha256": _guard_identities(root),
        "hash_encoding": "key-sorted compact UTF-8 JSON; tree rows are path/kind/content-sha256",
    }


class ScrubMoveObservation:
    """Owns the finite full-corpus stimulus and privacy-safe observations."""

    def __init__(self) -> None:
        self.expected = json.loads((FIXTURE / "expected.json").read_text("utf-8"))

    def frozen_case(self, source: TrackedStripInput) -> tuple[str, dict] | None:
        """The historical receipt whose frozen corpus equals the current one, if any."""
        cases = self.expected["cases"]
        _require(
            self.expected["schema_version"] == 2
            and set(cases) == {"original-R@5f882", "candidate-premove@aaacec7"},
            "the frozen receipt population is not the declared closed pair",
            "the historical move proof is exactly two independently frozen corpora",
            "restore the two recorded cases; receipts are never added or rewritten",
        )
        actual = source.identity()
        matches = [
            (identifier, case)
            for identifier, case in cases.items()
            if case["input"] == actual
        ]
        return matches[0] if matches else None

    def observe_preserved_output(self) -> str:
        source = TrackedStripInput.read(ROOT)
        frozen_case = self.frozen_case(source)
        frozen_path = FIXTURE / "pre_move_strip.py.txt"
        _require(
            _sha(frozen_path.read_bytes()) == self.expected["frozen_strip_sha256"],
            "frozen pre-move public algorithm bytes changed",
            "a rewritten reference cannot establish the preserving move",
            "restore the authentic pre-move strip bytes; never update the golden manually",
        )
        for name, digest in self.expected["guard_sha256"].items():
            _require(
                _sha((ROOT / name).read_bytes()) == digest,
                f"privacy guard {name} differs from the declared merged base",
                "G1–G5 and the catalog guard are immutable safety obligations",
                "stop the move and restore the unchanged guard through its owner",
            )
        frozen = _load_strip(frozen_path, "frozen_pre_move_strip_for_observation")
        current = _load_strip(
            ROOT / "scripts/release/strip_private_agents.py",
            "current_strip_for_preserving_move",
        )
        with _outside_workspace() as temporary:
            parent = Path(temporary)
            before_target, after_target = parent / "before", parent / "after"
            source.materialize(before_target)
            source.materialize(after_target)
            before_input, after_input = _tree(before_target), _tree(after_target)
            _require(
                before_input == after_input,
                "the two strip algorithms did not receive byte-identical complete inputs",
                "different corpora cannot establish preserving-move equivalence",
                "materialize both targets from the same tracked input snapshot",
            )
            before_report = _strip_locally(frozen, before_target)
            after_report = _strip_locally(current, after_target)
            before_tree, after_tree = _tree(before_target), _tree(after_target)
            _require(
                before_tree == after_tree,
                "the complete before/after strip trees differ",
                "the scrub move must preserve every output byte and directory",
                "move the scrub body unchanged and rewire only its owning call",
            )
            _require(
                before_report == after_report,
                "the complete before/after removed reports differ",
                "the scrub move must preserve removal identities, categories and order",
                "preserve the original scrub's reports through the public strip port",
            )
            _require(
                any(before_report.values()) and before_tree != before_input,
                "the frozen strip removed nothing from the current tracked corpus",
                "two algorithms that both strip nothing are not preserving-move evidence",
                "run the strip on the complete tracked catalog, agents and skills",
            )
            if frozen_case is not None:
                case = frozen_case[1]
                for tree in (before_tree, after_tree):
                    _require(
                        _tree_identity(tree) == case["output"],
                        "strip output differs from the authentic frozen public expectation",
                        "two equally broken algorithms are not preserving-move evidence",
                        "restore the unchanged behavior; never hand-author a new digest",
                    )
                for report in (before_report, after_report):
                    _require(
                        _sha(_encoded(report)) == case["removed_report_sha256"],
                        "removed report differs from the authentic frozen report digest",
                        "equivalence alone cannot validate a drifted common filtering dependency",
                        "restore the unchanged removal behavior; never hand-author a new digest",
                    )
        _require(
            not parent.exists(),
            "the transient before/after corpora survived the observation",
            "private tracked inputs must not persist after the vector",
            "remove the owned temporary corpus on every exit path",
        )
        _require(
            TrackedStripInput.read(ROOT).identity() == source.identity(),
            "strip changed the original tracked source population",
            "only the two temporary target copies may be mutated",
            "pass the temporary targets to strip and leave the source tier unchanged",
        )
        return "current-corpus" if frozen_case is None else frozen_case[0]


@pytest.mark.acceptance
def test_scrub_move_preserves_complete_tracked_strip_output(record_property):
    record_property(
        "preservation_vector", ScrubMoveObservation().observe_preserved_output()
    )
