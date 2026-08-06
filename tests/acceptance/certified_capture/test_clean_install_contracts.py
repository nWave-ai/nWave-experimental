# @feature-certified-capture
# @slice-01
# @walking_skeleton @driving_port @real-io @contract-shape:pure-function

"""Release-shaped walking skeleton for the certified-capture public contract."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from tests.e2e.conftest import _build_pypi_shape_wheel, _copy_repo_subset


pytestmark = [pytest.mark.acceptance, pytest.mark.e2e]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _result(
    phase: str,
    status: str,
    *,
    error_kind: str | None = None,
    error_message: str | None = None,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One parent-visible envelope for every producer, install, or harness outcome."""
    return {
        "phase": phase,
        "status": status,
        "error_kind": error_kind,
        "error_message": error_message,
        "observation": observation or {},
    }


def _release_candidate(tmp_path: Path) -> tuple[Path, str] | dict[str, Any]:
    """Build one immutable candidate, preserving producer incapacity as data."""
    try:
        producer_workspace = tmp_path / "release-producer"
        _copy_repo_subset(_REPOSITORY_ROOT, producer_workspace)
        candidate = _build_pypi_shape_wheel(producer_workspace)
        return candidate, hashlib.sha256(candidate.read_bytes()).hexdigest()
    except (
        Exception
    ) as error:  # production-pipeline incapacity is an observable outcome
        return _result(
            "candidate_build",
            "INCAPACITY",
            error_kind=type(error).__name__,
            error_message=str(error),
        )


def _run_clean_harness(candidate: Path, consumer_root: Path) -> dict[str, Any]:
    """Install one wheel and obtain exactly one structured consumer observation."""
    environment = consumer_root / "harness-environment"
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(environment)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        install = subprocess.run(
            [str(environment / "bin" / "pip"), "install", "--no-deps", str(candidate)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (
        Exception
    ) as error:  # venv creation is an environmental incapacity, not package absence
        return _result(
            "candidate_install",
            "INCAPACITY",
            error_kind=type(error).__name__,
            error_message=str(error),
        )
    if install.returncode != 0:
        return _result(
            "candidate_install",
            "INCAPACITY",
            error_kind="InstallFailed",
            error_message=install.stdout,
        )

    harness = r"""
import dataclasses
import importlib
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from uuid import UUID

PUBLIC_NAMES = (
    "TaskCaseContractRef", "StudyRef", "RunRef", "PartitionRef", "RequestRef",
    "RepositoryRef", "UsageObservationMode", "UsageObservationSemantics",
    "RunManifest", "Complete", "Incomplete", "Indeterminate", "CaptureResult",
)

class DenyNeutralImports:
    forbidden = ("des", "src.des", "scripts", "tests")
    def __init__(self):
        self.attempts = []
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == root or fullname.startswith(root + ".") for root in self.forbidden):
            self.attempts.append(fullname)
            raise ImportError("neutral contract attempted forbidden import: " + fullname)
        return None

def emit(phase, status, error_kind=None, error_message=None, observation=None):
    print(json.dumps({
        "phase": phase, "status": status, "error_kind": error_kind,
        "error_message": error_message, "observation": observation or {},
    }, sort_keys=True))

guard = DenyNeutralImports()
sys.meta_path.insert(0, guard)
candidate_contains_des = any((Path(entry) / "des").exists() for entry in sys.path if entry)
try:
    importlib.util.find_spec("des")
except ImportError:
    guard_sensitive = guard.attempts == ["des"]
else:
    guard_sensitive = False
guard.attempts.clear()

try:
    capture = importlib.import_module("nwave_capture")
except ModuleNotFoundError as error:
    status = "ABSENT" if error.name == "nwave_capture" else "MISMATCH"
    emit("public_import", status, type(error).__name__, str(error), {
        "candidate_contains_des": candidate_contains_des,
        "guard_sensitive": guard_sensitive,
        "guard_attempts": guard.attempts,
    })
except ImportError as error:
    emit("public_import", "MISMATCH", type(error).__name__, str(error), {
        "candidate_contains_des": candidate_contains_des,
        "guard_sensitive": guard_sensitive,
        "guard_attempts": guard.attempts,
    })
except Exception as error:
    emit("public_construction", "MISMATCH", type(error).__name__, str(error), {
        "candidate_contains_des": candidate_contains_des,
        "guard_sensitive": guard_sensitive,
        "guard_attempts": guard.attempts,
    })
else:
    try:
        digest = "a" * 64
        task = capture.TaskCaseContractRef("case-1", digest, digest, digest, digest)
        study = capture.StudyRef("study-1", digest, "current-des")
        run = capture.RunRef(UUID("12345678-1234-5678-1234-567812345678"), 1, study)
        root = capture.PartitionRef("root", run.run_id, "host-1", "host")
        request = capture.RequestRef("anthropic", "request-1", root, "claude")
        repository = capture.RepositoryRef(digest, digest, "f" * 40)
        semantics = capture.UsageObservationSemantics(
            "anthropic", "v1", capture.UsageObservationMode.CUMULATIVE_SNAPSHOT, "max-v1"
        )
        now = datetime(2026, 8, 5, tzinfo=UTC)
        manifest = capture.RunManifest(
            "v1", run, digest, ("tokens",), (semantics,), root, now,
            now + timedelta(minutes=1), now + timedelta(minutes=6),
            PurePosixPath("/tmp/certified-capture"), digest, digest, digest, digest,
            "writer-v1", "metadata-only", now + timedelta(days=30), repository,
            ("anthropic:v1",), digest,
        )
        complete = capture.Complete(digest)
        incomplete = capture.Incomplete(("writer-refused",))
        indeterminate = capture.Indeterminate(("unknown-provenance",))
        values = {
            "TaskCaseContractRef": task, "StudyRef": study, "RunRef": run,
            "PartitionRef": root, "RequestRef": request, "RepositoryRef": repository,
            "UsageObservationSemantics": semantics, "RunManifest": manifest,
            "Complete": complete, "Incomplete": incomplete, "Indeterminate": indeterminate,
        }
        emit("public_construction", "OK", observation={
            "candidate_contains_des": candidate_contains_des,
            "guard_sensitive": guard_sensitive,
            "guard_attempts": guard.attempts,
            "public_names": tuple(getattr(capture, "__all__", ())),
            "field_outcomes": {name: tuple(field.name for field in dataclasses.fields(value)) for name, value in values.items()},
            "frozen": {name: dataclasses.is_dataclass(value) and value.__dataclass_params__.frozen for name, value in values.items()},
            "mode": capture.UsageObservationMode.CUMULATIVE_SNAPSHOT.value,
            "manifest_coherent": (
                manifest.root_partition.run_id == manifest.run.run_id
                and manifest.task_case_contract_digest == manifest.run.study.task_case_contract_digest
                and manifest.root_partition.parent_partition_id is None
                and manifest.interval_start < manifest.interval_end <= manifest.reconciliation_deadline <= manifest.retention_deadline
            ),
            "request_coherent": request.partition.run_id == run.run_id,
            "result_arms": (type(complete).__name__, type(incomplete).__name__, type(indeterminate).__name__),
            "module_path": str(Path(capture.__file__).resolve()),
        })
    except Exception as error:
        emit("public_construction", "MISMATCH", type(error).__name__, str(error), {
            "candidate_contains_des": candidate_contains_des,
            "guard_sensitive": guard_sensitive,
            "guard_attempts": guard.attempts,
        })
"""
    environment_variables = {
        "HOME": str(consumer_root / "home"),
        "PATH": f"{environment / 'bin'}:{os.environ.get('PATH', '')}",
    }
    completed = subprocess.run(
        [str(environment / "bin" / "python"), "-I", "-c", harness],
        cwd=consumer_root,
        env=environment_variables,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return _result(
            "harness_launch",
            "INCAPACITY",
            error_kind="MalformedHarnessEnvelope",
            error_message=completed.stdout,
        )


@pytest.mark.walking_skeleton
@pytest.mark.negative_at
def test_clean_installed_wheel_never_borrows_checkout_for_public_capture_contracts(
    tmp_path: Path,
) -> None:
    """A study harness constructs the complete neutral contract from one wheel.

    CONTRACT_SHAPE: pure-function
    Outcome anchor: DISCUSS Elevator Pitch — A clean installed nwave_capture wheel exposes public contracts, manifest, and result values that an external harness can construct without importing DES.
    # covers: R1
    # covers: R2
    # covers: R3
    # covers: R4
    # covers: R5
    # covers: R6
    # covers: R7
    # covers: R8
    # covers: R9
    """
    unavailable_candidate = tmp_path / "unavailable-candidate.whl"
    incapacity_observation = _run_clean_harness(
        unavailable_candidate, tmp_path / "incapacity-consumer"
    )

    assert incapacity_observation["status"] == "INCAPACITY", (
        "WHAT: an unavailable candidate was not classified as install incapacity. "
        "WHY: producer/install inability must remain distinct from an absent public "
        "package inside a successfully installed wheel. HOW: preserve pip failure as "
        f"the candidate_install envelope; observation={incapacity_observation}"
    )
    assert incapacity_observation["phase"] == "candidate_install", (
        "WHAT: the controlled pip failure was attributed to the wrong phase. WHY: "
        "the parent must identify the exact failed boundary. HOW: emit "
        f"phase=candidate_install; observation={incapacity_observation}"
    )
    assert incapacity_observation["error_kind"] == "InstallFailed", (
        "WHAT: the install incapacity lacks its stable error kind. WHY: package "
        "absence and installer failure require distinct remediation. HOW: retain "
        f"InstallFailed from the real pip result; observation={incapacity_observation}"
    )
    assert incapacity_observation["error_message"], (
        "WHAT: install incapacity emitted an empty reason. WHY: operators need the "
        "real pip failure to recover. HOW: include captured pip output in error_message."
    )

    candidate_or_incapacity = _release_candidate(tmp_path)
    if isinstance(candidate_or_incapacity, dict):
        observation = candidate_or_incapacity
    else:
        candidate, digest = candidate_or_incapacity
        observation = _run_clean_harness(candidate, tmp_path / "clean-consumer")
        observation["candidate_sha256"] = digest

    assert observation["status"] != "INCAPACITY", (
        "WHAT: the release candidate could not be built, installed, or launched. "
        "WHY: incapacity is distinct from a public package defect and must retain "
        "its exact phase. HOW: restore the named producer/install capability. "
        f"observation={observation}"
    )
    assert observation["status"] == "OK", (
        "WHAT: the installed candidate does not provide the ratified public capture "
        "contract. WHY: an external study harness must distinguish package absence "
        "or mismatch from environmental incapacity. HOW: ship src/nwave_capture, "
        "its root exports, and the declared frozen constructors. "
        f"phase={observation['phase']} kind={observation['error_kind']} "
        f"message={observation['error_message']} observation={observation['observation']}"
    )

    details = observation["observation"]
    expected_names = (
        "TaskCaseContractRef",
        "StudyRef",
        "RunRef",
        "PartitionRef",
        "RequestRef",
        "RepositoryRef",
        "UsageObservationMode",
        "UsageObservationSemantics",
        "RunManifest",
        "Complete",
        "Incomplete",
        "Indeterminate",
        "CaptureResult",
    )
    assert details["candidate_contains_des"] and details["guard_sensitive"], (
        "WHAT: the neutral-import guard was not demonstrably sensitive while the "
        "candidate contains des. WHY: a no-op guard cannot prove neutrality. HOW: "
        "install the deny meta-path finder before import and make it reject des."
    )
    assert details["guard_attempts"] == [], (
        "WHAT: constructing the neutral public package attempted a prohibited import. "
        "WHY: capture contracts must not resolve des, scripts, tests, or src.des. "
        "HOW: remove that dependency from nwave_capture."
    )
    public_names = tuple(details["public_names"])
    original_name_counts = {name: public_names.count(name) for name in expected_names}
    assert all(count == 1 for count in original_name_counts.values()), (
        "WHAT: the installed package removed or repeated an original slice-01 "
        f"public name; observed counts={original_name_counts}, root={public_names}. "
        "WHY: later certified-capture slices may extend the public root but must "
        "preserve every original contract name exactly once for existing consumers. "
        "HOW: DELIVER must restore each of the 13 original names once; keep exact "
        "current-root membership enforcement in the latest-slice clean-wheel AT."
    )
    assert all(details["frozen"].values())
    actual_field_outcomes = {
        name: tuple(fields) for name, fields in details["field_outcomes"].items()
    }
    assert actual_field_outcomes == {
        "TaskCaseContractRef": (
            "task_case_id",
            "task_spec_digest",
            "initial_state_digest",
            "environment_contract_digest",
            "quality_evaluation_plan_digest",
        ),
        "StudyRef": ("study_id", "task_case_contract_digest", "comparator_id"),
        "RunRef": ("run_id", "attempt_no", "study"),
        "PartitionRef": (
            "partition_id",
            "run_id",
            "actor_id",
            "actor_kind",
            "parent_partition_id",
        ),
        "RequestRef": ("provider_namespace", "request_id", "partition", "model"),
        "RepositoryRef": (
            "repo_id",
            "worktree_id",
            "base_commit_sha",
            "observed_head_sha",
        ),
        "UsageObservationSemantics": (
            "provider_namespace",
            "schema_version",
            "mode",
            "reducer_id_and_version",
        ),
        "RunManifest": (
            "capture_schema_version",
            "run",
            "task_case_contract_digest",
            "metric_vocabulary",
            "usage_observation_semantics",
            "root_partition",
            "interval_start",
            "interval_end",
            "reconciliation_deadline",
            "canonical_capture_root",
            "runtime_digest",
            "hook_digest",
            "executable_digest",
            "config_digest",
            "primary_writer_version",
            "retention_target",
            "retention_deadline",
            "repository",
            "provider_namespace_versions",
            "manifest_digest",
        ),
        "Complete": ("certificate_digest",),
        "Incomplete": ("known_failures",),
        "Indeterminate": ("unknowns",),
    }
    assert details["mode"] == "cumulative_snapshot"
    assert details["manifest_coherent"] and details["request_coherent"]
    assert tuple(details["result_arms"]) == ("Complete", "Incomplete", "Indeterminate")
    assert str(_REPOSITORY_ROOT) not in details["module_path"]
