# @feature-certified-capture
# @slice-02
# @real-io @driving_port @contract-shape:bounded-change
"""Clean-wheel contract for a retained local evidence bundle."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from tests.e2e.conftest import _copy_repo_subset


pytestmark = [pytest.mark.acceptance, pytest.mark.e2e]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_HATCHLING_VERSION = "1.31.0"
_TROVE_CLASSIFIERS_VERSION = "2026.6.1.19"


def _assert_exact_contract(
    actual: object,
    expected: object,
    *,
    invariant: str,
    repair: str,
) -> None:
    assert actual == expected, (
        f"WHAT: {invariant}; expected {expected!r}, observed {actual!r}. "
        "WHY: the clean installed wheel is the public certified-capture contract, "
        "so a divergent observable can mislead release consumers. "
        f"HOW: DELIVER must {repair}."
    )


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=600,
    )
    assert completed.returncode == 0, (
        "WHAT: the release producer could not create the immutable candidate. WHY: "
        "a clean-consumer result is meaningless when candidate assembly stops early. "
        f"HOW: restore the pinned offline builder or production staging step; "
        f"command {command!r} said: {completed.stdout}"
    )
    return completed.stdout


def _resolve_pinned_build_root(
    cache_root: Path,
    *,
    distribution: str,
    version: str,
) -> Path:
    candidates = [
        candidate
        for candidate in cache_root.glob(
            f"wheels-v*/pypi/{distribution}/{version}-py3-none-any"
        )
        if candidate.is_dir()
    ]
    assert len(candidates) == 1, (
        f"WHAT: pinned {distribution}=={version} has {len(candidates)} readable "
        f"unpacked cache roots. WHY: zero roots cannot build offline and multiple "
        "roots make the selected backend ambiguous. HOW: seed exactly one matching "
        f"uv wheel-cache entry beneath {cache_root}; found {candidates!r}"
    )
    return candidates[0].resolve(strict=True)


def _offline_build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("UV_CACHE_DIR", None)
    environment.update(
        {
            "HATCH_BUILD_NO_HOOKS": "true",
            "PIP_NO_INDEX": "1",
        }
    )
    cache = subprocess.run(
        ["uv", "cache", "dir"],
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert cache.returncode == 0 and cache.stdout.strip(), (
        "WHAT: uv did not identify its readable default cache. WHY: the pinned "
        "backend roots cannot be resolved without a cache root. HOW: restore the "
        f"uv installation and its cache directory; uv said: {cache.stdout}"
    )
    cache_root = Path(cache.stdout.strip()).resolve()
    build_roots = (
        _resolve_pinned_build_root(
            cache_root,
            distribution="hatchling",
            version=_HATCHLING_VERSION,
        ),
        _resolve_pinned_build_root(
            cache_root,
            distribution="trove-classifiers",
            version=_TROVE_CLASSIFIERS_VERSION,
        ),
    )
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            *(str(root) for root in build_roots),
            *([prior_pythonpath] if prior_pythonpath else []),
        ]
    )
    versions = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.metadata as m; "
            f"assert m.version('hatchling') == '{_HATCHLING_VERSION}'; "
            "assert m.version('trove-classifiers') == "
            f"'{_TROVE_CLASSIFIERS_VERSION}'",
        ],
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert versions.returncode == 0, (
        "WHAT: the resolved read-only build roots do not expose the pinned backend "
        "versions. WHY: the candidate identity is unreliable when another backend can "
        "win import resolution. HOW: seed the exact pinned unpacked cache entries; "
        f"the version probe said: {versions.stdout}"
    )
    return environment


def _build_release_candidate(tmp_path: Path) -> tuple[Path, str]:
    producer = tmp_path / "release-producer"
    _copy_repo_subset(_REPOSITORY_ROOT, producer)
    build_environment = _offline_build_environment()
    candidate_version = "0.0.0.dev0"
    pyproject = producer / "pyproject.toml"
    _run(
        [
            sys.executable,
            "scripts/release/patch_pyproject.py",
            "--input",
            str(pyproject),
            "--output",
            str(pyproject),
            "--target-name",
            "nwave-ai",
            "--target-version",
            candidate_version,
        ],
        cwd=producer,
    )
    module_init = producer / "nwave_ai" / "__init__.py"
    stamped, replacements = re.subn(
        r'(?m)^__version__ = ".*"$',
        f'__version__ = "{candidate_version}"',
        module_init.read_text(encoding="utf-8"),
    )
    assert replacements == 1, f"module version assignments: {replacements}"
    module_init.write_text(stamped, encoding="utf-8")
    _run([sys.executable, "scripts/build_dist.py"], cwd=producer)
    _run(
        [sys.executable, "scripts/release/stage_public_wheel_des.py", "--cleanup-dist"],
        cwd=producer,
    )
    wheelhouse = producer / "wheelhouse"
    _run(
        [
            sys.executable,
            "-m",
            "hatchling",
            "build",
            "--target",
            "wheel",
            "--directory",
            str(wheelhouse),
            "--no-hooks",
        ],
        cwd=producer,
        env=build_environment,
    )
    wheels = list(wheelhouse.glob("nwave_ai-*.whl"))
    assert len(wheels) == 1, f"expected one immutable candidate, found {wheels!r}"
    candidate = wheels[0]
    return candidate, hashlib.sha256(candidate.read_bytes()).hexdigest()


def _run_clean_harness(candidate: Path, consumer_root: Path) -> dict[str, Any]:
    environment = consumer_root / "clean-environment"
    subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    install = subprocess.run(
        [
            str(environment / "bin" / "pip"),
            "install",
            "--no-deps",
            "--force-reinstall",
            str(candidate),
        ],
        check=False,
        env={**os.environ, "PIP_NO_INDEX": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert install.returncode == 0, (
        "WHAT: the clean consumer could not install the immutable wheel. WHY: a "
        "bundle claim must be made from the release artifact, not the checkout. HOW: "
        f"make the wheel pip-installable; pip said: {install.stdout}"
    )

    harness = r"""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from uuid import UUID

def emit(status, **observation):
    print(json.dumps({"status": status, "observation": observation}, sort_keys=True))

try:
    import nwave_capture as capture
    required = (
        "AtomicHealthReceiptStore", "CaptureVerifier", "EvidenceRecord",
        "ExpectedPartition", "ExpectedPopulation", "FramedPartitionStore",
        "LocalEvidenceVerified", "PartitionRef", "RunManifest", "RunRef",
        "StudyRef", "TaskCaseContractRef", "TerminalReason",
        "UsageObservationMode", "UsageObservationSemantics", "RepositoryRef",
    )
    missing = tuple(name for name in required if not hasattr(capture, name))
    expected_exports = {
        "AtomicHealthReceiptStore", "CaptureResult", "CaptureStorageError",
        "CaptureVerifier", "Complete", "EvidenceRecord", "ExpectedPartition",
        "ExpectedPopulation", "FramedPartitionStore", "HealthReceiptUnavailableError",
        "Incomplete", "Indeterminate", "LocalEvidenceIncomplete",
        "LocalEvidenceIndeterminate", "LocalEvidenceResult", "LocalEvidenceVerified",
        "PartitionRef", "PartitionStateError", "PartitionTerminal",
        "PartitionWriterConflictError", "ReceiptConflictError", "RepositoryRef",
        "RequestRef", "RunManifest", "RunRef", "StudyRef", "TaskCaseContractRef",
        "TerminalReason", "UsageObservationMode", "UsageObservationSemantics",
    }
    actual_export_sequence = tuple(capture.__all__)
    actual_exports = set(actual_export_sequence)
    duplicate_exports = tuple(sorted(
        name for name in actual_exports if actual_export_sequence.count(name) > 1
    ))
    if (
        missing
        or len(actual_export_sequence) != 30
        or duplicate_exports
        or actual_exports != expected_exports
    ):
        emit(
            "MISSING_FUNCTIONALITY",
            what="the installed package root is not the duplicate-free exact-30 contract",
            why="release consumers must receive one closed public vocabulary",
            how="DELIVER must export every and only the 30 ratified names once",
            missing=missing,
            export_count=len(actual_export_sequence),
            duplicate_exports=duplicate_exports,
            unexpected_exports=tuple(sorted(actual_exports - expected_exports)),
            absent_exports=tuple(sorted(expected_exports - actual_exports)),
        )
        raise SystemExit

    digest = "a" * 64
    run_id = UUID("12345678-1234-5678-1234-567812345678")
    now = datetime(2026, 8, 5, tzinfo=UTC)

    def manifest_for(bundle_root):
        study = capture.StudyRef("study-1", digest, "current-des")
        run = capture.RunRef(run_id, 1, study)
        root = capture.PartitionRef("root", run_id, "harness-1", "harness")
        manifest = capture.RunManifest(
            "v1", run, digest, ("tokens",),
            (capture.UsageObservationSemantics(
                "provider", "v1", capture.UsageObservationMode.CUMULATIVE_SNAPSHOT,
                "max-v1",
            ),),
            root, now, now + timedelta(minutes=1), now + timedelta(minutes=6),
            PurePosixPath(bundle_root), digest, digest, digest, digest, "writer-v1",
            "metadata-only", now + timedelta(days=30),
            capture.RepositoryRef(digest, digest, "f" * 40), ("provider:v1",), digest,
        )
        expected = capture.ExpectedPartition(root, "writer-1", now)
        return manifest, expected, capture.ExpectedPopulation(run_id, digest, (expected,))

    bundle_root = Path("bundle").resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    manifest, expected, population = manifest_for(bundle_root)
    health = capture.AtomicHealthReceiptStore(bundle_root, manifest)
    primary = capture.FramedPartitionStore(bundle_root, manifest, expected)
    verifier = capture.CaptureVerifier(bundle_root, manifest)
    public_methods = {
        "observer": tuple(sorted(
            name for name in dir(health)
            if not name.startswith("_") and callable(getattr(health, name))
        )),
        "writer": tuple(sorted(
            name for name in dir(primary)
            if not name.startswith("_") and callable(getattr(primary, name))
        )),
        "verifier": tuple(sorted(
            name for name in dir(verifier)
            if not name.startswith("_") and callable(getattr(verifier, name))
        )),
    }
    expected_methods = {
        "observer": ("probe", "read"),
        "writer": ("abort", "append", "close", "open", "probe"),
        "verifier": ("probe", "verify"),
    }
    forbidden_aliases = (
        "declare", "start", "latch_failure", "publish_terminal"
    )
    exposed_aliases = {
        boundary: tuple(name for name in forbidden_aliases if hasattr(instance, name))
        for boundary, instance in (
            ("observer", health), ("writer", primary), ("verifier", verifier)
        )
    }
    if public_methods != expected_methods or any(exposed_aliases.values()):
        emit(
            "SURFACE_MISMATCH",
            what="an installed effect boundary exposes an unratified public action",
            why="extra aliases can bypass the writer-owned terminal lifecycle",
            how="DELIVER must expose only the ratified role methods and remove aliases",
            public_methods=public_methods,
            exposed_aliases=exposed_aliases,
        )
        raise SystemExit
    health.probe()
    primary.probe()
    verifier.probe()
    primary.open()
    primary.append(capture.EvidenceRecord(1, "usage", '{"tokens":1}'))
    receipt_kinds_before_close = tuple(
        json.loads(value)["kind"] for value in health.read(expected)
    )
    primary.close(capture.TerminalReason.CAPTURED)
    receipt_kinds_after_close = tuple(
        json.loads(value)["kind"] for value in health.read(expected)
    )
    result = verifier.verify(population)
    receipt_bytes = health.read(expected)
    receipts = {json.loads(value)["kind"]: value for value in receipt_bytes}
    terminal = json.loads(receipts["terminal"])
    primary_file = next(
        path for path in (bundle_root / "primary").rglob("*.jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest()
        == terminal["payload"]["primary_digest"]
    )
    descriptor = {
        "manifest_digest": manifest.manifest_digest,
        "partitions": [{
            "expected_receipt_digest": hashlib.sha256(receipts["expected"]).hexdigest(),
            "partition_id": expected.partition.partition_id,
            "primary_digest": hashlib.sha256(primary_file.read_bytes()).hexdigest(),
            "started_receipt_digest": hashlib.sha256(receipts["started"]).hexdigest(),
            "terminal_receipt_digest": hashlib.sha256(receipts["terminal"]).hexdigest(),
            "writer_id": expected.writer_id,
        }],
        "run_id": str(manifest.run.run_id),
        "schema": "nwave_capture.bundle.v1",
    }
    descriptor_bytes = json.dumps(
        descriptor, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    derived_bundle_digest = hashlib.sha256(
        b"nwave-capture:bundle:v1\x00" + descriptor_bytes
    ).hexdigest()

    fault_root = Path("fault-bundle").resolve()
    fault_root.mkdir(parents=True, exist_ok=True)
    fault_manifest, fault_expected, fault_population = manifest_for(fault_root)
    fault_health = capture.AtomicHealthReceiptStore(fault_root, fault_manifest)
    fault_primary = capture.FramedPartitionStore(
        fault_root, fault_manifest, fault_expected
    )
    fault_verifier = capture.CaptureVerifier(fault_root, fault_manifest)
    fault_health.probe()
    fault_primary.probe()
    fault_verifier.probe()
    (fault_root / "primary").write_text("blocked", encoding="utf-8")
    fault_error = None
    try:
        fault_primary.open()
    except capture.CaptureStorageError as error:
        fault_error = error
    fault_result = fault_verifier.verify(fault_population)
    bundle_paths = tuple(sorted(
        str(path.relative_to(bundle_root)) for path in bundle_root.rglob("*") if path.is_file()
    ))
    emit(
        "VERIFIED" if isinstance(result, capture.LocalEvidenceVerified) else "NOT_VERIFIED",
        bundle_digest=getattr(result, "bundle_digest", None),
        derived_bundle_digest=derived_bundle_digest,
        bundle_paths=bundle_paths,
        export_count=len(actual_export_sequence),
        duplicate_exports=duplicate_exports,
        fault_error_fields={
            name: getattr(fault_error, name, None)
            for name in ("operation", "partition_id", "reason", "remediation")
        },
        fault_result_type=type(fault_result).__name__,
        module_path=capture.__file__,
        public_methods=public_methods,
        exposed_aliases=exposed_aliases,
        receipt_kinds_before_close=receipt_kinds_before_close,
        receipt_kinds_after_close=receipt_kinds_after_close,
        result_type=type(result).__name__,
    )
except Exception as error:
    emit("BUNDLE_ERROR", error_kind=type(error).__name__, error_message=str(error))
"""
    completed = subprocess.run(
        [str(environment / "bin" / "python"), "-I", "-c", harness],
        cwd=consumer_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert completed.returncode == 0, (
        "WHAT: the clean consumer harness did not finish. WHY: the release wheel "
        "must create a bundle without checkout imports. HOW: make the installed public "
        f"surface complete; harness output: {completed.stdout}"
    )
    return json.loads(completed.stdout)


@pytest.mark.negative_at
def test_clean_installed_package_retains_one_verifiable_local_evidence_bundle(
    tmp_path: Path,
) -> None:
    """# covers: R10
    # covers: R11
    # covers: R12
    # covers: R13

    A release operator can verify one retained local bundle.
    """
    candidate, candidate_digest = _build_release_candidate(tmp_path)
    observation = _run_clean_harness(candidate, tmp_path / "consumer")
    bundle_paths = set(observation["observation"].get("bundle_paths", ()))

    assert observation["status"] == "VERIFIED", (
        "WHAT: the clean installed wheel did not verify its local evidence bundle. WHY: "
        "a release operator needs retained evidence rather than a checkout-only claim. "
        "HOW: expose the ratified stores and verifier, then retain coherent receipts and "
        f"frames; observed {observation}."
    )
    assert observation["observation"].get("result_type") == "LocalEvidenceVerified", (
        "WHAT: local verification returned the wrong result arm. WHY: slice-02 proves "
        "bundle retention, not a slice-05 certificate. HOW: return LocalEvidenceVerified "
        f"only after the retained local bundle validates; observed {observation}."
    )
    _assert_exact_contract(
        observation["observation"].get("export_count"),
        30,
        invariant="the installed root export cardinality is not exactly 30",
        repair="make nwave_capture.__all__ contain exactly 30 entries",
    )
    _assert_exact_contract(
        observation["observation"].get("duplicate_exports"),
        [],
        invariant="the installed root repeats one or more public exports",
        repair="deduplicate nwave_capture.__all__ without changing its ratified membership",
    )
    _assert_exact_contract(
        observation["observation"].get("public_methods"),
        {
            "observer": ["probe", "read"],
            "writer": ["abort", "append", "close", "open", "probe"],
            "verifier": ["probe", "verify"],
        },
        invariant="the installed observer, writer, or verifier method set diverges",
        repair="expose only the exact role methods ratified by CC-S02-1",
    )
    _assert_exact_contract(
        observation["observation"].get("exposed_aliases"),
        {"observer": [], "writer": [], "verifier": []},
        invariant="an installed boundary exposes a forbidden lifecycle alias",
        repair="remove declare/start/latch_failure/publish_terminal from public boundaries",
    )
    _assert_exact_contract(
        observation["observation"].get("receipt_kinds_before_close"),
        ["expected", "started"],
        invariant="terminal health evidence exists before the writer closes",
        repair="keep terminal publication private and invoke it only from writer.close",
    )
    _assert_exact_contract(
        observation["observation"].get("receipt_kinds_after_close"),
        ["expected", "started", "terminal"],
        invariant="writer.close does not publish exactly one terminal observation",
        repair="make writer.close retain the sole terminal receipt after expected/started",
    )
    assert observation["observation"].get("bundle_digest", "") != "", (
        "WHAT: the verified bundle has no immutable identity. WHY: an operator must be "
        "able to identify the exact retained evidence. HOW: return its bundle digest from "
        f"LocalEvidenceVerified; candidate SHA-256 is {candidate_digest}."
    )
    assert observation["observation"].get("bundle_digest") == observation[
        "observation"
    ].get("derived_bundle_digest"), (
        "WHAT: the installed verifier's bundle identity differs from independently "
        "derived retained bytes. WHY: a label cannot substitute for the canonical "
        "CC-S02-3 property. HOW: hash the exact descriptor and domain prefix; observed "
        f"{observation}."
    )
    assert observation["observation"].get("fault_result_type") in {
        "LocalEvidenceIncomplete",
        "LocalEvidenceIndeterminate",
    }, (
        "WHAT: the clean installed writer fault looked verified. WHY: the charter "
        "requires an unsuccessful attempt to remain visibly non-complete. HOW: retain "
        f"the fault and return an incomplete or indeterminate result; observed {observation}."
    )
    assert all(observation["observation"].get("fault_error_fields", {}).values()), (
        "WHAT: the clean installed writer fault is not actionable. WHY: the release "
        "operator needs what failed, why, and how to recover. HOW: populate all public "
        f"error fields; observed {observation}."
    )
    assert {"health", "primary"} <= {path.split("/", 1)[0] for path in bundle_paths}, (
        "WHAT: the bundle omitted its independent health or primary evidence. WHY: a "
        "single writer cannot certify its own successful work. HOW: retain both paths "
        f"under the manifest-pinned root; observed files {sorted(bundle_paths)}."
    )
    assert "site-packages" in observation["observation"].get("module_path", ""), (
        "WHAT: the consumer did not load nwave_capture from the clean installation. WHY: "
        "a source checkout can mask a broken wheel. HOW: run the harness with the venv's "
        f"isolated Python; module path was {observation['observation'].get('module_path')!r}."
    )
