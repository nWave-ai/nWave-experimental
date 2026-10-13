"""Bounded exact-c429 identity controls; no worktree or expectation mutations.

The host runs this declared verification after acceptance authoring. Each child
loads real exported source in isolation; only the two named source loci change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASELINE = "c42970373b92767f7bd57797de8588cc43727e6e"
FAMILY = "tests/des/acceptance/design_no_product_change"
HISTORICAL = "tests/des/unit/application/test_native_delivery_lifecycle.py"
NODE = (
    HISTORICAL
    + "::test_cited_design_sections_preserves_prerequisite_hash_without_architect_handoff"
)
OVERLAY = (
    FAMILY + "/public_observation.py",
    HISTORICAL,
    FAMILY + "/fixtures/historical_prerequisite.json",
    FAMILY + "/fixtures/historical_prerequisite.sha256",
    FAMILY + "/identity_mutant_probe.py",
)
SOURCE_LOCI = (
    "src/des/domain/design_document.py",
    "src/des/application/delivery_continuation.py",
)
POPULATION = (
    "correct-public-control",
    "correct-historical-control",
    "public-identity-mutant",
    "historical-prerequisite-mutant",
)

# A fresh isolated interpreter, not a fork of imported lane modules. The
# bootstrap observes origins and pytest phases; it changes no test expectations.
CHILD = r"""
import importlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
kind = sys.argv[2]
prefixes = tuple(Path(p).resolve() for p in (sys.prefix, sys.base_prefix))
sys.path[:] = [
    str(root / "src"), str(root),
    *(p for p in sys.path if p and any(Path(p).resolve().is_relative_to(base) for base in prefixes)),
]
sys.meta_path[:] = [
    finder for finder in sys.meta_path
    if not getattr(finder, "__module__", type(finder).__module__).startswith("__editable__")
]
for name in tuple(sys.modules):
    if name == "des" or name.startswith("des.") or name == "tests" or name.startswith("tests."):
        del sys.modules[name]
sys.path_importer_cache.clear()
importlib.invalidate_caches()

def origins():
    files = {
        name: str(Path(module.__file__).resolve())
        for name, module in tuple(sys.modules.items())
        if (name == "des" or name.startswith("des.") or name == "tests" or name.startswith("tests."))
        and getattr(module, "__file__", None)
    }
    foreign = {name: path for name, path in files.items() if not Path(path).is_relative_to(root)}
    return files, foreign

def emit(data):
    print(json.dumps(data), flush=True)

try:
    importlib.import_module("des.domain.design_document")
    importlib.import_module("des.application.delivery_continuation")
    files, foreign = origins()
    if foreign:
        raise RuntimeError("foreign source imports: " + repr(foreign))
    if kind == "public":
        journey = importlib.import_module("tests.des.acceptance.design_no_product_change.public_observation")
        population = [case.name for case in journey.CASES]
        emit({"label": "declared-public-population", "cases": population})
        code = journey.main()
        reports = None
    else:
        import pytest

        class Phases:
            def __init__(self):
                self.reports = []
                self.collection_errors = []
                self.selected_items = []
            def pytest_collection_finish(self, session):
                # Bind reports to the actual selected function, not a reporting
                # plugin's incidental rendering of its nodeid.
                self.selected_items = [
                    {
                        "nodeid": item.nodeid,
                        "path": Path(item.path).resolve().relative_to(root).as_posix(),
                        "originalname": item.originalname,
                    }
                    for item in session.items
                ]
            def pytest_collectreport(self, report):
                if report.failed:
                    self.collection_errors.append(str(report.longrepr))
            def pytest_runtest_logreport(self, report):
                crash = getattr(report.longrepr, "reprcrash", None)
                self.reports.append({
                    "nodeid": report.nodeid, "when": report.when,
                    "outcome": report.outcome,
                    "diagnostic": str(report.longrepr) if report.failed else "",
                    "crash": getattr(crash, "message", ""),
                })

        phases = Phases()
        argv = [
            "-q", "-s", "-o", "addopts=", "-p", "no:cacheprovider",
            "--basetemp", str(root.parent / (root.name + "-pytest")),
            "tests/des/unit/application/test_native_delivery_lifecycle.py::test_cited_design_sections_preserves_prerequisite_hash_without_architect_handoff",
        ]
        emit({"label": "historical-pytest-argv", "argv": argv})
        code = int(pytest.main(argv, plugins=[phases]))
        reports = {
            "phases": phases.reports, "collection_errors": phases.collection_errors,
            "selected_items": phases.selected_items,
        }
    files, foreign = origins()
    emit({
        "label": "identity-probe-child", "kind": kind,
        "source_root": str(root), "module_origins": files,
        "foreign_imports": foreign, "pytest_reports": reports, "exit": code,
    })
    raise SystemExit(2 if foreign else code)
except Exception as error:
    emit({"label": "identity-probe-child-setup-failure", "diagnostic": repr(error)})
    raise
"""


def emit(data):
    print(json.dumps(data), flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(root):
    source = {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted((root / "src/des").rglob("*.py"))
    }
    return {
        "source_loci": {name: digest(root / name) for name in SOURCE_LOCI},
        "des_source_tree_sha256": hashlib.sha256(
            json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "oracle_support_sha256": {
            name: digest(root / name)
            for name in (*OVERLAY, FAMILY + "/test_design_no_product_change.py")
        },
    }


def environment(scope, source):
    home = scope / "home"
    home.mkdir()
    return {
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        # Only this exported source is visible to native nested Python checks.
        # The isolated bootstrap ignores PYTHONPATH and installs the same paths
        # explicitly; the historical runner retains its declared pytest plugins.
        "PYTHONPATH": os.pathsep.join((str(source / "src"), str(source))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(scope),
    }


def records(stdout):
    found = []
    for line in stdout.splitlines():
        start = line.find("{")
        if start < 0:
            continue
        try:
            record = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            found.append(record)
    return found


def child(root, kind, name):
    argv = [sys.executable, "-I", "-B", "-c", CHILD, str(root), kind]
    receipt = {
        "label": "identity-probe-execution",
        "name": name,
        "argv": argv,
        "cwd": str(root),
        "identities": identities(root),
    }
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            env=environment(root.parent, root),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        receipt.update(
            {
                "exit": None,
                "stdout": getattr(error, "stdout", None),
                "stderr": getattr(error, "stderr", None),
                "diagnostic": repr(error),
            }
        )
        # TimeoutExpired may retain bytes even when text=True.
        for key in ("stdout", "stderr"):
            if isinstance(receipt[key], bytes):
                receipt[key] = receipt[key].decode("utf-8", errors="replace")
        emit(receipt)
        return None
    data = records(result.stdout)
    receipt.update(
        {
            "exit": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "observed_identity_checkpoints": [
                row
                for row in data
                if row.get("label")
                in ("default-canonical-identities", "historical-prerequisite-identity")
            ],
        }
    )
    emit(receipt)
    return result, data


def assess(execution, kind, mutant):
    if execution is None:
        return "setup_failed", "Child execution unavailable; no identity RED observed."
    result, data = execution
    metadata = [row for row in data if row.get("label") == "identity-probe-child"]
    if len(metadata) != 1 or metadata[0]["foreign_imports"]:
        return (
            "setup_failed",
            "Missing isolated child completion or foreign production imports.",
        )
    if kind == "public":
        populations = [
            row["cases"]
            for row in data
            if row.get("label") == "declared-public-population"
        ]
        markers = [
            json.loads(line.split("DES-ORACLE-OBSERVATION: ", 1)[1])
            for line in result.stdout.splitlines()
            if line.startswith("DES-ORACLE-OBSERVATION: ")
        ]
        states = [row for row in data if row.get("label") == "constructor-state"]
        captures = [
            row for row in data if row.get("label") == "default-canonical-identities"
        ]
        failures = [
            row for row in data if row.get("label") == "failed-public-observation"
        ]
        if (
            len(populations) != 1
            or len(populations[0]) != 17
            or len(set(populations[0])) != 17
            or len(markers) != 1
            or markers[0]["setup_failed"] != 0
            or markers[0]["observed"] != 17
            or len(states) != 17
            or {row["case"] for row in states} != set(populations[0])
        ):
            return (
                "setup_failed",
                "Public population/observation incomplete or native setup failure.",
            )
        replacements = {
            row["input"].get("product_change", "required")
            for row in data
            if row.get("label") == "default-canonical-identity"
        }
        required_cases = {
            row["label"]
            for row in data
            if row.get("label") in set(populations[0])
            and row["exit"] == 0
            and row["input"].get("product_change", "required") == "required"
        }
        if (
            replacements != {"required"}
            or not required_cases
            or len(captures) != len(required_cases)
            or {row["case"] for row in captures} != required_cases
        ):
            return (
                "setup_failed",
                "Required-default replacement population was not fully reached.",
            )
        if not mutant:
            valid = (
                result.returncode == 0
                and markers[0]["assertions_failed"] == 0
                and not failures
                and all(
                    row["persisted_before"]
                    == row["emitted_before"]
                    == row["persisted_after"]
                    == row["emitted_after"]
                    for row in captures
                )
            )
        else:
            killed = {row["case"] for row in failures}
            valid = (
                result.returncode == 1
                and markers[0]["assertions_failed"] == len(captures)
                and len(failures) == len(captures)
                and killed == {row["case"] for row in captures}
                and all(
                    "AssertionError: WHAT: default-persisted-identity-conservation:"
                    in row["diagnostic"]
                    for row in failures
                )
                and all(
                    row["persisted_before"] == row["emitted_before"]
                    and row["persisted_after"] == row["emitted_after"]
                    and row["persisted_before"] != row["persisted_after"]
                    and row["authority_before"] == row["authority_after"]
                    for row in captures
                )
            )
        return (
            "satisfied" if valid else "assertion_failed",
            f"Public identity proof {'satisfied' if valid else 'failed'}; expected "
            + (
                "named identity-assertion RED with equal authority fields."
                if mutant
                else "all declared cases GREEN."
            ),
        )
    reports = metadata[0]["pytest_reports"]
    phases = reports["phases"]
    calls = [row for row in phases if row["when"] == "call"]
    captures = [
        row for row in data if row.get("label") == "historical-prerequisite-identity"
    ]
    selected = reports["selected_items"]
    declared_path, _, declared_function = NODE.partition("::")
    if (
        reports["collection_errors"]
        or len(selected) != 1
        or selected[0]["path"] != declared_path
        or selected[0]["originalname"] != declared_function
        or len(calls) != 1
        or sorted(row["when"] for row in phases) != ["call", "setup", "teardown"]
        or any(row["nodeid"] != selected[0]["nodeid"] for row in phases)
        or any(row["outcome"] != "passed" for row in phases if row["when"] != "call")
        or calls[0]["outcome"] == "skipped"
        or len(captures) != 1
    ):
        return (
            "setup_failed",
            "Historical collection/setup/checkpoint incomplete; not semantic RED.",
        )
    identity = captures[0]
    fixed = "d33e4a181fc127227c5024d866cafd3634319105ddf5f642ee77c648ce8ccc4f"
    if (
        not isinstance(identity["actual"], str)
        or len(identity["actual"]) != 64
        or any(character not in "0123456789abcdef" for character in identity["actual"])
    ):
        return (
            "setup_failed",
            "Historical checkpoint has no actual SHA256 identity; not semantic RED.",
        )
    if mutant:
        valid = (
            result.returncode == 1
            and calls[0]["outcome"] == "failed"
            and "AssertionError: WHAT: historical-prerequisite-identity-conservation:"
            in calls[0]["crash"]
            and identity["expected"] == fixed
            and identity["actual"] != fixed
        )
    else:
        valid = (
            result.returncode == 0
            and calls[0]["outcome"] == "passed"
            and identity["expected"] == identity["actual"] == fixed
        )
    return (
        "satisfied" if valid else "assertion_failed",
        f"Historical identity proof {'satisfied' if valid else 'failed'}; expected "
        + ("fixed-d33 identity-assertion RED." if mutant else "fixed-d33 GREEN."),
    )


def mutate(root, locus, original, replacement):
    path = root / locus
    source = path.read_text()
    if source.count(original) != 1:
        raise RuntimeError(f"Exact baseline mutation locus unavailable: {locus}")
    before = digest(path)
    path.write_text(source.replace(original, replacement, 1))
    emit(
        {
            "label": "source-only-identity-mutation",
            "source_root": str(root),
            "path": locus,
            "before_sha256": before,
            "after_sha256": digest(path),
            "removed": original,
            "inserted": replacement,
        }
    )


def materialize_checkout(source):
    """Give exported bytes genuine, private Git metadata before any import.

    The runtime admits developer source through a real checkout marker. An
    archive alone is not that substrate; neither a freshness opt-out nor an
    invented install manifest may stand in for it. Commit the unmodified export
    before overlaying acceptance bytes, then copy this private repository with
    each source scope so none can write the host's shared Git state.
    """
    template = source.parent / "empty-git-template"
    template.mkdir()
    env = environment(source.parent, source)
    commands = (
        ["git", "init", "--quiet", "--template=" + str(template), str(source)],
        ["git", "-C", str(source), "add", "--force", "--all"],
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Identity Probe",
            "-c",
            "user.email=identity-probe@example.invalid",
            "commit",
            "--quiet",
            "--no-gpg-sign",
            "-m",
            "Immutable c429 source export",
        ],
        ["git", "-C", str(source), "rev-parse", "--verify", "HEAD"],
    )
    for argv in commands:
        result = subprocess.run(
            argv, env=env, cwd=source, capture_output=True, text=True, timeout=60
        )
        emit(
            {
                "label": "disposable-checkout-construction",
                "source_root": str(source),
                "argv": argv,
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Disposable real Git checkout construction failed; no identity observation ran."
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, choices=(BASELINE,))
    args = parser.parse_args()
    outcomes = {}
    try:
        with tempfile.TemporaryDirectory(
            prefix="design-identity-mutants-"
        ) as directory:
            scope = Path(directory)
            archive = scope / "baseline.tar"
            argv = [
                "git",
                "-C",
                str(ROOT),
                "archive",
                "--format=tar",
                "--output=" + str(archive),
                args.baseline,
            ]
            exported = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            emit(
                {
                    "label": "immutable-baseline-export",
                    "baseline": args.baseline,
                    "argv": argv,
                    "exit": exported.returncode,
                    "stdout": exported.stdout,
                    "stderr": exported.stderr,
                    "archive_sha256": digest(archive) if archive.is_file() else None,
                }
            )
            if exported.returncode != 0:
                raise RuntimeError(
                    "Exact-c429 Git archive unavailable; no control or mutant ran."
                )
            seed = scope / "seed"
            seed.mkdir()
            with tarfile.open(archive) as package:
                package.extractall(seed, filter="data")
            materialize_checkout(seed)
            baseline_identities = identities_without_overlay(seed)
            for name in OVERLAY:
                destination = seed / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            emit(
                {
                    "label": "acceptance-only-overlay",
                    "paths": list(OVERLAY),
                    "baseline_source_sha256": baseline_identities,
                    "overlaid_identities": identities(seed),
                }
            )
            if baseline_identities != identities(seed)["source_loci"]:
                raise RuntimeError("Acceptance overlay changed baseline source.")
            control_scope = scope / "control"
            control = control_scope / "source"
            shutil.copytree(seed, control)
            for kind, name in zip(
                ("public", "historical"), POPULATION[:2], strict=True
            ):
                # Each child has its own HOME/cache even when source is shared.
                execution = child(control, kind, name)
                status, diagnostic = assess(execution, kind, False)
                outcomes[name] = {"status": status, "diagnostic": diagnostic}
                if status != "satisfied":
                    break
                shutil.rmtree(control_scope / "home")
            if len(outcomes) == 2 and all(
                row["status"] == "satisfied" for row in outcomes.values()
            ):
                for kind, name, locus, original, replacement in (
                    (
                        "public",
                        POPULATION[2],
                        SOURCE_LOCI[0],
                        'and (key != "product_change" or value == "none")',
                        'and (key != "product_change" or value == "none" or "product_change" in manifest)',
                    ),
                    (
                        "historical",
                        POPULATION[3],
                        SOURCE_LOCI[1],
                        "            if (\n"
                        "                isinstance(item.authority, DesignFacts)\n"
                        '                and item.authority.product_change == "required"\n'
                        "            ):\n"
                        '                projection["authority"].pop("product_change", None)\n',
                        "",
                    ),
                ):
                    source = scope / name / "source"
                    shutil.copytree(seed, source)
                    mutate(source, locus, original, replacement)
                    if (
                        identities(source)["oracle_support_sha256"]
                        != identities(seed)["oracle_support_sha256"]
                    ):
                        raise RuntimeError(
                            "A source mutant changed the oracle or its supports."
                        )
                    status, diagnostic = assess(child(source, kind, name), kind, True)
                    outcomes[name] = {"status": status, "diagnostic": diagnostic}
    except Exception as error:
        emit({"label": "identity-probe-setup-failure", "diagnostic": repr(error)})
    for name in POPULATION:
        outcomes.setdefault(
            name,
            {
                "status": "setup_failed",
                "diagnostic": "Not executed: positive controls or disposable-source preparation unavailable.",
            },
        )
    counts = {
        status: sum(row["status"] == status for row in outcomes.values())
        for status in ("satisfied", "assertion_failed", "setup_failed")
    }
    emit(
        {
            "label": "identity-mutant-proof",
            "baseline": args.baseline,
            "population": list(POPULATION),
            "checkpoints": outcomes,
            "counts": counts,
        }
    )
    print(
        "DES-ORACLE-OBSERVATION: "
        + json.dumps(
            {
                "version": 1,
                "observed": counts["satisfied"] + counts["assertion_failed"],
                "assertions_failed": counts["assertion_failed"],
                "setup_failed": counts["setup_failed"],
            }
        ),
        flush=True,
    )
    return 2 if counts["setup_failed"] else 1 if counts["assertion_failed"] else 0


def identities_without_overlay(root):
    return {name: digest(root / name) for name in SOURCE_LOCI}


if __name__ == "__main__":
    raise SystemExit(main())
