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
    b = s.add_parser("assemble-decision-bundle")
    for n in ("prepared", "migration", "output"):
        b.add_argument("--" + n, required=True)
    a = p.parse_args(argv)
    try:
        return capture(a) if a.command == "capture-review-input" else assemble(a)
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
