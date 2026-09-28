"""Portable retained-record and executable-boundary fixtures for release tests.

These records model retained observations and byte bindings; they never assert
that a public package has actually been installed or upgraded.
"""

from __future__ import annotations

import base64
import hashlib
import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path


CHECKPOINTS = (
    "predecessor_identity",
    "candidate_wheel",
    "canonical_install_identity",
    "canonical_console_version",
    "canonical_installer",
    "public_des_migration",
    "doctor_json",
    "selected_root_config",
    "des_install_manifest",
)


CHANNEL_VERSIONS = {
    "dev": "1.2.3.dev1",
    "rc": "1.2.3rc1",
    "stable": "1.2.3",
    # The standalone GitHub prerelease intentionally uses this chosen RC
    # candidate instead of deriving another transport-specific version.
    "github-prerelease": "1.2.3rc1",
}


def candidate_version(channel: str, version: str | None = None) -> str:
    """Return the exact PEP 440 candidate version for a fixture channel."""
    if version is not None:
        return version
    try:
        return CHANNEL_VERSIONS[channel]
    except KeyError as error:
        raise ValueError(f"unknown fixture channel {channel!r}") from error


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def reference(path: Path, root: Path) -> dict[str, str]:
    return {"file": str(path.relative_to(root)), "sha256": sha256(path)}


def candidate_wheel(
    root: Path,
    *,
    channel: str = "rc",
    version: str | None = None,
    source_bytes: bytes = b"BOUND_MIGRATION = 'fixture'\n",
) -> tuple[Path, str]:
    """Write a consistent pure-Python wheel and return its mapped source member."""
    version = candidate_version(channel, version)
    member = "nwave_ai/release/decision.py"
    dist_info = f"nwave_ai-{version}.dist-info"
    wheel = root / "dist" / f"nwave_ai-{version}-py3-none-any.whl"
    wheel.parent.mkdir(parents=True, exist_ok=True)
    contents = {
        member: source_bytes,
        f"{dist_info}/METADATA": f"Metadata-Version: 2.1\nName: nwave-ai\nVersion: {version}\n".encode(),
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    rows = []
    for name, data in sorted(contents.items()):
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        )
        rows.append(f"{name},sha256={digest},{len(data)}")
    contents[f"{dist_info}/RECORD"] = (
        "\n".join(rows) + f"\n{dist_info}/RECORD,,\n"
    ).encode()
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    return wheel, member


def _observations(
    candidate: dict[str, object], predecessor: dict[str, str]
) -> dict[str, object]:
    version = str(candidate["version"])
    return {
        "predecessor_identity": {
            "distributions": {predecessor["name"]: predecessor["version"]},
            "module_owners": [predecessor["name"]],
        },
        "candidate_wheel": {
            "Name": candidate["name"],
            "Version": version,
            "SHA256": candidate["wheel"]["sha256"],
        },
        "canonical_install_identity": {
            "distributions": {candidate["name"]: version},
            "module_owners": [candidate["name"]],
        },
        "canonical_console_version": {"version": version},
        "canonical_installer": {"installed_version": version, "status": "ok"},
        "public_des_migration": {
            "migration_path": "scripts/release/publish_experimental.py",
            "status": "ok",
        },
        "doctor_json": {"summary": {"failed": 0}, "status": "ok"},
        "selected_root_config": {"installed_version": version, "status": "ok"},
        "des_install_manifest": {"installed_version": version, "status": "ok"},
    }


def required_upgrade_proof(
    root: Path, candidate: dict[str, object], predecessor: dict[str, str]
) -> dict[str, object]:
    """Create all nine exact retained observation shapes used by the validator."""
    checkpoints: dict[str, dict[str, str]] = {}
    for name, observation in _observations(candidate, predecessor).items():
        stdout = write_json(root / f"{name}.stdout.json", observation)
        stderr = root / f"{name}.stderr.bin"
        stderr.write_bytes(b"")
        checkpoint = write_json(
            root / f"{name}.json",
            {
                "checkpoint": name,
                "candidate": candidate,
                "predecessor": predecessor,
                "command": {
                    "argv": ["fixture", name],
                    "returncode": 0,
                    "stdout": reference(stdout, root),
                    "stderr": reference(stderr, root),
                },
            },
        )
        checkpoints[name] = reference(checkpoint, root)
    proof = write_json(
        root / "upgrade-proof.json",
        {
            "kind": "public-distribution-upgrade-v1",
            "candidate": candidate,
            "predecessor": predecessor,
            "checkpoints": checkpoints,
        },
    )
    return {
        "kind": "public-distribution-upgrade-v1",
        "record": reference(proof, root),
        "checkpoints": checkpoints,
    }


def _rebase_proof(record: Path) -> None:
    root = record.parent
    value = json.loads(record.read_text(encoding="utf-8"))
    binding = value["migration"]["upgrade_proof"]
    candidate = value["candidate"]
    predecessor = {
        "name": value["predecessor"]["distribution_name"],
        "version": value["predecessor"]["version"],
    }
    checkpoints: dict[str, dict[str, str]] = {}
    for name in CHECKPOINTS:
        path = root / f"{name}.json"
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        checkpoint["candidate"] = candidate
        checkpoint["predecessor"] = predecessor
        command = checkpoint["command"]
        command["stdout"] = reference(root / command["stdout"]["file"], root)
        command["stderr"] = reference(root / command["stderr"]["file"], root)
        write_json(path, checkpoint)
        checkpoints[name] = reference(path, root)
    proof_path = root / binding["record"]["file"]
    write_json(
        proof_path,
        {
            "kind": "public-distribution-upgrade-v1",
            "candidate": candidate,
            "predecessor": predecessor,
            "checkpoints": checkpoints,
        },
    )
    binding["checkpoints"] = checkpoints
    binding["record"] = reference(proof_path, root)
    write_json(record, value)


def update_checkpoint(record: Path, name: str, observation: object) -> None:
    """Replace a raw stdout observation and rehash checkpoint, proof, and decision."""
    if name not in CHECKPOINTS:
        raise ValueError(f"unknown checkpoint {name!r}")
    root = record.parent
    checkpoint = json.loads((root / f"{name}.json").read_text(encoding="utf-8"))
    command = checkpoint.get("command")
    if not isinstance(command, dict):
        raise ValueError(f"checkpoint {name!r} has no command observation")
    write_json(root / command["stdout"]["file"], observation)
    _rebase_proof(record)


def rewrite_wheel_member(record: Path, member: str, data: bytes) -> None:
    """Rewrite one wheel member and recursively rebind wheel/proof references."""
    root = record.parent
    value = json.loads(record.read_text(encoding="utf-8"))
    wheel = root / value["candidate"]["wheel"]["file"]
    with zipfile.ZipFile(wheel) as archive:
        members = {
            info.filename: archive.read(info.filename) for info in archive.infolist()
        }
    if member not in members:
        raise ValueError(f"wheel member {member!r} is absent")
    members[member] = data
    record_member = next(name for name in members if name.endswith(".dist-info/RECORD"))
    rows = []
    for name, contents in sorted(members.items()):
        if name != record_member:
            digest = (
                base64.urlsafe_b64encode(hashlib.sha256(contents).digest())
                .decode()
                .rstrip("=")
            )
            rows.append(f"{name},sha256={digest},{len(contents)}")
    members[record_member] = ("\n".join(rows) + f"\n{record_member},,\n").encode()
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    value["candidate"]["wheel"] = reference(wheel, root)
    write_json(record, value)
    stdout = root / "candidate_wheel.stdout.json"
    observed = json.loads(stdout.read_text(encoding="utf-8"))
    observed["SHA256"] = value["candidate"]["wheel"]["sha256"]
    write_json(stdout, observed)
    _rebase_proof(record)


#: The source blob and candidate artifact a fixture decision binds by default.
_DEFAULT_SOURCE_SHA = "a" * 40
_DEFAULT_SOURCE_PATH = "src/release/decision.py"
_DEFAULT_SOURCE_BYTES = b"BOUND_MIGRATION = 'fixture'\n"


@dataclass(frozen=True, kw_only=True)
class DecisionBinding:
    """What one fixture decision BINDS: a source blob and a candidate artifact.

    Keyword-only, and load-bearing: `source_sha`, `source_path`, `wheel_member`
    and `version` are all strings or None, so a positional permutation binds a
    decision to a sha named by a path, or an archive member named by a version,
    and nothing raises.

    There is no `predecessor` field. `decision` took one and never read it: the
    record's predecessor is the hardcoded `prior` below, because a caller with its
    own branch predecessor carries it on the BRANCH UNIT instead.
    """

    source_sha: str = _DEFAULT_SOURCE_SHA
    source_path: str = _DEFAULT_SOURCE_PATH
    source_bytes: bytes = _DEFAULT_SOURCE_BYTES
    wheel: Path | None = None
    wheel_member: str | None = None
    version: str | None = None


_DEFAULT_BINDING = DecisionBinding()


def decision(
    root: Path,
    *,
    channel: str,
    units: list[dict[str, object]],
    required: bool = False,
    binding: DecisionBinding = _DEFAULT_BINDING,
) -> Path:
    """Construct one decision around the supplied retained candidate wheel.

    Callers which publish an asset create the wheel first and pass that exact
    path here.  This deliberately prevents a later fixture call from replacing
    the bytes whose digest the publication unit already bound.
    """
    source_sha = binding.source_sha
    source_path = binding.source_path
    source_bytes = binding.source_bytes
    wheel = binding.wheel
    wheel_member = binding.wheel_member
    version = candidate_version(channel, binding.version)
    if wheel is None:
        wheel, member = candidate_wheel(
            root, channel=channel, version=version, source_bytes=source_bytes
        )
    else:
        member = wheel_member or "nwave_ai/release/decision.py"
    candidate: dict[str, object] = {
        "source_sha": source_sha,
        "name": "nwave-ai",
        "version": version,
        "wheel": reference(wheel, root),
    }
    # The fixture record must bind a real immutable predecessor in the selected
    # source repository.  Callers with a separate branch predecessor retain it
    # on that branch unit, where the live writer checks it with its lease.
    prior = {"distribution_name": "nwave-ai", "version": "1.2.2"}
    evidence = write_json(
        root / "compatibility.json", {"boundary": "fixture compatibility"}
    )
    migration: dict[str, object] = {
        "required": required,
        "compatibility_boundary": "fixture compatibility",
        "evidence": [reference(evidence, root)],
    }
    if required:
        source = root / source_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(source_bytes)
        migration.update(
            {
                "path": source_path,
                "source_locator": {"repo_path": source_path},
                "wheel_locator": {"archive_member": member},
                "upgrade_proof": required_upgrade_proof(
                    root, candidate, {"name": "nwave-ai", "version": "1.2.2"}
                ),
            }
        )
    return write_json(
        root / "decision.json",
        {
            "schema": "nwave.release-migration-decision.v4",
            "channel": channel,
            "candidate": candidate,
            "predecessor": prior,
            "migration": migration,
            "publication_units": units,
        },
    )


def fake_executable(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


FAKE_GH = r"""import hashlib, json, os, sys
path = os.environ["FAKE_GH_STATE"]
state = json.loads(open(path).read()) if os.path.exists(path) else {"releases": {}, "tags": {}, "runs": [], "calls": []}
for key, default in (("releases", {}), ("tags", {}), ("runs", []), ("calls", [])):
    state.setdefault(key, default)
args = sys.argv[1:]
state["calls"].append(args)
def save():
    with open(path, "w") as handle: json.dump(state, handle, sort_keys=True)
def fail(message):
    save(); raise SystemExit(message)
def option(name, default=None):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default
def emit(value):
    save(); print(json.dumps(value, sort_keys=True)); raise SystemExit(0)
route = next((arg for arg in args if arg.startswith("repos/")), None)
if route is not None:
    path_only = route.split("?", 1)[0]
    parts = path_only.strip("/").split("/")
    if parts[-1] == "releases":
        pages = state.get("release_pages")
        if pages is None: pages = [list(state["releases"].values())]
        emit(pages)
    if len(parts) >= 5 and parts[-3] == "releases" and parts[-2] == "tags":
        release = state["releases"].get(parts[-1])
        if release is None: fail("release not found")
        emit(release)
    if len(parts) >= 4 and parts[-1] == "assets" and parts[-3] == "releases":
        release = next((item for item in state["releases"].values() if str(item["id"]) == parts[-2]), None)
        if release is None: fail("release not found")
        emit(release["assets"])
    if len(parts) >= 5 and parts[-3] == "ref" and parts[-2] == "tags":
        sha = state["tags"].get(parts[-1])
        if sha is None: fail("tag not found")
        emit({"ref": "refs/tags/" + parts[-1], "object": {"type": "commit", "sha": sha}})
    if len(parts) >= 5 and parts[-2] == "tags":
        item = state.get("annotated_tags", {}).get(parts[-1])
        if item is None: fail("annotated tag not found")
        emit(item)
    fail("unexpected gh api " + repr(args))
if args[:2] == ["release", "view"]:
    release = state["releases"].get(args[2]) if len(args) > 2 else None
    if release is None: fail("release not found")
    names = {"tagName": "tag_name", "targetCommitish": "target_commitish", "isPrerelease": "prerelease"}
    emit({field: release[names.get(field, field)] for field in option("--json", "").split(",") if names.get(field, field) in release})
if args[:2] == ["release", "create"]:
    if len(args) < 3 or args[2] in state["releases"]: fail("invalid or duplicate release")
    tag, target = args[2], option("--target")
    if not target: fail("--target is required")
    if tag in state["tags"] and state["tags"][tag] != target: fail("tag target differs")
    notes = option("--notes-file")
    release_id = max([item["id"] for item in state["releases"].values()] + [0]) + 1
    state["releases"][tag] = {"id": release_id, "tag_name": tag, "target_commitish": target, "name": option("--title", tag), "body": open(notes).read() if notes else "", "prerelease": "--prerelease" in args, "assets": []}
    state["tags"][tag] = target
    save(); raise SystemExit(0)
if args[:2] == ["release", "upload"]:
    if len(args) < 4 or "--clobber" in args: fail("invalid upload")
    release = state["releases"].get(args[2])
    if release is None: fail("release not found")
    filenames, index = [], 3
    while index < len(args):
        if args[index] == "--repo":
            index += 2
            continue
        if args[index].startswith("-"):
            index += 1
            continue
        filenames.append(args[index])
        index += 1
    for filename in filenames:
        data, name = open(filename, "rb").read(), os.path.basename(filename)
        if any(asset["name"] == name for asset in release["assets"]): fail("asset already exists")
        asset_id = max([asset["id"] for asset in release["assets"]] + [0]) + 1
        release["assets"].append({"name": name, "size": len(data), "digest": "sha256:" + hashlib.sha256(data).hexdigest(), "id": asset_id})
    save(); raise SystemExit(0)
if args[:2] == ["run", "list"]:
    fields = option("--json", "").split(",")
    emit([{field: run[field] for field in fields if field in run} for run in state["runs"]])
if args[:2] == ["run", "view"]:
    run = next((item for item in state["runs"] if str(item["databaseId"]) == (args[2] if len(args) > 2 else "")), None)
    if run is None: fail("run not found")
    emit({field: run[field] for field in option("--json", "").split(",") if field in run})
if args[:2] == ["workflow", "run"]:
    workflow, ref = (args[2] if len(args) > 2 else ""), option("--ref")
    if not workflow or not ref: fail("workflow and --ref are required")
    fields, index = {}, 0
    while index < len(args):
        if args[index] in ("-f", "--field") and index + 1 < len(args): fields.update([args[index + 1].split("=", 1)]); index += 1
        index += 1
    refs_path = os.environ.get("FAKE_GH_SOURCE_REFS")
    source_refs = json.loads(open(refs_path).read()) if refs_path and os.path.exists(refs_path) else {}
    head_sha = source_refs.get(ref)
    if not head_sha: fail("no exact source SHA is mapped for ref " + repr(ref))
    run_id = max([run["databaseId"] for run in state["runs"]] + [0]) + 1
    state["runs"].append({"databaseId": run_id, "headSha": head_sha, "status": "queued", "conclusion": None, "displayTitle": workflow, **fields})
    save(); raise SystemExit(0)
fail("unexpected gh command " + repr(args))
"""


FAKE_TWINE = r"""import hashlib, json, os, sys
path = os.environ["FAKE_TWINE_STATE"]
state = json.loads(open(path).read()) if os.path.exists(path) else {"files": []}
state.setdefault("files", [])
state.setdefault("uploads", [])
args = sys.argv[1:]
if not args or args[0] != "upload": raise SystemExit("unexpected twine command " + repr(args))
option_values = {"--repository-url", "--repository", "--username", "--password", "--config-file", "--cert", "--client-cert", "--comment"}
filenames = []
index = 1
while index < len(args):
    arg = args[index]
    if arg in option_values:
        index += 2
        continue
    if arg.startswith("-"):
        index += 1
        continue
    filenames.append(arg)
    index += 1
for filename in filenames:
    data, name = open(filename, "rb").read(), os.path.basename(filename)
    if any(item["filename"] == name for item in state["files"]): raise SystemExit("package already exists")
    state["files"].append({"filename": name, "sha256": hashlib.sha256(data).hexdigest()})
    state["uploads"].append({"filename": name, "sha256": hashlib.sha256(data).hexdigest()})
with open(path, "w") as handle: json.dump(state, handle, sort_keys=True)
"""


FAKE_GIT = r"""import os, subprocess, sys
raise SystemExit(subprocess.run([os.environ["FAKE_GIT_REAL"], *sys.argv[1:]], stdin=subprocess.DEVNULL, timeout=60).returncode)
"""
