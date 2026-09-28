#!/usr/bin/env python3
"""Fail-closed writer boundary for release migration decisions (v4)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlsplit, urlunsplit


if TYPE_CHECKING:
    from packaging.version import Version


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.release.discover_tag import (  # noqa: E402
    _is_dev_tag,
    _is_rc_tag,
    _parse_tag,
)
from scripts.release.experimental_migration_decision import (  # noqa: E402
    CHECKPOINTS,
    Candidate,
    Decision,
    DecisionRefusal,
    Predecessor,
    _reference,
    _validate_checkpoint,
    _wheel_metadata,
)


SCHEMA = "nwave.release-migration-decision.v4"
HEX = set("0123456789abcdef")
DATE = re.compile(r"^-?[0-9]+ [+-][0-9]{4}$")


def refusal(what: str, why: str, how: str) -> DecisionRefusal:
    return DecisionRefusal(f"REFUSAL: {what}. WHY: {why}. HOW: {how}.")


def _obj(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise refusal(name, "it is not an object", "supply the closed record shape")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise refusal(name, "it is empty", "supply a non-empty string")
    return value.strip()


def _sha(value: object, name: str) -> str:
    value = _text(value, name)
    if len(value) != 40 or any(c not in HEX for c in value):
        raise refusal(
            name, "it is not a full lowercase Git object id", "bind a full object id"
        )
    return value


def _digest(value: object, name: str) -> str:
    value = _text(value, name).removeprefix("sha256:")
    if len(value) != 64 or any(c not in HEX for c in value):
        raise refusal(name, "it is not lowercase SHA-256", "bind exact bytes")
    return value


def _closed(value: dict[str, Any], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise refusal(
            name,
            "fields are incomplete or unsupported",
            "supply the supported closed payload",
        )


def _git(
    repo: Path,
    args: list[str],
    *,
    input: bytes | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        stdin=subprocess.DEVNULL if input is None else None,
        input=input,
        capture_output=True,
        check=False,
        timeout=60,
        env=env,
    )


def _run(
    args: list[str], *, input: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        stdin=subprocess.DEVNULL if input is None else None,
        input=input,
        capture_output=True,
        check=False,
        timeout=90,
    )


def _indeterminate(
    what: str, result: subprocess.CompletedProcess[bytes]
) -> RuntimeError:
    detail = result.stderr.decode(errors="replace").strip()
    return RuntimeError(
        f"Indeterminate: {what} unavailable" + (f": {detail}" if detail else "")
    )


def _object(repo: Path, oid: str, what: str, suffix: str = "") -> None:
    if _git(repo, ["cat-file", "-e", oid + suffix]).returncode:
        raise refusal(
            what,
            "bound object is absent from selected repository",
            "select the repository containing it",
        )


@dataclass(frozen=True)
class GeneratedCommitSpec:
    unit_id: str
    original_source_sha: str
    tree_oid: str
    parent_oid: str
    author_name: str
    author_email: str
    author_date: str
    committer_name: str
    committer_email: str
    committer_date: str
    message_template: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class GeneratedCommitRef:
    producer_unit: str
    commit_oid: str
    spec_sha256: str
    decision_sha256: str

    def wire(self) -> dict[str, str]:
        return {
            "kind": "generated-commit-ref-v1",
            "producer_unit": self.producer_unit,
            "commit_oid": self.commit_oid,
            "spec_sha256": self.spec_sha256,
            "decision_sha256": self.decision_sha256,
        }


@dataclass(frozen=True)
class PublicationExpectation:
    unit_id: str
    kind: str
    body: dict[str, Any]


@dataclass(frozen=True)
class InvocationDecision:
    raw: bytes
    root: Path
    repo: Path
    channel: str
    candidate: Candidate
    predecessor: MigrationPredecessor | None
    migration: dict[str, Any]
    units: tuple[PublicationExpectation, ...]
    specs: dict[str, GeneratedCommitSpec]

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    def unit(self, uid: str) -> PublicationExpectation:
        for unit in self.units:
            if unit.unit_id == uid:
                return unit
        raise refusal(
            "publication unit", "selected id is not declared", "select a declared unit"
        )


@dataclass(frozen=True)
class MigrationPredecessor:
    distribution_name: str
    version: str


def _validate_required(migration: dict[str, Any], decision: InvocationDecision) -> None:
    source, wheel = (
        _obj(migration["source_locator"], "migration.source_locator"),
        _obj(migration["wheel_locator"], "migration.wheel_locator"),
    )
    if set(source) != {"repo_path"} or set(wheel) != {"archive_member"}:
        raise refusal(
            "migration locators",
            "they are not exact locators",
            "bind repo_path and archive_member",
        )
    path, member = (
        _text(source["repo_path"], "source_locator.repo_path"),
        _text(wheel["archive_member"], "wheel_locator.archive_member"),
    )
    shown = _git(decision.repo, ["show", f"{decision.candidate.source_sha}:{path}"])
    if shown.returncode:
        raise refusal(
            "migration source",
            "locator is absent at candidate source",
            "bind an existing candidate file",
        )
    try:
        with zipfile.ZipFile(
            decision.root / decision.candidate.wheel["file"]
        ) as archive:
            offered = archive.read(member)
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise refusal(
            "migration wheel member", str(error), "bind an actual retained member"
        ) from error
    if shown.stdout != offered:
        raise refusal(
            "migration mapping",
            "source bytes differ from wheel member",
            "bind same-bytes source-to-wheel mapping",
        )
    proof = _obj(migration["upgrade_proof"], "migration.upgrade_proof")
    if (
        set(proof) != {"kind", "record", "checkpoints"}
        or proof.get("kind") != "public-distribution-upgrade-v1"
    ):
        raise refusal(
            "upgrade proof",
            "kind is unsupported",
            "retain public-distribution-upgrade-v1",
        )
    proof_path, _ = _reference(proof["record"], decision.root, "upgrade proof record")
    try:
        value = _obj(
            json.loads(proof_path.read_text(encoding="utf-8")), "upgrade proof record"
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise refusal("upgrade proof", str(error), "retain valid proof JSON") from error
    candidate = {
        "source_sha": decision.candidate.source_sha,
        "name": decision.candidate.name,
        "version": decision.candidate.version,
        "wheel": decision.candidate.wheel,
    }
    if decision.predecessor is None:
        raise refusal(
            "required migration",
            "initial publication has no supported predecessor",
            "use required false",
        )
    predecessor = {
        "name": decision.predecessor.distribution_name,
        "version": decision.predecessor.version,
    }
    checkpoints = _obj(proof["checkpoints"], "upgrade proof checkpoints")
    if (
        value.get("kind") != "public-distribution-upgrade-v1"
        or value.get("candidate") != candidate
        or value.get("predecessor") != predecessor
        or set(checkpoints) != set(CHECKPOINTS)
        or value.get("checkpoints") != checkpoints
    ):
        raise refusal(
            "upgrade proof",
            "candidate, predecessor, or checkpoints differ",
            "retain all exact proof bindings",
        )
    # Reuse the v2 semantic proof checker through its actual typed Decision.
    v2 = Decision(
        decision.raw,
        decision.root,
        decision.candidate,
        Predecessor(
            "", decision.predecessor.distribution_name, decision.predecessor.version
        ),
        decision.migration,
    )
    for name in CHECKPOINTS:
        checkpoint, _ = _reference(
            checkpoints[name], decision.root, f"upgrade checkpoint {name}"
        )
        _validate_checkpoint(checkpoint, name, v2)


def _target_shape(
    value: object, specs: dict[str, GeneratedCommitSpec], name: str
) -> None:
    if isinstance(value, str):
        _sha(value, name)
        return
    value = _obj(value, name)
    if (
        set(value) != {"kind", "producer_unit"}
        or value.get("kind") != "generated-commit"
        or _text(value.get("producer_unit"), f"{name}.producer_unit") not in specs
    ):
        raise refusal(
            name,
            "not a declared generated target",
            "bind a declared generated producer",
        )


def _publication_predecessor(value: object, name: str) -> dict[str, object] | None:
    if value is None:
        return None
    item = _obj(value, name)
    _closed(item, {"release_id", "tag", "version", "target_sha"}, name)
    if not isinstance(item["release_id"], int) or item["release_id"] <= 0:
        raise refusal(
            name, "release_id is not positive", "bind observed release identity"
        )
    _text(item["tag"], f"{name}.tag")
    _text(item["version"], f"{name}.version")
    _sha(item["target_sha"], f"{name}.target_sha")
    return item


def _unit(unit: PublicationExpectation, specs: dict[str, GeneratedCommitSpec]) -> None:
    b, common = unit.body, {"id", "kind"}
    if unit.kind == "git_branch":
        _closed(b, common | {"branch", "remote", "predecessor", "target"}, "git branch")
        _text(b["branch"], "branch")
        _text(b["remote"], "remote")
        _sha(b["predecessor"], "branch predecessor")
        _target_shape(b["target"], specs, "branch target")
    elif unit.kind == "git_tag":
        _closed(
            b,
            common
            | {"repository", "tag", "remote", "target", "publication_predecessor"},
            "git tag",
        )
        _text(b["repository"], "repository")
        _text(b["tag"], "tag")
        _text(b["remote"], "remote")
        _target_shape(b["target"], specs, "tag target")
        _publication_predecessor(
            b["publication_predecessor"], "tag publication predecessor"
        )
    elif unit.kind == "github_release_metadata":
        _closed(
            b,
            common
            | {
                "repository",
                "tag",
                "target",
                "title",
                "notes",
                "notes_sha256",
                "prerelease",
                "publication_predecessor",
            },
            "GitHub release metadata",
        )
        for x in ("repository", "tag", "title"):
            _text(b[x], x)
        _target_shape(b["target"], specs, "release target")
        _digest(b["notes_sha256"], "notes sha256")
        if not isinstance(b["prerelease"], bool):
            raise refusal(
                "release prerelease", "it is not boolean", "bind release state"
            )
        _publication_predecessor(
            b["publication_predecessor"], "release publication predecessor"
        )
    elif unit.kind == "github_release_asset":
        _closed(
            b,
            common | {"release_unit", "file", "sha256", "size"},
            "GitHub release asset",
        )
        _text(b["release_unit"], "release_unit")
        _text(b["file"], "asset file")
        _digest(b["sha256"], "asset sha256")
        if not isinstance(b["size"], int) or b["size"] < 0:
            raise refusal("asset size", "it is invalid", "bind exact bytes")
    elif unit.kind == "package_index_upload":
        _closed(
            b,
            common
            | {
                "repository",
                "endpoint",
                "file",
                "sha256",
                "size",
                "publication_predecessor_version",
            },
            "package upload",
        )
        for x in ("repository", "endpoint", "file"):
            _text(b[x], x)
        if not b["endpoint"].startswith(("https://", "http://")):
            raise refusal(
                "package endpoint", "it is not HTTP", "bind the JSON endpoint"
            )
        _digest(b["sha256"], "package sha256")
        if not isinstance(b["size"], int) or b["size"] < 0:
            raise refusal("package size", "it is invalid", "bind exact bytes")
        if b["publication_predecessor_version"] is not None:
            _text(b["publication_predecessor_version"], "package predecessor version")
    elif unit.kind == "workflow_dispatch":
        _closed(
            b,
            common
            | {
                "repository",
                "workflow",
                "ref",
                "source_sha",
                "downstream_channel",
                "downstream_decision_sha256",
                "downstream_decision_handle",
                "downstream_source_sha",
            },
            "workflow dispatch",
        )
        for x in (
            "repository",
            "workflow",
            "ref",
            "downstream_channel",
            "downstream_decision_handle",
        ):
            _text(b[x], x)
        if _sha(b["source_sha"], "workflow source") != _sha(
            b["downstream_source_sha"], "child source"
        ):
            raise refusal(
                "workflow dispatch",
                "source fields disagree",
                "bind one selected source",
            )
        _digest(b["downstream_decision_sha256"], "child decision digest")
    else:
        raise refusal(
            "publication unit", "kind is unsupported", "use a supported writer unit"
        )


def decode_decision(path: Path, repo_root: Path = ROOT) -> InvocationDecision:
    try:
        raw = path.read_bytes()
        record = _obj(json.loads(raw), "decision")
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DecisionRefusal,
    ) as error:
        if isinstance(error, DecisionRefusal):
            raise
        raise refusal("decision", str(error), "supply retained valid JSON") from error
    if (
        set(record)
        != {
            "schema",
            "channel",
            "candidate",
            "predecessor",
            "migration",
            "publication_units",
        }
        or record.get("schema") != SCHEMA
    ):
        raise refusal(
            "decision",
            "schema or fields unsupported",
            "use release-migration-decision.v4",
        )
    root, repo = path.parent.resolve(), repo_root.resolve()
    c = _obj(record["candidate"], "candidate")
    _closed(c, {"source_sha", "name", "version", "wheel"}, "candidate")
    wheel, wheel_ref = _reference(c["wheel"], root, "candidate.wheel")
    candidate = Candidate(
        _sha(c["source_sha"], "candidate.source_sha"),
        _text(c["name"], "candidate.name"),
        _text(c["version"], "candidate.version"),
        wheel_ref,
    )
    _object(repo, candidate.source_sha, "candidate source")
    md = _wheel_metadata(wheel)
    if (md.get("Name"), md.get("Version")) != (candidate.name, candidate.version):
        raise refusal(
            "candidate wheel", "metadata differs", "retain exact candidate wheel"
        )
    p = record["predecessor"]
    predecessor = (
        None
        if p is None
        else MigrationPredecessor(
            _text(_obj(p, "predecessor").get("distribution_name"), "predecessor name"),
            _text(_obj(p, "predecessor").get("version"), "predecessor version"),
        )
    )
    if p is not None:
        _closed(_obj(p, "predecessor"), {"distribution_name", "version"}, "predecessor")
    migration = _obj(record["migration"], "migration")
    base = {"required", "compatibility_boundary", "evidence"}
    if not isinstance(migration.get("required"), bool):
        raise refusal("migration", "required is not boolean", "bind migration choice")
    _text(migration.get("compatibility_boundary"), "migration boundary")
    evidence = migration.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise refusal(
            "migration evidence", "it is empty", "retain compatibility evidence"
        )
    for i, item in enumerate(evidence):
        _reference(item, root, f"migration.evidence[{i}]")
    if migration["required"]:
        _closed(
            migration,
            base | {"path", "source_locator", "wheel_locator", "upgrade_proof"},
            "required migration",
        )
        if _text(migration["path"], "migration.path") != _text(
            _obj(migration["source_locator"], "source locator").get("repo_path"),
            "source locator path",
        ):
            raise refusal(
                "migration path",
                "legacy path and locator differ",
                "bind the same source path",
            )
    else:
        _closed(migration, base, "compatible migration")
    raw_units = record["publication_units"]
    if not isinstance(raw_units, list) or not raw_units:
        raise refusal("publication units", "they are empty", "bind writer units")
    units: list[PublicationExpectation] = []
    specs: dict[str, GeneratedCommitSpec] = {}
    ids: set[str] = set()
    for raw_unit in raw_units:
        b = _obj(raw_unit, "publication unit")
        uid, kind = _text(b.get("id"), "unit id"), _text(b.get("kind"), "unit kind")
        if uid in ids:
            raise refusal("publication unit", "id is duplicated", "use unique ids")
        ids.add(uid)
        if kind == "generated_commit":
            fields = {
                "id",
                "kind",
                "original_source_sha",
                "tree_oid",
                "parent_oid",
                "author_name",
                "author_email",
                "author_date",
                "committer_name",
                "committer_email",
                "committer_date",
                "message_template",
            }
            _closed(b, fields, "generated commit")
            message = b["message_template"]
            if (
                not isinstance(message, str)
                or "\r" in message
                or not message.endswith("\n")
                or message.count("{decision_sha256}") != 1
            ):
                raise refusal(
                    "generated message",
                    "template is not canonical",
                    "use one placeholder and trailing LF",
                )
            spec = GeneratedCommitSpec(
                uid,
                _sha(b["original_source_sha"], "original source"),
                _sha(b["tree_oid"], "tree"),
                _sha(b["parent_oid"], "parent"),
                *[
                    _text(b[x], x)
                    for x in (
                        "author_name",
                        "author_email",
                        "author_date",
                        "committer_name",
                        "committer_email",
                        "committer_date",
                    )
                ],
                message,
            )
            if spec.original_source_sha != candidate.source_sha:
                raise refusal(
                    "generated commit",
                    "original source differs from candidate",
                    "preserve promotion source",
                )
            if not DATE.match(spec.author_date) or not DATE.match(spec.committer_date):
                raise refusal(
                    "generated dates",
                    "they are not canonical Git dates",
                    "bind '<seconds> <+/-HHMM>'",
                )
            if any(
                "\n" in x or "\r" in x
                for x in (
                    spec.author_name,
                    spec.author_email,
                    spec.committer_name,
                    spec.committer_email,
                )
            ):
                raise refusal(
                    "generated identity",
                    "it contains a line break",
                    "bind single-line identities",
                )
            specs[uid] = spec
        elif kind not in {
            "git_branch",
            "git_tag",
            "github_release_metadata",
            "github_release_asset",
            "package_index_upload",
            "workflow_dispatch",
        }:
            raise refusal("publication unit", "kind is unknown", "use supported kind")
        units.append(PublicationExpectation(uid, kind, b))
    decision = InvocationDecision(
        raw,
        root,
        repo,
        _text(record["channel"], "channel"),
        candidate,
        predecessor,
        migration,
        tuple(units),
        specs,
    )
    for unit in units:
        if unit.kind != "generated_commit":
            _unit(unit, specs)
        if unit.kind == "github_release_metadata":
            _reference(unit.body["notes"], root, "release notes")
        if (
            unit.kind == "github_release_asset"
            and decision.unit(_text(unit.body["release_unit"], "release unit")).kind
            != "github_release_metadata"
        ):
            raise refusal(
                "release asset", "release unit is not metadata", "bind metadata unit"
            )
        if unit.kind in {
            "git_branch",
            "git_tag",
            "github_release_metadata",
        } and isinstance(unit.body.get("target"), str):
            target = _sha(unit.body["target"], "destination target")
            if target != candidate.source_sha:
                raise refusal(
                    "destination target",
                    "plain target is unrelated to candidate source",
                    "use candidate source or a declared generated commit",
                )
            _object(repo, target, "destination target", "^{commit}")
    if predecessor is None:
        if migration["required"]:
            raise refusal(
                "initial migration",
                "required migration has no predecessor",
                "use required false",
            )
    if migration["required"]:
        _validate_required(migration, decision)
    return decision


def _commit_bytes(spec: GeneratedCommitSpec, digest: str) -> bytes:
    return (
        f"tree {spec.tree_oid}\nparent {spec.parent_oid}\nauthor {spec.author_name} <{spec.author_email}> {spec.author_date}\ncommitter {spec.committer_name} <{spec.committer_email}> {spec.committer_date}\n\n".encode()
        + spec.message_template.format(decision_sha256=digest).encode()
    )


def _expected_oid(spec: GeneratedCommitSpec, digest: str) -> str:
    body = _commit_bytes(spec, digest)
    return hashlib.sha1(b"commit " + str(len(body)).encode() + b"\0" + body).hexdigest()


def _git_date(value: str) -> str:
    """Adapt the decision's canonical Git date to git's environment syntax."""
    return f"@{value}"


def _verify_generated(
    decision: InvocationDecision, producer: str, oid: str, object_repo: Path
) -> str:
    spec = decision.specs.get(producer)
    if spec is None or oid != _expected_oid(spec, decision.digest):
        raise refusal(
            "generated reference",
            "oid is not derived from bound spec and decision",
            "regenerate exact commit",
        )
    actual = _git(object_repo, ["cat-file", "commit", oid])
    if actual.returncode or actual.stdout != _commit_bytes(spec, decision.digest):
        raise refusal(
            "generated reference",
            "actual commit object differs or is absent",
            "prepare exact object in selected target repository",
        )
    return oid


def _refs(
    paths: list[str], decision: InvocationDecision, object_repo: Path
) -> dict[str, GeneratedCommitRef]:
    result: dict[str, GeneratedCommitRef] = {}
    for path in paths:
        try:
            value = _obj(
                json.loads(Path(path).read_text(encoding="utf-8")),
                "generated reference",
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise refusal(
                "generated reference", str(error), "supply prepare output"
            ) from error
        _closed(
            value,
            {"kind", "producer_unit", "commit_oid", "spec_sha256", "decision_sha256"},
            "generated reference",
        )
        producer = _text(value.get("producer_unit"), "generated producer")
        if (
            value.get("kind") != "generated-commit-ref-v1"
            or producer not in decision.specs
            or producer in result
        ):
            raise refusal(
                "generated reference",
                "kind or producer is invalid",
                "supply one declared producer ref",
            )
        ref = GeneratedCommitRef(
            producer,
            _sha(value["commit_oid"], "commit oid"),
            _digest(value["spec_sha256"], "spec digest"),
            _digest(value["decision_sha256"], "decision digest"),
        )
        if (
            ref.spec_sha256 != decision.specs[producer].digest
            or ref.decision_sha256 != decision.digest
        ):
            raise refusal(
                "generated reference", "digest binding differs", "regenerate reference"
            )
        _verify_generated(decision, producer, ref.commit_oid, object_repo)
        result[producer] = ref
    return result


def _target(
    decision: InvocationDecision,
    unit: PublicationExpectation,
    refs: dict[str, GeneratedCommitRef],
    object_repo: Path,
) -> str:
    target = unit.body["target"]
    if isinstance(target, str):
        _object(object_repo, _sha(target, "target"), "target", "^{commit}")
        return target
    producer = _text(_obj(target, "target").get("producer_unit"), "generated producer")
    return _verify_generated(
        decision,
        producer,
        refs[producer].commit_oid
        if producer in refs
        else _expected_oid(decision.specs[producer], decision.digest),
        object_repo,
    )


def _snapshot_target(decision: InvocationDecision, unit: PublicationExpectation) -> str:
    target = unit.body["target"]
    if isinstance(target, str):
        return _sha(target, "snapshot target")
    producer = _text(
        _obj(target, "snapshot target").get("producer_unit"), "generated producer"
    )
    spec = decision.specs.get(producer)
    if spec is None:
        raise refusal(
            "snapshot target",
            "generated producer is undeclared",
            "bind a declared producer",
        )
    return _expected_oid(spec, decision.digest)


def prepare_generated_commit(
    decision: InvocationDecision, uid: str, worktree: Path
) -> GeneratedCommitRef:
    spec = decision.specs.get(uid)
    if spec is None:
        raise refusal(
            "generated commit", "unit is not generated", "select generated_commit"
        )
    _object(worktree, spec.parent_oid, "generated parent", "^{commit}")
    _object(worktree, spec.tree_oid, "generated tree")
    tree = _git(worktree, ["write-tree"])
    if tree.returncode or tree.stdout.decode(errors="replace").strip() != spec.tree_oid:
        raise refusal("generated tree", "worktree differs", "prepare bound tree")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": spec.author_name,
        "GIT_AUTHOR_EMAIL": spec.author_email,
        "GIT_AUTHOR_DATE": _git_date(spec.author_date),
        "GIT_COMMITTER_NAME": spec.committer_name,
        "GIT_COMMITTER_EMAIL": spec.committer_email,
        "GIT_COMMITTER_DATE": _git_date(spec.committer_date),
    }
    message = spec.message_template.format(decision_sha256=decision.digest).encode()
    made = _git(
        worktree,
        ["commit-tree", spec.tree_oid, "-p", spec.parent_oid],
        input=message,
        env=env,
    )
    if made.returncode:
        raise refusal(
            "generated commit",
            "commit-tree failed",
            made.stderr.decode(errors="replace"),
        )
    oid = _sha(made.stdout.decode().strip(), "generated oid")
    _verify_generated(decision, uid, oid, worktree)
    return GeneratedCommitRef(uid, oid, spec.digest, decision.digest)


def _not_found(result: subprocess.CompletedProcess[bytes]) -> bool:
    return b"not found" in (result.stdout + result.stderr).lower()


def _gh_release(repo: str, tag: str) -> dict[str, Any] | None:
    result = _run(["gh", "api", "--method", "GET", f"repos/{repo}/releases/tags/{tag}"])
    if result.returncode:
        if _not_found(result):
            return None
        raise _indeterminate("GitHub release observer", result)
    try:
        return _obj(json.loads(result.stdout), "GitHub release")
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError(
            f"Indeterminate: unreadable GitHub release: {error}"
        ) from error


def _channel_release_version(
    channel: str, tag: str, prerelease: bool
) -> Version | None:
    """Return the channel-qualified version using discover_tag's tag policy."""
    version = _parse_tag(tag)
    if version is None:
        return None
    if channel == "dev":
        return version if prerelease and _is_dev_tag(version) else None
    if channel in {"rc", "github-prerelease"}:
        return version if prerelease and _is_rc_tag(version) else None
    if channel == "stable":
        return version if not prerelease and not version.is_prerelease else None
    raise refusal(
        "channel", "has no GitHub release version policy", "use a release channel"
    )


def _gh_channel_predecessor(repo: str, channel: str) -> dict[str, object] | None:
    """Observe the highest qualifying GitHub release and peel its remote tag.

    ``--slurp`` preserves page boundaries. Treat anything other than an array
    of arrays as unavailable so a partial page cannot authorize publication.
    """
    result = _run(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "--method",
            "GET",
            f"repos/{repo}/releases?per_page=100",
        ]
    )
    if result.returncode:
        raise _indeterminate("GitHub release history observer", result)
    try:
        pages = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError(
            f"Indeterminate: unreadable GitHub release history: {error}"
        ) from error
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise RuntimeError("Indeterminate: incomplete GitHub release pagination")
    candidates: list[tuple[Version, dict[str, object]]] = []
    for page in pages:
        for raw in page:
            try:
                release = _obj(raw, "GitHub history release")
                release_id = release.get("id")
                if not isinstance(release_id, int) or release_id <= 0:
                    raise refusal(
                        "GitHub history release id",
                        "it is not positive",
                        "observe a complete release record",
                    )
                tag = _text(release.get("tag_name"), "GitHub history tag")
                prerelease = release.get("prerelease")
                draft = release.get("draft")
                if not isinstance(prerelease, bool) or not isinstance(draft, bool):
                    raise refusal(
                        "GitHub history release state",
                        "prerelease or draft is not boolean",
                        "observe a complete release record",
                    )
            except DecisionRefusal as error:
                raise RuntimeError(
                    f"Indeterminate: malformed GitHub release history: {error}"
                ) from error
            version = (
                None if draft else _channel_release_version(channel, tag, prerelease)
            )
            if version is not None:
                candidates.append(
                    (
                        version,
                        {
                            "release_id": release_id,
                            "tag": tag,
                            "version": str(version),
                            "prerelease": prerelease,
                        },
                    )
                )
    if not candidates:
        return None
    highest = max(version for version, _ in candidates)
    selected = [item for version, item in candidates if version == highest]
    if len(selected) != 1:
        raise RuntimeError(
            "Indeterminate: GitHub release history has duplicate highest versions"
        )
    predecessor = selected[0]
    target = _gh_tag(repo, _text(predecessor["tag"], "GitHub predecessor tag"))
    if target is None:
        raise RuntimeError("Indeterminate: GitHub predecessor tag is absent")
    return {**predecessor, "target_sha": target}


def _require_live_predecessor(d: InvocationDecision, u: PublicationExpectation) -> None:
    """Require this destination's retained predecessor to equal live history."""
    b = u.body
    live = _gh_channel_predecessor(_text(b["repository"], "repository"), d.channel)
    declared = _publication_predecessor(
        b["publication_predecessor"], "publication predecessor"
    )
    if live is None:
        if declared is not None:
            raise refusal(
                "publication predecessor",
                "live qualifying GitHub history is empty",
                "bind null only for an initial publication",
            )
        return
    live_binding = {
        key: live[key] for key in ("release_id", "tag", "version", "target_sha")
    }
    if declared != live_binding:
        raise refusal(
            "publication predecessor",
            "declared record differs from the live channel predecessor",
            "recreate the decision from the observed release",
        )


def _gh_tag(repo: str, tag: str) -> str | None:
    result = _run(["gh", "api", "--method", "GET", f"repos/{repo}/git/ref/tags/{tag}"])
    if result.returncode:
        if _not_found(result):
            return None
        raise _indeterminate("GitHub tag observer", result)
    try:
        obj = _obj(
            _obj(json.loads(result.stdout), "GitHub tag").get("object"),
            "GitHub tag object",
        )
        typ, oid = _text(obj.get("type"), "tag type"), _sha(obj.get("sha"), "tag sha")
    except (json.JSONDecodeError, TypeError, DecisionRefusal) as error:
        raise RuntimeError(f"Indeterminate: unreadable GitHub tag: {error}") from error
    for _ in range(16):
        if typ == "commit":
            return oid
        if typ != "tag":
            raise RuntimeError("Indeterminate: GitHub tag has unsupported target")
        peeled = _run(["gh", "api", "--method", "GET", f"repos/{repo}/git/tags/{oid}"])
        if peeled.returncode:
            raise _indeterminate("GitHub annotated tag observer", peeled)
        try:
            nested = _obj(
                _obj(json.loads(peeled.stdout), "annotated tag").get("object"),
                "annotated target",
            )
            typ = _text(nested.get("type"), "annotated target type")
            oid = _sha(nested.get("sha"), "peeled target")
        except (json.JSONDecodeError, TypeError, DecisionRefusal) as error:
            raise RuntimeError(
                f"Indeterminate: unreadable annotated tag: {error}"
            ) from error
    raise RuntimeError("Indeterminate: annotated GitHub tag peel is too deep")


def _notes(decision: InvocationDecision, unit: PublicationExpectation) -> str:
    path, ref = _reference(unit.body["notes"], decision.root, "release notes")
    if _digest(unit.body["notes_sha256"], "notes sha256") != ref["sha256"]:
        raise refusal("release notes", "digest differs", "bind retained notes")
    try:
        return (
            path.read_text(encoding="utf-8")
            + f"\nMigration decision SHA-256: {decision.digest}\n"
        )
    except (OSError, UnicodeDecodeError) as error:
        raise refusal("release notes", str(error), "retain UTF-8 notes") from error


def _release_exact(
    d: InvocationDecision, u: PublicationExpectation, r: dict[str, Any], target: str
) -> bool:
    b = u.body
    return (
        r.get("tag_name") == b["tag"]
        and r.get("target_commitish") == target
        and r.get("name") == b["title"]
        and r.get("body") == _notes(d, u)
        and r.get("prerelease") == b["prerelease"]
    )


def _asset_file(d: InvocationDecision, u: PublicationExpectation, root: Path) -> Path:
    root = root.resolve()
    path = (root / _text(u.body["file"], "asset file")).resolve()
    if root not in path.parents or not path.is_file():
        raise refusal(
            "asset", "file is absent below artifact root", "offer retained candidate"
        )
    digest = _digest(u.body["sha256"], "asset sha256")
    if (
        path.stat().st_size != u.body["size"]
        or hashlib.sha256(path.read_bytes()).hexdigest() != digest
    ):
        raise refusal(
            "asset",
            "bytes differ from its declared immutable asset",
            "offer the decision-bound file",
        )
    if (
        path.name == Path(d.candidate.wheel["file"]).name
        and digest != d.candidate.wheel["sha256"]
    ):
        raise refusal(
            "candidate wheel asset",
            "bytes differ from the exact candidate wheel",
            "offer the retained candidate wheel",
        )
    return path


def _asset_digest(repo: str, asset: dict[str, Any]) -> str | None:
    value = asset.get("digest")
    if isinstance(value, str) and value.startswith("sha256:"):
        try:
            return _digest(value, "GitHub asset digest")
        except DecisionRefusal:
            return None
    # GitHub may omit digest: bounded real download is required, otherwise unknown.
    if not isinstance(asset.get("id"), int):
        return None
    result = _run(
        [
            "gh",
            "api",
            "--method",
            "GET",
            "-H",
            "Accept: application/octet-stream",
            f"repos/{repo}/releases/assets/{asset['id']}",
        ]
    )
    return hashlib.sha256(result.stdout).hexdigest() if not result.returncode else None


def _assets(
    d: InvocationDecision,
    release: PublicationExpectation,
    state: dict[str, Any],
    root: Path,
    *,
    download: bool = True,
) -> tuple[str, dict[str, tuple[PublicationExpectation, Path]]]:
    declared: dict[str, tuple[PublicationExpectation, Path]] = {}
    for unit in d.units:
        if (
            unit.kind == "github_release_asset"
            and unit.body["release_unit"] == release.unit_id
        ):
            path = _asset_file(d, unit, root)
            if path.name in declared:
                raise refusal(
                    "release assets",
                    "duplicate declared name",
                    "use one unit per immutable name",
                )
            declared[path.name] = (unit, path)
    if not declared:
        raise refusal(
            "release assets",
            "metadata has no declared assets",
            "bind candidate asset units",
        )
    observed = state.get("assets")
    if not isinstance(observed, list):
        return "Unavailable", declared
    names: set[str] = set()
    for asset in observed:
        if (
            not isinstance(asset, dict)
            or not isinstance(asset.get("name"), str)
            or asset["name"] in names
            or asset["name"] not in declared
        ):
            return "Conflict", declared
        names.add(asset["name"])
        unit, path = declared[asset["name"]]
        digest = (
            _asset_digest(_text(release.body["repository"], "repository"), asset)
            if download
            else asset.get("digest", "").removeprefix("sha256:")
        )
        if digest is None:
            return "Unavailable", declared
        if asset.get("size") != path.stat().st_size or digest != _digest(
            unit.body["sha256"], "asset sha256"
        ):
            return "Conflict", declared
    return ("PublishedExact" if len(names) == len(declared) else "Pending"), declared


def _remote(repo: Path, remote: str, ref: str) -> str | None:
    result = _git(repo, ["ls-remote", remote, ref])
    if result.returncode:
        raise _indeterminate("Git remote observer", result)
    rows = result.stdout.decode(errors="replace").splitlines()
    if not rows:
        return None
    parts = rows[0].split()
    if len(parts) != 2:
        raise RuntimeError("Indeterminate: unreadable Git remote ref")
    return _sha(parts[0], "remote object")


def _tag_target(repo: Path, remote: str, tag: str) -> str | None:
    result = _git(
        repo, ["ls-remote", remote, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"]
    )
    if result.returncode:
        raise _indeterminate("Git tag observer", result)
    direct = peeled = None
    for row in result.stdout.decode(errors="replace").splitlines():
        parts = row.split()
        if len(parts) != 2:
            raise RuntimeError("Indeterminate: unreadable Git tag")
        if parts[1] == f"refs/tags/{tag}":
            direct = _sha(parts[0], "tag object")
        if parts[1] == f"refs/tags/{tag}^{{}}":
            peeled = _sha(parts[0], "peeled tag")
    return peeled or direct


def _index_endpoints(endpoint: str, distribution_name: str) -> tuple[str, str]:
    """Derive official Index and exact-version endpoints from the bound URL.

    Decisions retain a project JSON endpoint because it identifies the target
    index and project.  Project JSON's historic ``releases`` inventory is not
    used: the Simple API is the inventory, while the version JSON resource is
    used only for immutable files and their digests.
    """
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise refusal(
            "package endpoint",
            "it cannot identify an Index API project",
            "bind an HTTP PyPI or TestPyPI project JSON endpoint",
        )
    parts = [part for part in parsed.path.split("/") if part]
    if (
        len(parts) not in {3, 4}
        or parts[0] != "pypi"
        or parts[-1] != "json"
        or parts[1] != distribution_name
    ):
        raise refusal(
            "package endpoint",
            "it does not bind the candidate project JSON resource",
            "bind /pypi/<candidate-name>/json",
        )
    prefix = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    project = quote(distribution_name, safe="")
    return (
        f"{prefix}/simple/{project}/",
        f"{prefix}/pypi/{project}/{{version}}/json",
    )


def _index_json(url: str, what: str) -> dict[str, Any] | None:
    """Read a bounded public JSON resource; 404 is an observed absence."""
    try:
        request = urllib.request.Request(
            url, headers={"Accept": "application/vnd.pypi.simple.v1+json"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.headers.get_content_type() not in {
                "application/json",
                "application/vnd.pypi.simple.v1+json",
            }:
                raise RuntimeError(
                    "Indeterminate: package endpoint did not return JSON"
                )
            value = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(
            f"Indeterminate: package index unavailable: HTTP {error.code}"
        ) from error
    except (
        urllib.error.URLError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            f"Indeterminate: package index unavailable: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RuntimeError("Indeterminate: package JSON is not an object")
    return value


def _filename_identity(filename: str) -> tuple[str, Version] | None:
    """Parse one distribution filename without trusting a project JSON map."""
    try:
        from packaging.utils import parse_sdist_filename, parse_wheel_filename

        if filename.endswith(".whl"):
            name, version, _, _ = parse_wheel_filename(filename)
        else:
            name, version = parse_sdist_filename(filename)
        return name, version
    except (ImportError, ValueError):
        return None


def _same_distribution(observed: object, expected: str) -> bool:
    if not isinstance(observed, str):
        return False
    try:
        from packaging.utils import canonicalize_name

        return canonicalize_name(observed) == canonicalize_name(expected)
    except ImportError:
        return False


def _index_inventory(endpoint: str, distribution_name: str) -> list[dict[str, str]]:
    inventory_url, _ = _index_endpoints(endpoint, distribution_name)
    value = _index_json(inventory_url, "package inventory")
    if value is None:
        return []
    if not _same_distribution(value.get("name"), distribution_name):
        raise RuntimeError("Indeterminate: package Index API project identity differs")
    files = value.get("files")
    if not isinstance(files, list):
        raise RuntimeError("Indeterminate: package Index API lacks files")
    result: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise RuntimeError("Indeterminate: package Index API lacks filename")
        identity = _filename_identity(item["filename"])
        if identity is None:
            continue
        name, version = identity
        if not _same_distribution(name, distribution_name):
            raise RuntimeError(
                "Indeterminate: package Index API contains another project"
            )
        result.append({"filename": item["filename"], "version": str(version)})
    return result


def _index_version_files(
    endpoint: str, distribution_name: str, version: str
) -> list[dict[str, str]] | None:
    _, version_url = _index_endpoints(endpoint, distribution_name)
    value = _index_json(
        version_url.format(version=quote(version, safe="")), "package version"
    )
    if value is None:
        return None
    info = value.get("info")
    if not isinstance(info, dict) or not _same_distribution(
        info.get("name"), distribution_name
    ):
        raise RuntimeError("Indeterminate: package version JSON lacks identity")
    try:
        from packaging.version import Version as PackagingVersion

        expected_version = PackagingVersion(version)
        if (
            PackagingVersion(_text(info.get("version"), "package version"))
            != expected_version
        ):
            raise RuntimeError("Indeterminate: package version JSON identity differs")
    except ImportError as error:
        raise RuntimeError(
            "Indeterminate: packaging version parser is unavailable"
        ) from error
    files = value.get("urls")
    if not isinstance(files, list):
        raise RuntimeError("Indeterminate: package version JSON lacks files")
    result: list[dict[str, str]] = []
    for item in files:
        hashes = item.get("digests") if isinstance(item, dict) else None
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("filename"), str)
            or not isinstance(hashes, dict)
            or not isinstance(hashes.get("sha256"), str)
        ):
            raise RuntimeError(
                "Indeterminate: package version JSON lacks filename/hash"
            )
        identity = _filename_identity(item["filename"])
        if (
            identity is None
            or not _same_distribution(identity[0], distribution_name)
            or identity[1] != expected_version
        ):
            raise RuntimeError(
                "Indeterminate: package version JSON contains another version"
            )
        try:
            digest = _digest(hashes["sha256"], "package file sha256")
        except DecisionRefusal as error:
            raise RuntimeError(
                f"Indeterminate: package version JSON has invalid digest: {error}"
            ) from error
        result.append({"filename": item["filename"], "sha256": digest})
    return result


def _index_channel_predecessor(
    endpoint: str, distribution_name: str, channel: str
) -> str | None:
    try:
        from packaging.version import Version as PackagingVersion
    except ImportError as error:
        raise RuntimeError(
            "Indeterminate: packaging version parser is unavailable"
        ) from error
    versions: set[PackagingVersion] = set()
    for file in _index_inventory(endpoint, distribution_name):
        version = PackagingVersion(file["version"])
        qualifies = (
            channel == "rc"
            and version.is_prerelease
            and version.pre is not None
            and version.pre[0] == "rc"
        ) or (
            channel == "stable"
            and not version.is_prerelease
            and not version.is_devrelease
        )
        if qualifies:
            versions.add(version)
    if channel not in {"rc", "stable"}:
        raise refusal(
            "channel",
            "has no package-index publication version policy",
            "use rc for TestPyPI or stable for PyPI",
        )
    if not versions:
        return None
    selected = max(versions)
    # The Index API selects the version.  Read its exact-version JSON before
    # authorizing it as a predecessor so malformed inventory never looks empty.
    files = _index_version_files(endpoint, distribution_name, str(selected))
    if not files:
        raise RuntimeError("Indeterminate: selected package predecessor has no files")
    return str(selected)


def _require_live_index_predecessor(
    d: InvocationDecision, u: PublicationExpectation
) -> None:
    b = u.body
    live = _index_channel_predecessor(
        _text(b["endpoint"], "package endpoint"), d.candidate.name, d.channel
    )
    declared = b["publication_predecessor_version"]
    if live is None:
        if declared is not None:
            raise refusal(
                "package publication predecessor",
                "live qualifying package history is empty",
                "bind null only for an initial publication",
            )
        return
    try:
        from packaging.version import Version as PackagingVersion

        declared_version = str(
            PackagingVersion(_text(declared, "package predecessor version"))
        )
    except ImportError as error:
        raise RuntimeError(
            "Indeterminate: packaging version parser is unavailable"
        ) from error
    except ValueError as error:
        raise refusal(
            "package publication predecessor",
            "declared version is not PEP 440",
            "bind the observed package version",
        ) from error
    if declared_version != live:
        raise refusal(
            "package publication predecessor",
            "declared version differs from the live channel predecessor",
            "recreate the decision from the observed package version",
        )


def classify_destination(
    d: InvocationDecision, u: PublicationExpectation, observation: object, root: Path
) -> str:
    """Pure classification only; snapshots cannot authorize publication."""
    state = _obj(observation, "destination observation")
    b = u.body
    if u.kind == "github_release_metadata":
        releases, tags = state.get("releases", {}), state.get("tags", {})
        if not isinstance(releases, dict) or not isinstance(tags, dict):
            return "Unavailable"
        item = releases.get(b["tag"])
        target = _snapshot_target(d, u)
        if item is None:
            return "Pending" if tags.get(b["tag"]) in (None, target) else "Conflict"
        return (
            "PublishedExact"
            if isinstance(item, dict)
            and _release_exact(d, u, item, target)
            and tags.get(b["tag"], target) == target
            else "Conflict"
        )
    if u.kind == "git_branch":
        branches = state.get("branches", {})
        current = branches.get(b["branch"]) if isinstance(branches, dict) else False
        return (
            "Unavailable"
            if current is False
            else "PublishedExact"
            if current == _snapshot_target(d, u)
            else "Pending"
            if current == b["predecessor"]
            else "Conflict"
        )
    if u.kind == "git_tag":
        tags = state.get("tags", {})
        current = tags.get(b["tag"]) if isinstance(tags, dict) else False
        return (
            "Unavailable"
            if current is False
            else "PublishedExact"
            if current == _snapshot_target(d, u)
            else "Pending"
            if current is None
            else "Conflict"
        )
    if u.kind == "package_index_upload":
        files = state.get("files", [])
        if not isinstance(files, list):
            return "Unavailable"
        matches = [
            x
            for x in files
            if isinstance(x, dict) and x.get("filename") == Path(b["file"]).name
        ]
        return (
            "Pending"
            if not matches
            else "PublishedExact"
            if len(matches) == 1
            and matches[0].get("sha256", "").removeprefix("sha256:")
            == _digest(b["sha256"], "package sha256")
            else "Conflict"
        )
    if u.kind == "workflow_dispatch":
        runs = state.get("runs", [])
        if not isinstance(runs, list):
            return "Unavailable"
        matches = [
            x
            for x in runs
            if isinstance(x, dict)
            and x.get("headSha") == b["source_sha"]
            and x.get("displayTitle") == b["workflow"]
            and x.get("decision_sha256") == b["downstream_decision_sha256"]
        ]
        return (
            "Pending"
            if not matches
            else "PublishedExact"
            if len(matches) == 1
            and matches[0].get("status") in {"queued", "running", "in_progress"}
            else "Conflict"
        )
    if u.kind == "github_release_asset":
        release = d.unit(_text(b["release_unit"], "release unit"))
        releases = state.get("releases", {})
        if not isinstance(releases, dict) or not isinstance(
            releases.get(release.body["tag"]), dict
        ):
            return "Pending"
        item = releases[release.body["tag"]]
        if not _release_exact(d, release, item, _snapshot_target(d, release)):
            return "Conflict"
        declared = {
            Path(x.body["file"]).name: x
            for x in d.units
            if x.kind == "github_release_asset"
            and x.body["release_unit"] == release.unit_id
        }
        assets = item.get("assets")
        if not isinstance(assets, list):
            return "Unavailable"
        seen: set[str] = set()
        for asset in assets:
            if (
                not isinstance(asset, dict)
                or not isinstance(asset.get("name"), str)
                or asset["name"] in seen
                or asset["name"] not in declared
            ):
                return "Conflict"
            seen.add(asset["name"])
            expected = declared[asset["name"]]
            if asset.get("size") != expected.body["size"] or asset.get(
                "digest", ""
            ).removeprefix("sha256:") != _digest(
                expected.body["sha256"], "asset sha256"
            ):
                return "Conflict"
        return "PublishedExact" if Path(b["file"]).name in seen else "Pending"
    return "Unavailable"


@dataclass(frozen=True, kw_only=True)
class PublicationTargets:
    """WHERE one publication writes, and what may redirect it.

    Keyword-only: `root`, `downstream` and `target_repo` are all paths and
    `downstream` is optional, so a positional permutation would publish into the
    artifact root or the downstream decision instead of the target repository,
    and nothing raises. This module is outside `mypy src/des/`, which is itself
    executed by no workflow, so nothing would catch it.
    """

    root: Path
    downstream: Path | None
    override: str | None
    refs: dict[str, GeneratedCommitRef]
    target_repo: Path


def publish(
    d: InvocationDecision,
    u: PublicationExpectation,
    targets: PublicationTargets,
) -> str:
    root = targets.root
    downstream = targets.downstream
    override = targets.override
    refs = targets.refs
    target_repo = targets.target_repo
    b = u.body
    if u.kind == "github_release_metadata":
        repo, tag, target = (
            _text(b["repository"], "repository"),
            _text(b["tag"], "tag"),
            _target(d, u, refs, target_repo),
        )
        release = _gh_release(repo, tag)
        tag_target = _gh_tag(repo, tag)
        if release is not None:
            if _release_exact(d, u, release, target) and tag_target == target:
                state, _ = _assets(d, u, release, root)
                if state == "Conflict":
                    raise refusal(
                        "release assets", "a sibling differs", "do not mutate release"
                    )
                if state == "Unavailable":
                    raise RuntimeError(
                        "Indeterminate: GitHub asset bytes cannot be verified"
                    )
                return "PublishedExact"
            raise refusal(
                "GitHub release",
                "existing metadata or tag differs",
                "use an exact destination",
            )
        if tag_target != target:
            raise refusal(
                "GitHub release",
                "standalone tag is absent or divergent",
                "publish bound tag first",
            )
        _require_live_predecessor(d, u)
        _assets(d, u, {"assets": []}, root)
        notes = _notes(d, u)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(notes)
            note = handle.name
        try:
            result = _run(
                [
                    "gh",
                    "release",
                    "create",
                    tag,
                    "--repo",
                    repo,
                    "--target",
                    target,
                    "--title",
                    _text(b["title"], "title"),
                    "--notes-file",
                    note,
                ]
                + (["--prerelease"] if b["prerelease"] else [])
            )
        finally:
            Path(note).unlink()
        after = _gh_release(repo, tag)
        if (
            after
            and _release_exact(d, u, after, target)
            and _gh_tag(repo, tag) == target
        ):
            return "Published" if not result.returncode else "PublishedExact"
        raise RuntimeError("Retry: GitHub release create did not become exact")
    if u.kind == "github_release_asset":
        release = d.unit(_text(b["release_unit"], "release unit"))
        repo, tag = (
            _text(release.body["repository"], "repository"),
            _text(release.body["tag"], "tag"),
        )
        state = _gh_release(repo, tag)
        target = _target(d, release, refs, target_repo)
        if (
            state is None
            or not _release_exact(d, release, state, target)
            or _gh_tag(repo, tag) != target
        ):
            raise refusal(
                "release asset",
                "metadata or tag is absent or divergent",
                "publish exact metadata first",
            )
        status, _ = _assets(d, release, state, root)
        if status == "Conflict":
            raise refusal(
                "release assets", "a sibling differs", "do not clobber immutable asset"
            )
        if status == "Unavailable":
            raise RuntimeError("Indeterminate: GitHub asset bytes cannot be verified")
        path = _asset_file(d, u, root)
        if any(
            x.get("name") == path.name
            for x in state.get("assets", [])
            if isinstance(x, dict)
        ):
            return "PublishedExact"
        result = _run(["gh", "release", "upload", tag, str(path), "--repo", repo])
        after = _gh_release(repo, tag)
        if after:
            status, _ = _assets(d, release, after, root)
            if status in {"Pending", "PublishedExact"} and any(
                x.get("name") == path.name
                for x in after.get("assets", [])
                if isinstance(x, dict)
            ):
                return "Published" if not result.returncode else "PublishedExact"
            if status == "Conflict":
                raise refusal(
                    "release asset", "post-upload asset differs", "do not clobber"
                )
        raise RuntimeError("Retry: GitHub asset upload did not become exact")
    if u.kind == "git_branch":
        target, remote, branch = (
            _target(d, u, refs, target_repo),
            _text(b["remote"], "remote"),
            _text(b["branch"], "branch"),
        )
        current = _remote(target_repo, remote, f"refs/heads/{branch}")
        predecessor = _sha(b["predecessor"], "branch predecessor")
        _object(target_repo, predecessor, "branch predecessor", "^{commit}")
        if current == target:
            return "PublishedExact"
        if current != predecessor:
            raise refusal(
                "branch",
                "live predecessor differs from the decision-bound destination",
                "retry only at the observed bound predecessor",
            )
        result = _git(
            target_repo,
            [
                "push",
                f"--force-with-lease=refs/heads/{branch}:{predecessor}",
                remote,
                f"{target}:refs/heads/{branch}",
            ],
        )
        if _remote(target_repo, remote, f"refs/heads/{branch}") == target:
            return "Published" if not result.returncode else "PublishedExact"
        raise RuntimeError("Retry: Git branch lease raced")
    if u.kind == "git_tag":
        target, remote, tag = (
            _target(d, u, refs, target_repo),
            _text(b["remote"], "remote"),
            _text(b["tag"], "tag"),
        )
        current = _tag_target(target_repo, remote, tag)
        if current == target:
            return "PublishedExact"
        if current is not None:
            raise refusal("tag", "existing target differs", "never overwrite tags")
        _require_live_predecessor(d, u)
        result = _git(target_repo, ["push", remote, f"{target}:refs/tags/{tag}"])
        after = _tag_target(target_repo, remote, tag)
        if after == target:
            return "Published" if not result.returncode else "PublishedExact"
        if after is not None:
            raise refusal("tag", "concurrent target differs", "never force tags")
        raise RuntimeError("Retry: Git tag push did not become exact")
    if u.kind == "package_index_upload":
        endpoint = _text(b["endpoint"], "endpoint")
        if override is not None and override != endpoint:
            raise refusal(
                "package endpoint", "override differs", "use decision-bound endpoint"
            )
        path = _asset_file(d, u, root)
        expected = _digest(b["sha256"], "package sha256")
        before = _index_version_files(endpoint, d.candidate.name, d.candidate.version)
        matches = (
            [] if before is None else [x for x in before if x["filename"] == path.name]
        )
        if matches:
            if len(matches) == 1 and matches[0]["sha256"] == expected:
                return "PublishedExact"
            raise refusal(
                "package file", "immutable filename differs", "use a new version"
            )
        _require_live_index_predecessor(d, u)
        result = _run(
            [
                "twine",
                "upload",
                "--repository",
                _text(b["repository"], "repository"),
                str(path),
            ]
        )
        after_state = _index_version_files(
            endpoint, d.candidate.name, d.candidate.version
        )
        after = (
            []
            if after_state is None
            else [x for x in after_state if x["filename"] == path.name]
        )
        if len(after) == 1 and after[0]["sha256"] == expected:
            return "Published" if not result.returncode else "PublishedExact"
        if after:
            raise refusal(
                "package file",
                "post-upload immutable bytes differ",
                "use a new version",
            )
        raise RuntimeError("Retry: package upload did not become exact")
    if u.kind == "workflow_dispatch":
        if downstream is None:
            raise refusal(
                "workflow dispatch",
                "downstream decision is absent",
                "supply --downstream-decision",
            )
        child = decode_decision(downstream, d.repo)
        source = _sha(b["source_sha"], "workflow source")
        if (
            child.channel != b["downstream_channel"]
            or child.digest != _digest(b["downstream_decision_sha256"], "child digest")
            or child.candidate.source_sha != source
            or _sha(b["downstream_source_sha"], "child source") != source
        ):
            raise refusal(
                "workflow dispatch",
                "child channel, digest, or source differs",
                "supply matching independent child decision",
            )
        repo, workflow, ref = (
            _text(b["repository"], "repository"),
            _text(b["workflow"], "workflow"),
            _text(b["ref"], "ref"),
        )
        listed = _run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                workflow,
                "--json",
                "databaseId,headSha,status,conclusion,displayTitle,decision_sha256,source_sha",
            ]
        )
        if listed.returncode:
            raise _indeterminate("workflow observer", listed)
        try:
            runs = json.loads(listed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Indeterminate: unreadable workflow runs: {error}"
            ) from error
        if not isinstance(runs, list):
            raise RuntimeError("Indeterminate: workflow run list is not an array")
        matches = [
            x
            for x in runs
            if isinstance(x, dict)
            and x.get("headSha") == source
            and x.get("source_sha") == source
            and x.get("displayTitle") == workflow
            and x.get("decision_sha256") == child.digest
        ]
        if len(matches) > 1:
            raise refusal(
                "workflow dispatch",
                "multiple correlated runs exist",
                "resolve duplicate state",
            )
        if matches:
            if matches[0].get("status") in {"queued", "running", "in_progress"}:
                return "PublishedExact"
            if (
                matches[0].get("status") == "completed"
                and matches[0].get("conclusion") == "success"
            ):
                raise RuntimeError(
                    "Retry: completed workflow lacks exact child-publication evidence"
                )
            raise RuntimeError(
                "Retry: correlated workflow did not complete successfully"
            )
        handle = _text(b["downstream_decision_handle"], "child decision handle")
        result = _run(
            [
                "gh",
                "workflow",
                "run",
                workflow,
                "--repo",
                repo,
                "--ref",
                ref,
                "-f",
                f"source_sha={source}",
                "-f",
                f"decision_sha256={child.digest}",
                "-f",
                f"downstream_decision_handle={handle}",
            ]
        )
        if result.returncode:
            raise RuntimeError("Retry: workflow dispatch did not complete")
        return "Published"
    raise refusal(
        "publication unit",
        "generated commits are prepared, not published",
        "use prepare-generated-commit",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("publish-unit", "classify-snapshot", "prepare-generated-commit"):
        p = subs.add_parser(name)
        p.add_argument("--channel", required=True)
        p.add_argument("--decision", required=True)
        p.add_argument("--repo-root")
        if name == "publish-unit":
            p.add_argument("--unit", required=True)
            p.add_argument("--artifact-root", required=True)
            p.add_argument("--target-repo-root", required=True)
            p.add_argument("--downstream-decision")
            p.add_argument("--package-index-endpoint")
            p.add_argument("--generated-ref", action="append", default=[])
        elif name == "classify-snapshot":
            p.add_argument("--observations", required=True)
            p.add_argument("--artifact-root", default=".")
        else:
            p.add_argument("--unit", required=True)
            p.add_argument("--worktree", required=True)
            p.add_argument("--output-ref", required=True)
    args = parser.parse_args(argv)
    try:
        decision = decode_decision(
            Path(args.decision),
            Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve(),
        )
        if decision.channel != args.channel:
            raise refusal(
                "channel", "CLI differs from decision", "select bound channel"
            )
        if args.command == "prepare-generated-commit":
            ref = prepare_generated_commit(
                decision, args.unit, Path(args.worktree).resolve()
            )
            Path(args.output_ref).write_text(
                json.dumps(ref.wire(), sort_keys=True) + "\n", encoding="utf-8"
            )
            print(json.dumps(ref.wire(), sort_keys=True))
            return 0
        if args.command == "classify-snapshot":
            try:
                observation = _obj(
                    json.loads(Path(args.observations).read_text(encoding="utf-8")),
                    "observations",
                )
            except (
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                DecisionRefusal,
            ) as error:
                if isinstance(error, DecisionRefusal):
                    raise
                raise refusal(
                    "observations", str(error), "supply read-only valid JSON"
                ) from error
            print(
                json.dumps(
                    {
                        "decision_sha256": decision.digest,
                        "classifications": {
                            u.unit_id: classify_destination(
                                decision, u, observation, Path(args.artifact_root)
                            )
                            for u in decision.units
                            if u.kind != "generated_commit"
                        },
                    },
                    sort_keys=True,
                )
            )
            return 0
        target_repo = Path(args.target_repo_root).resolve()
        print(
            publish(
                decision,
                decision.unit(args.unit),
                PublicationTargets(
                    root=Path(args.artifact_root),
                    downstream=(
                        Path(args.downstream_decision)
                        if args.downstream_decision
                        else None
                    ),
                    override=args.package_index_endpoint,
                    refs=_refs(args.generated_ref, decision, target_repo),
                    target_repo=target_repo,
                ),
            )
        )
        return 0
    except DecisionRefusal as error:
        print(f"Refusal: {error}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
