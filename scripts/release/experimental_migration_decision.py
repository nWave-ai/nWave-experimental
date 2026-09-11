"""Validate the experimental publication decision at its real write boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
    import tomllib as tomli
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 release script.
    import tomli


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


class DecisionRefusal(ValueError):
    pass


# The `+atddpure.<sha>` version label embeds an ABBREVIATED commit id. Git's
# own `rev-parse --short` abbreviation width is NOT a constant: it depends on
# the object count of the repository the command runs against, so a full
# local clone and a shallow `actions/checkout` CI clone (`fetch-depth: 1`, far
# fewer objects) can abbreviate the SAME revision to different widths.
# Measured 2026-09-11 on f28ccc77f5e9c2fabc2721d62a1ad56b5ba13f85 (run
# 34587462454): local full clone -> `f28ccc77f` (9 chars); git's own default
# abbreviation on the CI shallow clone's smaller object count -> `f28ccc7`
# (7 chars). The publisher (full clone) and the CI gate (shallow clone) then
# composed two different candidate versions for the identical commit, and the
# equality check in `publish_experimental.py` refused a valid candidate with
# "migration decision candidate does not match this projected source".
#
# Fixed here, ONCE, derived from the FULL sha the caller already resolved --
# never re-derived by asking git to abbreviate again. Fixed at 9, not 7 and
# not git's ambient default, because the wheel already built and the
# transport release already published for this candidate both carry the
# 9-character label `f28ccc77f`; a shorter fixed width would orphan that
# already-published artifact and force a fourth rebuild.
SHORT_SHA_LENGTH = 9


def short_sha_of(full_sha: str) -> str:
    """Derive the canonical `+atddpure.<sha>` abbreviation from a FULL sha.

    Pure string truncation, not a git call: the caller has already resolved
    `full_sha` (e.g. via `git rev-parse <ref>` or `$GITHUB_SHA`), and slicing
    a known-full commit id is unambiguous regardless of how many objects the
    local repository happens to hold.
    """
    if len(full_sha) < SHORT_SHA_LENGTH or any(
        char not in "0123456789abcdef" for char in full_sha.lower()
    ):
        raise DecisionRefusal(
            f"full_sha must be a full hex commit id, got {full_sha!r}"
        )
    return full_sha[:SHORT_SHA_LENGTH]


@dataclass(frozen=True)
class Candidate:
    source_sha: str
    name: str
    version: str
    wheel: dict[str, str]


@dataclass(frozen=True)
class Predecessor:
    target_commit: str
    distribution_name: str
    version: str


@dataclass(frozen=True)
class Decision:
    raw: bytes
    root: Path
    candidate: Candidate
    predecessor: Predecessor
    migration: dict[str, Any]

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionRefusal(f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionRefusal(f"{name} must be a non-empty string")
    return value.strip()


def _reference(value: object, root: Path, name: str) -> tuple[Path, dict[str, str]]:
    item = _object(value, name)
    if set(item) != {"file", "sha256"}:
        raise DecisionRefusal(f"{name} must contain file and sha256")
    relative = Path(_text(item["file"], f"{name}.file"))
    if relative.is_absolute() or ".." in relative.parts:
        raise DecisionRefusal(f"{name}.file must stay below the decision record")
    digest = _text(item["sha256"], f"{name}.sha256")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise DecisionRefusal(f"{name}.sha256 must be lowercase SHA-256")
    path = root / relative
    if not path.is_file():
        raise DecisionRefusal(f"{name}.file is absent")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise DecisionRefusal(f"{name}.sha256 does not match retained bytes")
    return path, {"file": str(relative), "sha256": digest}


def _wheel_metadata(path: Path) -> dict[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(names) != 1:
                raise DecisionRefusal("candidate wheel has no unique METADATA")
            return dict(
                line.split(": ", 1)
                for line in archive.read(names[0]).decode("utf-8").splitlines()
                if ": " in line
            )
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as error:
        raise DecisionRefusal(
            f"candidate wheel metadata is unreadable: {error}"
        ) from error


def projected_candidate(repo_root: Path, source_sha: str) -> Candidate:
    result = subprocess.run(
        ["git", "show", f"{source_sha}:pyproject.toml"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    if result.returncode:
        raise DecisionRefusal("candidate ref has no readable pyproject.toml")
    try:
        project = tomli.loads(result.stdout)["project"]
        base = _text(project["version"], "candidate project.version").split("+", 1)[0]
    except (tomli.TOMLDecodeError, KeyError, TypeError, DecisionRefusal) as error:
        raise DecisionRefusal(
            f"candidate ref has invalid project metadata: {error}"
        ) from error
    return Candidate(
        source_sha, "nwave-ai", f"{base}+atddpure.{short_sha_of(source_sha)}", {}
    )


def _same_identity(value: object, candidate: Candidate, name: str) -> None:
    item = _object(value, name)
    if (
        item.get("source_sha") != candidate.source_sha
        or item.get("name") != candidate.name
        or item.get("version") != candidate.version
        or item.get("wheel") != candidate.wheel
    ):
        raise DecisionRefusal(f"{name} does not match decision candidate")


def _same_predecessor(value: object, predecessor: Predecessor, name: str) -> None:
    item = _object(value, name)
    if (
        item.get("name") != predecessor.distribution_name
        or item.get("version") != predecessor.version
    ):
        raise DecisionRefusal(f"{name} does not match decision predecessor")


def _validate_checkpoint(path: Path, expected: str, decision: Decision) -> None:
    try:
        value = _object(
            json.loads(path.read_text(encoding="utf-8")), f"checkpoint {expected}"
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionRefusal(
            f"checkpoint {expected} is unreadable: {error}"
        ) from error
    if value.get("checkpoint") != expected:
        raise DecisionRefusal(f"checkpoint {expected} name does not match")
    _same_identity(
        value.get("candidate"), decision.candidate, f"checkpoint {expected} candidate"
    )
    _same_predecessor(
        value.get("predecessor"),
        decision.predecessor,
        f"checkpoint {expected} predecessor",
    )
    if (
        expected in {"selected_root_config", "des_install_manifest"}
        and "artifact" in value
    ):
        artifact, _ = _reference(
            value.get("artifact"), decision.root, f"checkpoint {expected} artifact"
        )
        try:
            observation = _object(
                json.loads(artifact.read_text(encoding="utf-8")),
                f"checkpoint {expected} artifact",
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DecisionRefusal(
                f"checkpoint {expected} artifact is not JSON: {error}"
            ) from error
    else:
        command = _object(value.get("command"), f"checkpoint {expected} command")
        if not isinstance(command.get("argv"), list) or command.get("returncode") != 0:
            raise DecisionRefusal(
                f"checkpoint {expected} command is not a successful observation"
            )
        stdout_path, _ = _reference(
            command.get("stdout"), decision.root, f"checkpoint {expected} stdout"
        )
        _reference(
            command.get("stderr"), decision.root, f"checkpoint {expected} stderr"
        )
        observation_bytes = stdout_path.read_bytes()
        try:
            observation = _object(
                json.loads(observation_bytes), f"checkpoint {expected} stdout"
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            observation = {"text": observation_bytes.decode("utf-8", errors="replace")}
    if expected == "candidate_wheel" and (
        observation.get("Name") != decision.candidate.name
        or observation.get("Version") != decision.candidate.version
        or observation.get("SHA256") != decision.candidate.wheel["sha256"]
    ):
        raise DecisionRefusal(
            "candidate_wheel observation does not bind candidate metadata"
        )
    if expected == "predecessor_identity" and (
        observation.get("distributions")
        != {decision.predecessor.distribution_name: decision.predecessor.version}
        or observation.get("module_owners") != [decision.predecessor.distribution_name]
    ):
        raise DecisionRefusal(
            "predecessor_identity observation does not bind predecessor owner"
        )
    if expected == "canonical_install_identity" and (
        observation.get("distributions")
        != {decision.candidate.name: decision.candidate.version}
        or observation.get("module_owners") != [decision.candidate.name]
    ):
        raise DecisionRefusal(
            "canonical_install_identity observation does not bind canonical owner"
        )
    if expected == "canonical_console_version" and (
        decision.candidate.version not in observation.get("text", "")
        and observation.get("version") != decision.candidate.version
    ):
        raise DecisionRefusal(
            "canonical_console_version does not bind candidate version"
        )
    if expected == "doctor_json" and observation.get("summary", {}).get("failed") != 0:
        raise DecisionRefusal("doctor_json checkpoint is unhealthy")
    if (
        expected == "des_install_manifest"
        and observation.get("installed_version") != decision.candidate.version
    ):
        raise DecisionRefusal("des_install_manifest does not bind candidate version")


def validate_predecessor_metadata(
    commit: str, pyproject_text: str, decision: Any, target_commit: str
) -> None:
    """Bind an observed target commit to the decision's predecessor identity.

    ``target_commit`` is the declared CAS-lease value for the write (the
    ``git_branch`` publication unit's ``predecessor`` field on a v4-shaped
    decision; a bare ``predecessor.target_commit`` on the legacy v2 shape).
    It is supplied by the caller rather than read off ``decision.predecessor``
    because that fact travels in a different place depending on schema, while
    package identity (``distribution_name``/``version``) does not.
    """
    if commit != target_commit:
        raise DecisionRefusal(
            "target predecessor commit changed or does not match migration decision"
        )
    if decision.predecessor is None:
        raise DecisionRefusal(
            "migration decision has no predecessor to bind an observed target "
            "commit against (an initial-publication decision has none)"
        )
    try:
        project = tomli.loads(pyproject_text)["project"]
    except (tomli.TOMLDecodeError, KeyError, TypeError) as error:
        raise DecisionRefusal(
            f"target predecessor has no readable pyproject metadata: {error}"
        ) from error
    if (
        project.get("name") != decision.predecessor.distribution_name
        or project.get("version") != decision.predecessor.version
    ):
        raise DecisionRefusal(
            "target predecessor package identity does not match migration decision"
        )


def retry_message_matches(message: str, decision: Any) -> bool:
    expected = {
        "Source": decision.candidate.source_sha,
        "Candidate": f"{decision.candidate.name} {decision.candidate.version}",
        "Decision-SHA256": decision.digest,
    }
    observed: dict[str, list[str]] = {key: [] for key in expected}
    for line in message.splitlines():
        for key in expected:
            prefix = f"{key}: "
            if line.startswith(prefix):
                observed[key].append(line.removeprefix(prefix))
    return all(observed[key] == [value] for key, value in expected.items())
