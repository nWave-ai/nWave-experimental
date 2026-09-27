#!/usr/bin/env python3
"""Local two-phase producer for reviewable v3 migration-decision bundles."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def refuse(x: str) -> None:
    raise ValueError(
        f"REFUSAL: bundle producer. WHY: {x}. HOW: retain confined exact local inputs."
    )


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def regular(p: Path, what: str) -> Path:
    if p.is_symlink() or not p.is_file():
        refuse(f"{what} is not a regular file")
    return p.resolve()


def directory(p: Path, what: str) -> Path:
    if p.is_symlink() or not p.is_dir():
        refuse(f"{what} is not a real directory")
    return p.resolve()


def git(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    r = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if r.returncode:
        refuse(
            f"git {' '.join(args)} failed: {r.stderr.decode(errors='replace').strip()}"
        )
    return r.stdout if binary else r.stdout.decode().strip()


def load(p: Path) -> dict[str, object]:
    try:
        x = json.loads(regular(p, "JSON input").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        refuse(f"invalid JSON: {e}")
    if not isinstance(x, dict):
        refuse("JSON root is not an object")
    return x


def uid(x: object) -> str:
    if (
        not isinstance(x, str)
        or not x
        or Path(x).is_absolute()
        or "/" in x
        or "\\" in x
        or x in {".", ".."}
    ):
        refuse("generated unit id is not a confined filename")
    return x


def declares_this_source(unit: dict[str, object], sha: str) -> bool:
    """Whether a generated unit declares the sha this run was asked to bind.

    This is the v4 decoder's own `spec.original_source_sha != candidate.source_sha`
    rule, projected forward to input time so an operator hears the same verdict
    before any wheel is built instead of minutes later.
    """
    return unit.get("original_source_sha") == sha


def wheel_meta(p: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                refuse("wheel has no unique METADATA")
            fields = dict(
                line.split(": ", 1)
                for line in z.read(names[0]).decode().splitlines()
                if ": " in line
            )
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as e:
        refuse(f"wheel is unreadable: {e}")
    if not isinstance(fields.get("Name"), str) or not isinstance(
        fields.get("Version"), str
    ):
        refuse("wheel lacks Name or Version")
    return fields["Name"], fields["Version"]


def copy_artifact(root: Path, source: Path, seen: dict[str, str]) -> dict[str, str]:
    source = regular(source, "retained artifact")
    rel = f"artifacts/{source.name}"
    h = digest(source)
    if rel in seen:
        if seen[rel] != h:
            refuse(f"different retained artifacts collide at {rel}")
        return {"file": rel, "sha256": h}
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    seen[rel] = h
    return {"file": rel, "sha256": h}


def copy_wheelhouse(
    root: Path, wheelhouse: Path, seen: dict[str, str]
) -> list[dict[str, str]]:
    """Retain a candidate's adjacent offline wheelhouse beside its wheel.

    `scripts/release/offline_wheelhouse_hook.py` (a Hatch build hook wired in
    `pyproject.toml`) writes this directory next to every wheel this project
    builds -- and `scripts/release/smoke_opencode_installed_hook.py` requires
    it at `<wheel>.parent / "offline-wheelhouse" / "requirements.lock"` before
    it will install and smoke a candidate.  A bundle-retained wheel is no
    longer sitting next to the worktree that built it, so without this the
    smoke step fails downstream in a job that never touched a broken wheel --
    just an incomplete retained handoff (CI run 34590377773).
    """
    wheelhouse = directory(wheelhouse, "candidate wheelhouse")
    lock = wheelhouse / "requirements.lock"
    if lock.is_symlink() or not lock.is_file():
        refuse("candidate wheelhouse has no requirements.lock")
    entries: list[dict[str, str]] = []
    for source in sorted(wheelhouse.rglob("*")):
        if source.is_dir():
            continue
        if source.is_symlink() or not source.is_file():
            refuse("candidate wheelhouse contains a non-regular entry")
        rel = f"artifacts/offline-wheelhouse/{source.relative_to(wheelhouse)}"
        h = digest(source)
        if rel in seen:
            if seen[rel] != h:
                refuse(f"different retained wheelhouse files collide at {rel}")
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        seen[rel] = h
        entries.append({"file": rel, "sha256": h})
    if not any(entry["file"].endswith("/requirements.lock") for entry in entries):
        refuse("candidate wheelhouse capture lost requirements.lock")
    return entries


def capture_inputs(
    plan: dict[str, object],
) -> tuple[list[Path], dict[str, Path], list[dict[str, object]]]:
    """Validate every capture destination before creating its output directory.

    The bundle is a review record.  A malformed plan must therefore not leave a
    partially captured record behind, even when its bad value would only be
    consumed later while archiving a generated worktree.
    """
    retained: list[Path] = []
    destination_sources: dict[str, Path] = {}

    def add_artifact(value: object, what: str) -> Path:
        if not isinstance(value, str):
            refuse(f"{what} must be a path")
        source = regular(Path(value), what)
        destination = f"artifacts/{source.name}"
        prior = destination_sources.get(destination)
        if prior is not None and prior != source:
            refuse(f"retained artifact archive-name collision at {destination}")
        destination_sources[destination] = source
        return source

    # Check all generated unit ids before output.mkdir().  In particular this
    # blocks ../ names before they can influence generated/<unit>/ paths.
    units = plan.get("publication_units")
    if not isinstance(units, list) or not units:
        refuse("plan needs predecessor and publication_units")
    captured_units: list[dict[str, object]] = []
    generated_ids: set[str] = set()
    for raw in units:
        if not isinstance(raw, dict):
            refuse("publication unit is not an object")
        unit = dict(raw)
        if unit.get("kind") == "generated_commit":
            unit_id = uid(unit.get("id"))
            if unit_id in generated_ids:
                refuse("generated unit id is duplicated")
            generated_ids.add(unit_id)
        captured_units.append(unit)

    for raw in plan.get("retained_artifacts", []):
        retained.append(add_artifact(raw, "retained artifact"))
    return retained, destination_sources, captured_units


def archive_tree(
    root: Path, unit: str, work: Path, parent: str
) -> tuple[str, dict[str, str]]:
    tree = git(work, "write-tree")
    if not isinstance(tree, str) or len(tree) != 40:
        refuse("write-tree did not emit an object id")
    if git(work, "rev-parse", "--verify", f"{parent}^{{commit}}") != parent:
        refuse("generated parent is absent from generated worktree")
    folder = root / "generated" / uid(unit)
    folder.mkdir(parents=True)
    archive = git(work, "archive", "--format=tar", tree, binary=True)
    patch = git(work, "diff", "--binary", parent, tree, binary=True)
    assert isinstance(archive, bytes) and isinstance(patch, bytes)
    (folder / "tree.tar").write_bytes(archive)
    (folder / "changes.patch").write_bytes(patch)
    return tree, {
        "tree_review": str((folder / "tree.tar").relative_to(root)),
        "changes_review": str((folder / "changes.patch").relative_to(root)),
    }


def capture(a: argparse.Namespace) -> int:
    raw_source, raw_output = Path(a.source_repo), Path(a.output)
    source, output = directory(raw_source, "source repository"), raw_output.absolute()
    if raw_output.is_symlink() or output.exists():
        refuse("capture output already exists or is a symlink")
    wheel, plan = (
        regular(Path(a.candidate_wheel), "candidate wheel"),
        load(Path(a.publication_plan)),
    )
    source_sha = git(source, "rev-parse", "--verify", f"{a.source_sha}^{{commit}}")
    if not isinstance(source_sha, str):
        refuse("source SHA is invalid")
    predecessor = plan.get("predecessor")
    if predecessor is not None and not isinstance(predecessor, dict):
        refuse("plan needs predecessor and publication_units")
    works = {}
    for x in a.generated_worktree:
        if "=" not in x:
            refuse("generated worktree must be UNIT=PATH")
        k, v = x.split("=", 1)
        k = uid(k)
        if k in works:
            refuse("generated worktree unit is duplicated")
        works[k] = directory(Path(v), "generated worktree")
    retained_sources, destination_sources, captured = capture_inputs(plan)
    # The candidate is also retained.  Validate its archive destination before
    # creating output so a same-basename evidence file cannot leave a partial
    # bundle on disk.
    candidate_destination = f"artifacts/{wheel.name}"
    candidate_source = wheel.resolve()
    prior = destination_sources.get(candidate_destination)
    if prior is not None and prior != candidate_source:
        refuse(f"retained artifact archive-name collision at {candidate_destination}")
    output.mkdir(parents=True)
    seen = {}
    wheel_ref = copy_artifact(output, wheel, seen)
    name, version = wheel_meta(output / wheel_ref["file"])
    retained = [wheel_ref]
    if a.candidate_wheelhouse is not None:
        retained.extend(copy_wheelhouse(output, Path(a.candidate_wheelhouse), seen))
    for artifact in retained_sources:
        retained.append(copy_artifact(output, artifact, seen))
    review = {}
    for unit in captured:
        if unit.get("kind") == "generated_commit":
            k = uid(unit.get("id"))
            parent = unit.get("parent_oid")
            if (
                k not in works
                or not isinstance(parent, str)
                or unit.get("original_source_sha") != source_sha
            ):
                refuse("generated unit lacks matching local facts")
            tree, material = archive_tree(output, k, works[k], parent)
            unit["tree_oid"] = tree
            review[k] = material
    review_artifacts = []
    for material in review.values():
        for relative in material.values():
            path = output / relative
            review_artifacts.append(
                {"file": relative, "sha256": digest(path), "size": path.stat().st_size}
            )
    facts = {
        "schema": "nwave.release-migration-prepared.v2",
        "channel": a.channel,
        "source_repo": str(source),
        "candidate": {
            "source_sha": source_sha,
            "name": name,
            "version": version,
            "wheel": wheel_ref,
        },
        "predecessor": predecessor,
        "publication_units": captured,
        "artifacts": [
            {**x, "size": (output / x["file"]).stat().st_size} for x in retained
        ]
        + review_artifacts,
        "generated_review": review,
    }
    (output / "prepared-release.json").write_text(
        json.dumps(facts, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    (output / "artifact-manifest.json").write_text(
        json.dumps(facts["artifacts"], sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"prepared": str(output / "prepared-release.json"), "candidate": wheel_ref},
            sort_keys=True,
        )
    )
    return 0


def zip_bytes(stage: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_symlink():
                refuse("staging contains symlink")
            if p.is_file():
                i = zipfile.ZipInfo(str(p.relative_to(stage)))
                i.date_time = (1980, 1, 1, 0, 0, 0)
                i.external_attr = 0o100644 << 16
                i.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(i, p.read_bytes())
    return buf.getvalue()


def assemble(a: argparse.Namespace) -> int:
    from scripts.release.release_migration_decision import SCHEMA, decode_decision

    prepared = regular(Path(a.prepared), "prepared facts")
    root = prepared.parent.resolve()
    migration = load(Path(a.migration))
    output = Path(a.output).absolute()
    if output.is_symlink() or output == root or root in output.parents:
        refuse("bundle output must be outside prepared directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    facts = load(prepared)
    try:
        if facts["schema"] != "nwave.release-migration-prepared.v2":
            refuse("prepared facts schema is unsupported")
        decision = {
            "schema": SCHEMA,
            "channel": facts["channel"],
            "candidate": facts["candidate"],
            "predecessor": facts["predecessor"],
            "migration": migration,
            "publication_units": facts["publication_units"],
        }
        source = directory(Path(facts["source_repo"]), "prepared source repository")
    except (KeyError, TypeError):
        refuse("prepared facts are malformed")
    stage = Path(
        tempfile.mkdtemp(prefix=".release-migration-stage-", dir=output.parent)
    )
    try:
        artifacts = facts.get("artifacts")
        if not isinstance(artifacts, list):
            refuse("prepared artifact manifest is malformed")
        for item in artifacts:
            if not isinstance(item, dict):
                refuse("prepared artifact entry is malformed")
            file, sha256, size = item.get("file"), item.get("sha256"), item.get("size")
            if (
                not isinstance(file, str)
                or Path(file).is_absolute()
                or ".." in Path(file).parts
            ):
                refuse("prepared artifact path escapes the capture")
            path = root / file
            if (
                not isinstance(sha256, str)
                or not isinstance(size, int)
                or not path.is_file()
                or path.is_symlink()
                or digest(path) != sha256
                or path.stat().st_size != size
            ):
                refuse("prepared artifact bytes differ from captured manifest")
        for p in root.rglob("*"):
            if p.is_symlink():
                refuse("prepared directory contains symlink")
            if p.is_file():
                target = stage / p.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
        dp = stage / "decision.json"
        dp.write_text(
            json.dumps(decision, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        decode_decision(dp, source)
        data = zip_bytes(stage)
        decision_digest = hashlib.sha256(dp.read_bytes()).hexdigest()
        if output.exists():
            if not output.is_file() or output.read_bytes() != data:
                refuse("existing bundle differs; preserve it and choose another output")
        else:
            fd, name = tempfile.mkstemp(
                prefix="." + output.name + ".", dir=output.parent
            )
            temp = Path(name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temp, output)
                except FileExistsError:
                    if not output.is_file() or output.read_bytes() != data:
                        refuse(
                            "existing bundle differs; preserve it and choose another output"
                        )
            finally:
                temp.unlink(missing_ok=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print(
        json.dumps(
            {"bundle": str(output), "decision_sha256": decision_digest}, sort_keys=True
        )
    )
    return 0


def step(argv: list[str], cwd: Path, what: str) -> None:
    """Run one build step and bind the refusal to its EXIT STATUS.

    Never to the presence of `dist/*.whl`: the offline wheelhouse hook runs
    AFTER the artifact exists, so a failed build can leave a complete,
    correctly named wheel behind, while a build-environment failure leaves
    none.  Neither presence nor absence is informative; the exit status is.
    """
    result = subprocess.run(
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    if result.returncode:
        lines = ((result.stderr or "") + (result.stdout or "")).strip().splitlines()
        detail = lines[-1].strip()[:200] if lines else "no output"
        refuse(f"{what} exited {result.returncode}: {detail}")


def build_candidate(sha: str, scratch: Path) -> Path:
    """Build the candidate wheel isolated on exactly `sha`, inside `scratch`."""
    from scripts.release.experimental_migration_decision import short_sha_of
    from scripts.release.publish_experimental import (
        export_committed_tree,
        prepare_experimental_distribution,
    )

    export = scratch / "export"
    export_committed_tree(sha, export)
    # The SAME abbreviation the expectation is derived from; never re-derived
    # by asking git to abbreviate again.
    prepare_experimental_distribution(export, short_sha_of(sha))
    step(
        [
            sys.executable,
            str(export / "scripts/build_dist.py"),
            "--project-root",
            str(export),
        ],
        export,
        "build_dist.py",
    )
    step(
        [
            sys.executable,
            str(export / "scripts/release/stage_public_wheel_des.py"),
            "--project-root",
            str(export),
            "--cleanup-dist",
        ],
        export,
        "stage_public_wheel_des.py",
    )
    step([sys.executable, "-m", "build", "--wheel"], export, "python -m build --wheel")
    wheels = sorted((export / "dist").glob("*.whl"))
    if len(wheels) != 1:
        refuse(
            f"candidate build left {len(wheels)} wheels in dist; expected exactly one"
        )
    step(
        [
            sys.executable,
            str(export / "scripts/release/verify_wheel_privacy.py"),
            str(wheels[0]),
        ],
        export,
        "verify_wheel_privacy.py",
    )
    return wheels[0]


def project_generated_worktree(sha: str, destination: Path | None, into: Path) -> Path:
    """Materialise what publishing `sha` would publish, via the PUBLISHER itself.

    Drives the publisher's own non-publishing `--project-into` mode as a
    SUBPROCESS, so the publisher remains the single definition of "what would be
    published" and this producer never restates that projection.  Segregating a
    review channel must not mean duplicating a contract.

    The refusal is bound to that subprocess's EXIT STATUS, never to the presence
    of a worktree, so a failed projection reads as one REFUSAL line and no
    bundle.  `--allow-branch` is deliberate and safe: nothing is published in
    this mode, and the candidate is bound by the exact `--ref` sha rather than by
    whichever branch the operator happens to stand on.
    """
    argv = [
        sys.executable,
        str(ROOT / "scripts/release/publish_experimental.py"),
        "--ref",
        sha,
        "--project-into",
        str(into),
        "--allow-branch",
    ]
    if destination is not None:
        argv.extend(["--target-local-repo", str(destination)])
    step(argv, ROOT, "publish_experimental.py --project-into")
    worktree = into / "target"
    if worktree.is_symlink() or not worktree.is_dir():
        refuse("publisher projection left no generated worktree to capture")
    return worktree.resolve()


def observed_predecessor(destination: Path | None) -> tuple[str, str, str, str]:
    """Read the PUBLISHED predecessor off the destination, read-only.

    Reuses the publisher's own `target_snapshot` as the sole destination
    observation seam -- local `git --git-dir` reads when `destination` is a bare
    repository, otherwise three read-only `gh api` GETs against the real public
    target.  Nothing is cloned, fetched, pushed or released.

    The identity comes from ONE source: `[project] name`/`version` of the head
    commit's `pyproject.toml` -- precisely the two fields the publisher's own
    predecessor gate compares.  Every destination fault is re-raised inside the
    producer's refusal grammar, so a bad destination reads as one REFUSAL line
    rather than a raw git argv escaping through main()'s generic handler.
    """
    from scripts.release.publish_experimental import target_snapshot

    what = str(destination) if destination is not None else public_destination()
    try:
        commit, pyproject_text, _message = target_snapshot(destination)
    except (subprocess.CalledProcessError, OSError) as error:
        refuse(f"could not read the published predecessor on {what}: {error}")
    try:
        project = tomllib.loads(pyproject_text)["project"]
        name, version = project["name"], project["version"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError, AttributeError) as error:
        refuse(
            f"published predecessor on {what} has no readable "
            f"[project] name/version at {commit}: {error}"
        )
    if not isinstance(name, str) or not isinstance(version, str):
        refuse(f"published predecessor on {what} declares a non-string identity")
    return commit, pyproject_text, name, version


def public_destination() -> str:
    """Name the real public target the way an operator recognises it."""
    from scripts.release.publish_experimental import TARGET_BRANCH, TARGET_SLUG

    return f"{TARGET_SLUG}@{TARGET_BRANCH}"


def bind_observed_predecessor(
    plan: dict[str, object], commit: str, name: str, version: str
) -> dict[str, object]:
    """Return the operator's plan with the OBSERVED predecessor bound into it.

    Three facts, and only three, are rewritten: the top-level predecessor
    identity, the CAS lease of the sole `git_branch` unit for the target branch
    -- selected by the same 'exactly one git_branch unit for main' rule the
    publisher applies -- and the `parent_oid` of a `generated_commit` unit, which
    becomes that same observed destination head.  The patch base is therefore
    never taken from the operator's guess, exactly as the CAS lease is not.
    This deliberately narrows 'keep the operator's plan bytes verbatim' for
    exactly those fields: the predecessor is observed on the destination, never
    taken on trust, so the plan's own predecessor key is optional here and
    ignored.  Pure: the argument is not mutated.

    At most ONE `generated_commit` unit is admissible, mirroring the publisher's
    own 'exactly one git_branch unit for main' rule: the publishable tree is a
    deterministic function of the candidate sha, so a second generated unit could
    only carry byte-identical material while pretending to be a distinct
    publication.
    """
    from scripts.release.publish_experimental import TARGET_BRANCH

    units = plan.get("publication_units")
    if not isinstance(units, list) or not units:
        refuse("plan needs predecessor and publication_units")
    bound_units: list[object] = []
    matches = 0
    generated = 0
    for raw in units:
        if not isinstance(raw, dict):
            refuse("publication unit is not an object")
        if raw.get("kind") == "git_branch" and raw.get("branch") == TARGET_BRANCH:
            matches += 1
            bound_units.append({**raw, "predecessor": commit})
        elif raw.get("kind") == "generated_commit":
            generated += 1
            bound_units.append({**raw, "parent_oid": commit})
        else:
            bound_units.append(dict(raw))
    if generated > 1:
        refuse(
            f"plan must declare at most one generated_commit unit, because the "
            f"publishable tree is a deterministic function of the candidate sha, "
            f"not {generated}"
        )
    if matches != 1:
        refuse(
            f"plan must declare exactly one git_branch unit for {TARGET_BRANCH} "
            f"to carry the observed predecessor lease, not {matches}"
        )
    return {
        **plan,
        "predecessor": {"distribution_name": name, "version": version},
        "publication_units": bound_units,
    }


def produce_decision_bundle(a: argparse.Namespace) -> int:
    """Compose capture + assemble in ONE local run, bound to one exact sha."""
    from scripts.release.experimental_migration_decision import (
        DecisionRefusal,
        projected_candidate,
        validate_predecessor_metadata,
    )
    from scripts.release.release_migration_decision import decode_decision

    if a.channel != "experimental":
        refuse("produce-decision-bundle serves only the experimental channel")
    repo_root = directory(ROOT, "source repository")
    plan_path = regular(Path(a.publication_plan), "publication plan")
    migration_path = regular(Path(a.migration), "migration block")
    raw_output = Path(a.output)
    if raw_output.is_symlink():
        refuse("bundle output is a symlink")
    output = raw_output.absolute()
    sha = git(repo_root, "rev-parse", "--verify", f"{a.source_sha}^{{commit}}")
    if not isinstance(sha, str) or len(sha) != 40:
        refuse("source SHA is invalid")
    try:
        expected = projected_candidate(repo_root, sha)
    except DecisionRefusal as error:
        refuse(str(error))

    # Pre-flight sha-faithfulness gate.  The operator's plan is loaded ONCE here
    # and reused for the binding below, so a malformed plan refuses through the
    # `load` grammar pre-flight and no time-of-check/time-of-use window is left
    # between this gate and the binding.  Inputs that cannot yield a bundle
    # faithful to this sha are decided from the operator's own bytes, before the
    # destination is touched, before any wheel is built and before any scratch
    # directory exists -- so 'no partial output' holds by construction.
    plan = load(plan_path)
    units = plan.get("publication_units")
    for unit in units if isinstance(units, list) else []:
        if not isinstance(unit, dict) or unit.get("kind") != "generated_commit":
            continue
        if not declares_this_source(unit, sha):
            refuse(
                f"publication unit {unit.get('id')!r} declares its generated "
                f"material as coming from original_source_sha "
                f"{unit.get('original_source_sha')!r}, but this run was asked to "
                f"bind {sha}; no bundle built from these inputs could be faithful "
                f"to that sha"
            )

    # Observe the destination BEFORE any scratch directory or candidate build:
    # the publisher reads its target first for the same reason, so a stale or
    # unreachable destination refuses without first spending minutes on a wheel.
    destination = None
    if a.target_local_repo is not None:
        destination = Path(a.target_local_repo).absolute()
        bare = subprocess.run(
            ["git", "--git-dir", str(destination), "rev-parse", "--is-bare-repository"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if bare.returncode or bare.stdout.strip() != "true":
            refuse(
                f"--target-local-repo {destination} is not an existing bare Git "
                "repository; observation must not fall back to the public target"
            )
    destination_label = (
        str(destination) if destination is not None else public_destination()
    )
    observed_commit, observed_pyproject, observed_name, observed_version = (
        observed_predecessor(destination)
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    existed_before = output.exists()
    scratch = Path(
        tempfile.mkdtemp(prefix=".produce-decision-bundle-", dir=output.parent)
    )
    try:
        wheel = build_candidate(sha, scratch)
        # Defensive construction invariant: the stamp and the expectation share
        # one source, so an honest build agrees here by construction.
        if wheel_meta(wheel) != (expected.name, expected.version):
            refuse("built wheel is not the candidate projected for this source sha")
        prepared = scratch / "prepared"
        # Bind by feeding capture() a REWRITTEN COPY of the operator's plan.
        # capture() and assemble() stay untouched: CI calls them directly as
        # separate phases, and this subcommand must not change what they mean.
        bound = bind_observed_predecessor(
            plan, observed_commit, observed_name, observed_version
        )
        bound_plan = scratch / "publication-plan.bound.json"
        bound_plan.write_text(
            json.dumps(bound, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        # Materialise the publishable projection for each generated unit the
        # BOUND plan declares, inside this run's scratch directory -- so a run
        # still leaves only the bundle behind.  A plan without generated units
        # projects nothing and keeps the previous behaviour and cost exactly.
        generated_worktree = [
            f"{uid(unit.get('id'))}="
            f"{project_generated_worktree(sha, destination, scratch / 'generated' / uid(unit.get('id')))}"
            for unit in bound["publication_units"]
            if isinstance(unit, dict) and unit.get("kind") == "generated_commit"
        ]
        capture(
            argparse.Namespace(
                channel=a.channel,
                source_repo=str(repo_root),
                source_sha=sha,
                candidate_wheel=str(wheel),
                publication_plan=str(bound_plan),
                output=str(prepared),
                generated_worktree=generated_worktree,
                # The candidate build leaves its offline wheelhouse beside the
                # wheel it returns; carry it, so the retained wheel reaches the
                # downstream installed-smoke step with the `requirements.lock`
                # that step refuses without.  `copy_wheelhouse` owns the
                # refusal when it is missing or malformed.
                candidate_wheelhouse=str(wheel.parent / "offline-wheelhouse"),
            )
        )
        assemble(
            argparse.Namespace(
                prepared=str(prepared / "prepared-release.json"),
                migration=str(migration_path),
                output=str(output),
            )
        )
        # Validate the EMITTED zip, not only what was staged: the zip is the
        # artifact the workflow actually replays.
        extracted = scratch / "emitted"
        extracted.mkdir()
        with zipfile.ZipFile(output) as bundle:
            for member in bundle.infolist():
                relative = Path(member.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    refuse("emitted bundle carries an unsafe member")
            bundle.extractall(extracted)
        record = extracted / "decision.json"
        if not record.is_file() or record.is_symlink():
            refuse("emitted bundle has no decision.json")
        try:
            decision = decode_decision(record, repo_root)
        except DecisionRefusal as error:
            refuse(f"emitted bundle failed local decode_decision: {error}")
        if (
            decision.candidate.source_sha,
            decision.candidate.name,
            decision.candidate.version,
        ) != (expected.source_sha, expected.name, expected.version):
            refuse("emitted bundle candidate does not match this projected source")
        # Verify the binding with the PUBLISHER'S OWN gate, over the DECODED
        # emitted bundle -- the identical call the publisher makes before it
        # publishes.  The benefit is then a checked property of the artifact.
        from scripts.release.publish_experimental import (
            TARGET_BRANCH,
            _branch_publication_unit,
        )

        try:
            branch_unit = _branch_publication_unit(decision, TARGET_BRANCH)
            validate_predecessor_metadata(
                observed_commit,
                observed_pyproject,
                decision,
                branch_unit.body["predecessor"],
            )
        except DecisionRefusal as error:
            refuse(
                f"emitted bundle failed the publisher's predecessor gate against "
                f"{destination_label}: {error}"
            )
        # Read the review facts off the DECODED EMITTED bundle, so the operator
        # line states a property of the artifact and never an intention.
        review_line = None
        for unit in decision.units:
            if unit.kind == "generated_commit":
                name = uid(unit.body.get("id"))
                review_line = (
                    f"REVIEW: {name} tree {unit.body.get('tree_oid')} on "
                    f"{unit.body.get('parent_oid')} -- generated/{name}/tree.tar, "
                    f"generated/{name}/changes.patch"
                )
        emitted_digest = hashlib.sha256(record.read_bytes()).hexdigest()
    except BaseException:
        if not existed_before:
            output.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    print(f"CANDIDATE: {expected.name} {expected.version} @ {sha}")
    print(f"PREDECESSOR: {observed_name} {observed_version} @ {observed_commit}")
    print(f"DESTINATION: {destination_label} (observed read-only; nothing written)")
    if review_line is not None:
        print(review_line)
    print(f"BUNDLE: {output}")
    print(f"DECISION-SHA256: {emitted_digest}")
    print("VALIDATED: decode_decision accepted the emitted bundle for this exact sha")
    print(
        "VALIDATED-PREDECESSOR: the publisher's own predecessor gate accepts this "
        "bundle against the observed destination"
    )
    # State the honesty boundary as OUTPUT: this run resolved every dependency
    # from an already-installed environment, unlike the workflow's fresh CI
    # install, so a local green is not proof the publish workflow completes.
    print(
        "LOCAL-SCOPE: this run validated locally with every dependency already "
        "installed and does not prove the publish workflow (fresh install on CI "
        "runners) will complete"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="command", required=True)
    c = s.add_parser("capture-review-input")
    for n in (
        "channel",
        "source_repo",
        "source_sha",
        "candidate_wheel",
        "publication_plan",
        "output",
    ):
        c.add_argument("--" + n.replace("_", "-"), required=True)
    c.add_argument("--generated-worktree", action="append", default=[])
    c.add_argument(
        "--candidate-wheelhouse",
        default=None,
        help="Directory beside the wheel produced by offline_wheelhouse_hook.py "
        "(candidate wheels + requirements.lock); retained when a downstream "
        "consumer needs an offline, hash-pinned install (e.g. the OpenCode "
        "smoke). Omit when the caller does not require it.",
    )
    b = s.add_parser("assemble-decision-bundle")
    for n in ("prepared", "migration", "output"):
        b.add_argument("--" + n, required=True)
    d = s.add_parser("produce-decision-bundle")
    for n in ("channel", "source_sha", "publication_plan", "migration", "output"):
        d.add_argument("--" + n.replace("_", "-"), required=True)
    d.add_argument(
        "--target-local-repo",
        default=None,
        help="Existing local bare Git repository to observe as the published "
        "destination, named and meaning exactly as the publisher's own flag. "
        "Omit to observe the real public experimental target read-only.",
    )
    a = p.parse_args(argv)
    commands = {
        "capture-review-input": capture,
        "assemble-decision-bundle": assemble,
        "produce-decision-bundle": produce_decision_bundle,
    }
    try:
        return commands[a.command](a)
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
