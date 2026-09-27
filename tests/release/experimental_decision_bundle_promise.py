#!/usr/bin/env python3
"""Executable public promise for the one-command experimental bundle producer.

Given an exact candidate sha and a decided migration block on file, ONE local
command run must produce a verified decision bundle bound to that sha, printing
the bundle path and the decision digest, having itself built the candidate wheel
isolated on that sha and run the same local `decode_decision` validation the
publish workflow repeats.

This harness drives the production script as a SUBPROCESS through its public
command line only.  It echoes that subprocess's own stdout -- the four operator
lines -- before its verdict, so an examiner who never reads the implementation
still sees the observation the promise is judged on.  It then derives the
expectation INDEPENDENTLY, via `projected_candidate`, and checks the emitted
zip rather than anything the command staged.

The same stimulus also observes the PUBLISHED PREDECESSOR.  Every run seeds its
own bare destination repository inside its temporary work directory and always
passes `--target-local-repo`, so the harness is incapable of contacting the
production target.  The operator's plan deliberately carries a WRONG
hand-supplied predecessor identity and lease; the emitted bundle must instead
carry the facts read off that destination.  The expectation is derived
INDEPENDENTLY with plain `git --git-dir` reads and `tomllib`, never through the
producer's own `target_snapshot` seam, and the destination is fingerprinted
before and after to show the run stayed read-only.

The same stimulus finally carries ONE `generated_commit` publication unit, so a
run must also capture the GENERATED PUBLICATION MATERIAL: the tree archive and
the change patch of the publishable projection of the candidate sha, carried in
the emitted zip as reviewable bundle material.  Here too the operator's plan
deliberately guesses the unit's `parent_oid` WRONG; the emitted bundle must
instead carry the head read off the destination, and the carried patch must
reproduce the carried tree when applied to it.

Because every run of this command builds its own candidate wheel, the emitted
bundle must also carry the OFFLINE WHEELHOUSE that build leaves beside that
wheel -- checked on every successful run, by the carried `requirements.lock` and
its artifact-manifest digest recomputed over the extracted bytes.  And the run
must state its own HONESTY BOUNDARY on stdout: one exactly-worded operator line
saying that a local green, resolved from an already-installed environment, does
not prove the publish workflow's fresh CI install will complete.

The same one command is finally observed REFUSING.  A second stimulus changes
exactly one operator byte-field -- the generated unit's declared
`original_source_sha` -- so the plan is unfaithful to the sha the run is asked
to bind.  That run must refuse with one operator-visible reason naming the
offending unit and BOTH shas, must leave the output directory EMPTY rather than
partially written, and must leave the destination byte-identical.  Both runs
additionally put a RECORDING `gh` first on PATH: the log of its invocations is
carried on `Run`, so `never creates or publishes any release` is observed as a
recorded fact -- zero invocations -- on the success run and on the refusal run
alike, rather than merely intended.

Run directly:  python tests/release/experimental_decision_bundle_promise.py
Prints `PROMISE: held` and exits 0, or `PROMISE: broken -- <reason>` and exits 1.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.release.release_migration_fixtures import (
    reference,
    write_json,
)


PRODUCER = Path("scripts/release/release_migration_bundle.py")
CHANNEL = "experimental"
BOUNDARY = "experimental candidate carries no breaking public boundary"
EVIDENCE_NAME = "compatibility.json"
VALIDATED_LINE = (
    "VALIDATED: decode_decision accepted the emitted bundle for this exact sha"
)
VALIDATED_PREDECESSOR_LINE = (
    "VALIDATED-PREDECESSOR: the publisher's own predecessor gate accepts this "
    "bundle against the observed destination"
)
LOCAL_SCOPE_LINE = (
    "LOCAL-SCOPE: this run validated locally with every dependency already "
    "installed and does not prove the publish workflow (fresh install on CI "
    "runners) will complete"
)
TARGET_BRANCH = "main"

# The offline wheelhouse the candidate build leaves beside the wheel it
# produces, retained into the bundle under this prefix.  `requirements.lock` is
# the file the downstream installed-smoke step refuses without, so it is the one
# member whose carriage is observed by name.
WHEELHOUSE_PREFIX = "artifacts/offline-wheelhouse/"
WHEELHOUSE_LOCK = WHEELHOUSE_PREFIX + "requirements.lock"

# The single generated publication unit the operator's plan declares, and the
# canonical commit message template the v4 schema requires of it.
GENERATED_UNIT = "experimental-commit"
GENERATED_MESSAGE = (
    "experimental: atdd-pure preview\n\nDecision-SHA256: {decision_sha256}\n"
)
GENERATED_IDENTITY = {
    "author_name": "nWave Experimental",
    "author_email": "experimental@nwave.ai",
    "author_date": "1700000000 +0000",
    "committer_name": "nWave Experimental",
    "committer_email": "experimental@nwave.ai",
    "committer_date": "1700000000 +0000",
}
TREE_REVIEW = f"generated/{GENERATED_UNIT}/tree.tar"
PATCH_REVIEW = f"generated/{GENERATED_UNIT}/changes.patch"

# The predecessor the operator HAND-SUPPLIES in the plan. It is deliberately
# wrong: nothing resembling it may reach the emitted bundle, because the
# predecessor is observed on the destination, never taken on trust.
GUESS_NAME = "hand-supplied-guess"
GUESS_VERSION = "0.0.0-not-observed"
GUESS_LEASE = "a" * 40

# Default identity seeded into the harness's own destination.
DEFAULT_DESTINATION_NAME = "nwave-ai"
DEFAULT_DESTINATION_VERSION = "4.0.0+atddpure.deadbeef1"


@dataclass(frozen=True)
class Run:
    """Everything one local command run made publicly observable."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    output: Path
    source_sha: str
    predecessor_sha: str
    status_before: str
    status_after: str
    destination: Path
    destination_before: str
    destination_after: str
    gh_calls: list[str]
    output_listing: list[str]
    plan_source_sha: str

    @property
    def bundle_exists(self) -> bool:
        return self.output.is_file()


def _git(*args: str, repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def seed_destination(
    path: Path,
    *,
    name: str = DEFAULT_DESTINATION_NAME,
    version: str = DEFAULT_DESTINATION_VERSION,
) -> Path:
    """Create the bare destination repository this run observes.

    The recipe is the publisher's own hermetic one: an existing BARE repository
    whose `main` carries a `pyproject.toml` declaring `[project] name` and
    `version`.  That published identity is the predecessor the command must
    read, and it is chosen HERE so it can be distinguished from anything the
    operator's plan guesses.
    """
    path = path.absolute()
    staging = path.parent / (path.name + ".seed")
    staging.mkdir(parents=True)
    (staging / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\n', encoding="utf-8"
    )
    _git("init", "--quiet", "--initial-branch", TARGET_BRANCH, ".", repo_root=staging)
    _git("config", "user.email", "promise@example.invalid", repo_root=staging)
    _git("config", "user.name", "Decision Bundle Promise", repo_root=staging)
    _git("add", "pyproject.toml", repo_root=staging)
    _git("commit", "--quiet", "-m", "published predecessor", repo_root=staging)
    _git(
        "clone", "--quiet", "--bare", str(staging), str(path), repo_root=staging.parent
    )
    return path


def destination_fingerprint(destination: Path) -> str:
    """Digest every ref and every object the destination holds.

    Any write to the destination -- a new ref, a fetched or created object --
    changes this string, so comparing it before and after a run is a direct
    observation that the run was read-only.
    """
    refs = _git("--git-dir", str(destination), "show-ref", repo_root=REPO_ROOT)
    objects = _git(
        "--git-dir",
        str(destination),
        "cat-file",
        "--batch-check=%(objectname) %(objecttype)",
        "--batch-all-objects",
        repo_root=REPO_ROOT,
    )
    material = refs + "\n--\n" + "\n".join(sorted(objects.splitlines()))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def observed_predecessor_independently(destination: Path) -> tuple[str, str, str]:
    """Read (commit, name, version) off the destination without the producer.

    Deliberately plain `git --git-dir` reads parsed with `tomllib`: the
    expectation must not be derived through `target_snapshot`, the very seam the
    command under observation uses, or the promise would only prove that seam
    agrees with itself.
    """
    commit = _git(
        "--git-dir", str(destination), "rev-parse", f"refs/heads/{TARGET_BRANCH}"
    )
    text = _git("--git-dir", str(destination), "show", f"{commit}:pyproject.toml")
    project = tomllib.loads(text)["project"]
    return commit, project["name"], project["version"]


def write_inputs(
    workdir: Path,
    *,
    source_sha: str,
    predecessor_sha: str,
    plan_source_sha: str | None = None,
) -> tuple[Path, Path]:
    """Write the operator's publication plan and decided migration block.

    The plan carries exactly what an operator decides locally: one retained
    evidence artifact, one `generated_commit` unit declaring the publication
    material to be generated from the candidate sha, and one `git_branch`
    publication unit for the target branch whose target is that generated unit.
    Its predecessor
    fields -- the distribution identity, the branch unit's CAS lease and the
    generated unit's `parent_oid` -- are a
    deliberately WRONG hand-supplied guess, so a bundle that merely copied the
    plan through would be plainly distinguishable from one that observed the
    destination.  The generated unit deliberately omits `tree_oid`: that fact
    exists only once the material has actually been captured, and the command
    must fill it from what it captured, never from a declaration.  The
    migration block is the `required: false` v4 shape, and its evidence
    reference is written in the IN-BUNDLE form -- `artifacts/<name>` -- because
    the producer retains plan artifacts under `artifacts/` beside decision.json.

    `plan_source_sha` overrides the ONE field the generated unit uses to declare
    which commit its material is generated from.  Left unset it equals the sha
    the run is asked to bind, which is the faithful plan.  Set to some other
    commit it makes the plan UNFAITHFUL: the operator's declaration and the sha
    the run resolves disagree, and no bundle bound to either can be honest.
    """
    evidence = write_json(
        workdir / EVIDENCE_NAME, {"boundary": BOUNDARY, "source_sha": source_sha}
    )
    plan = write_json(
        workdir / "publication-plan.json",
        {
            "predecessor": {
                "distribution_name": GUESS_NAME,
                "version": GUESS_VERSION,
            },
            "retained_artifacts": [str(evidence)],
            "publication_units": [
                {
                    "id": GENERATED_UNIT,
                    "kind": "generated_commit",
                    "original_source_sha": plan_source_sha or source_sha,
                    "parent_oid": predecessor_sha,
                    "message_template": GENERATED_MESSAGE,
                    **GENERATED_IDENTITY,
                },
                {
                    "id": "experimental-branch",
                    "kind": "git_branch",
                    "branch": TARGET_BRANCH,
                    "remote": "origin",
                    "predecessor": predecessor_sha,
                    "target": {
                        "kind": "generated-commit",
                        "producer_unit": GENERATED_UNIT,
                    },
                },
            ],
        },
    )
    in_bundle = dict(reference(evidence, workdir))
    in_bundle["file"] = f"artifacts/{EVIDENCE_NAME}"
    migration = write_json(
        workdir / "migration.json",
        {
            "required": False,
            "compatibility_boundary": BOUNDARY,
            "evidence": [in_bundle],
        },
    )
    return plan, migration


def recording_gh(workdir: Path) -> tuple[Path, dict[str, str]]:
    """Put a RECORDING `gh` first on PATH and return its log path and env.

    Creating or publishing a release in this tree goes through `gh`.  The stub
    appends every invocation it receives to the log and then fails loudly, so an
    attempt to publish is both recorded and unable to succeed on ambient
    credentials.  An EMPTY log after a run is therefore a positive observation
    that the run created and published nothing.  Real Git stays available: the
    run legitimately reads the local destination with it.
    """
    bin_dir = workdir / "recording-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log = (workdir / "gh-calls.log").absolute()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "gh $*" >> {log}\n'
        "echo 'gh is unreachable in this promise' >&2\n"
        "exit 97\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return log, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


@dataclass(frozen=True)
class CandidateSource:
    """Which repository, and which revision in it, one run is asked to bind.

    The two are ONE fact for `produce`: a revision means nothing except
    against the repository it is resolved in, and `produce` resolves them
    together. The claim stops there. `other_commit` and `broken_reason` still
    take them apart, so this record does not yet describe the whole module.
    """

    repo_root: Path = REPO_ROOT
    revision: str = "HEAD"


THIS_REPOSITORY_AT_HEAD = CandidateSource()


def produce(
    workdir: Path,
    *,
    source: CandidateSource = THIS_REPOSITORY_AT_HEAD,
    env: dict[str, str] | None = None,
    destination: Path | None = None,
    plan_source_sha: str | None = None,
) -> Run:
    """Invoke the production command once, as a subprocess, and observe it.

    `destination` is the bare repository the command must observe as the
    published target.  When omitted the harness seeds its own; either way the
    run always names it with `--target-local-repo`, so no invocation of this
    promise can reach the production target.

    `--output` is placed in a DEDICATED `out/` subdirectory of the work
    directory, which holds nothing else.  That directory's listing after the run
    is therefore a direct observation of what the run left behind: exactly the
    one named bundle on success, and NOTHING at all -- no half-written zip, no
    surviving scratch directory -- on a refusal.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    if destination is None:
        destination = seed_destination(workdir / "destination.git")
    destination = destination.absolute()
    source_sha = _git(
        "rev-parse",
        "--verify",
        f"{source.revision}^{{commit}}",
        repo_root=source.repo_root,
    )
    predecessor_sha = GUESS_LEASE
    plan, migration = write_inputs(
        workdir,
        source_sha=source_sha,
        predecessor_sha=predecessor_sha,
        plan_source_sha=plan_source_sha,
    )
    gh_log, gh_env = recording_gh(workdir)
    out_dir = workdir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "experimental-migration-decision.zip"
    argv = [
        sys.executable,
        str(source.repo_root / PRODUCER),
        "produce-decision-bundle",
        "--channel",
        CHANNEL,
        "--source-sha",
        source_sha,
        "--publication-plan",
        str(plan),
        "--migration",
        str(migration),
        "--output",
        str(output),
        "--target-local-repo",
        str(destination),
    ]
    child_env = dict(os.environ)
    child_env.update(gh_env)
    child_env.update(env or {})
    status_before = _git("status", "--porcelain", repo_root=source.repo_root)
    destination_before = destination_fingerprint(destination)
    result = subprocess.run(
        argv,
        cwd=source.repo_root,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=1800,
        env=child_env,
        check=False,
    )
    status_after = _git("status", "--porcelain", repo_root=source.repo_root)
    destination_after = destination_fingerprint(destination)
    return Run(
        argv=argv,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        output=output,
        source_sha=source_sha,
        predecessor_sha=predecessor_sha,
        status_before=status_before,
        status_after=status_after,
        destination=destination,
        destination_before=destination_before,
        destination_after=destination_after,
        gh_calls=(
            gh_log.read_text(encoding="utf-8").splitlines() if gh_log.is_file() else []
        ),
        output_listing=sorted(p.name for p in out_dir.iterdir()),
        plan_source_sha=plan_source_sha or source_sha,
    )


def _operator_lines(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        for key in (
            "CANDIDATE",
            "BUNDLE",
            "DECISION-SHA256",
            "PREDECESSOR",
            "DESTINATION",
            "REVIEW",
        ):
            prefix = key + ": "
            if line.startswith(prefix):
                fields[key] = line[len(prefix) :].strip()
        if line.strip() == VALIDATED_LINE:
            fields["VALIDATED"] = VALIDATED_LINE
        if line.strip() == VALIDATED_PREDECESSOR_LINE:
            fields["VALIDATED-PREDECESSOR"] = VALIDATED_PREDECESSOR_LINE
        if line.strip() == LOCAL_SCOPE_LINE:
            fields["LOCAL-SCOPE"] = LOCAL_SCOPE_LINE
    return fields


def _wheel_metadata(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise RuntimeError("retained wheel has no unique METADATA")
        fields = dict(
            line.split(": ", 1)
            for line in archive.read(names[0]).decode().splitlines()
            if ": " in line
        )
    return fields["Name"], fields["Version"]


def _tar_members(archive: Path) -> dict[str, bytes]:
    """Read the tree archive as name -> bytes, ignoring archive-time metadata."""
    members: dict[str, bytes] = {}
    with tarfile.open(archive, "r:") as tar:
        for info in tar.getmembers():
            if info.isfile():
                handle = tar.extractfile(info)
                members[info.name.removeprefix("./")] = (
                    b"" if handle is None else handle.read()
                )
    return members


def _reproduced_tree(destination: Path, parent: str, patch: Path) -> str:
    """Apply the carried patch onto the carried parent and return the tree oid.

    A throwaway clone of the destination is used so the reproduction is done
    with plain Git against the very head the bundle claims as its base.
    """
    with tempfile.TemporaryDirectory(prefix="promise-patch-") as raw:
        work = Path(raw) / "work"
        _git("clone", "--quiet", "--no-checkout", str(destination), str(work))
        _git("-C", str(work), "checkout", "--quiet", "--detach", parent)
        _git("-C", str(work), "apply", "--binary", "--index", str(patch))
        return _git("-C", str(work), "write-tree")


def generated_material_reason(
    extracted: Path, decision: object, head: str, source_sha: str, destination: Path
) -> str | None:
    """Return why the carried publication material is wrong, or None.

    The bundle must carry, for the single declared generated unit, the tree
    archive and the change patch of the publishable projection of the candidate
    sha: both files present in the emitted zip and listed in its artifact
    manifest with matching bytes, the unit's `parent_oid` equal to the head read
    INDEPENDENTLY off the destination, the patch reproducing the declared
    `tree_oid` when applied to that head, and the archived tree carrying a
    candidate-stamped `pyproject.toml` while carrying none of the private
    surface the publisher strips.
    """
    from scripts.release.experimental_migration_decision import short_sha_of

    generated = [
        unit
        for unit in decision.units  # type: ignore[attr-defined]
        if unit.kind == "generated_commit"
    ]
    if len(generated) != 1:
        return (
            f"emitted bundle declares {len(generated)} generated_commit units, "
            "not exactly one"
        )
    body = generated[0].body
    tree_oid, parent_oid = body.get("tree_oid"), body.get("parent_oid")
    if parent_oid != head:
        return (
            f"carried parent_oid {parent_oid!r} is not the destination's published "
            f"head {head!r}"
        )
    tree_archive, patch = extracted / TREE_REVIEW, extracted / PATCH_REVIEW
    for path, name in ((tree_archive, TREE_REVIEW), (patch, PATCH_REVIEW)):
        if not path.is_file():
            return f"emitted bundle carries no review material at {name}"
    manifest_path = extracted / "artifact-manifest.json"
    if not manifest_path.is_file():
        return "emitted bundle has no artifact-manifest.json"
    manifest = {
        item.get("file"): item
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(item, dict)
    }
    for path, name in ((tree_archive, TREE_REVIEW), (patch, PATCH_REVIEW)):
        item = manifest.get(name)
        if item is None:
            return f"review material {name} is absent from the artifact manifest"
        if item.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            return f"review material {name} does not match its manifest sha256"
        if item.get("size") != path.stat().st_size:
            return f"review material {name} does not match its manifest size"

    reproduced = _reproduced_tree(destination, head, patch)
    if reproduced != tree_oid:
        return (
            f"applying {PATCH_REVIEW} to {head} produced tree {reproduced}, not the "
            f"carried tree_oid {tree_oid}"
        )

    members = _tar_members(tree_archive)
    project = members.get("pyproject.toml")
    if project is None:
        return f"{TREE_REVIEW} carries no pyproject.toml"
    stamp = f"+atddpure.{short_sha_of(source_sha)}"
    version = tomllib.loads(project.decode("utf-8"))["project"]["version"]
    if stamp not in version:
        return (
            f"{TREE_REVIEW} declares version {version!r}, which is not stamped "
            f"with {stamp!r}"
        )
    private = sorted(
        name for name in members if name.startswith(".github/") or name == "CLAUDE.md"
    )
    if private:
        return f"{TREE_REVIEW} carries private material {private}"
    return None


def wheelhouse_reason(extracted: Path) -> str | None:
    """Return why the carried offline wheelhouse is wrong, or None.

    Every run of this command builds its own candidate wheel, and that build
    leaves an offline wheelhouse beside the wheel.  A bundle carrying the wheel
    without that wheelhouse is an incomplete handoff: the downstream installed
    smoke step refuses a retained wheel whose adjacent `requirements.lock` is
    missing, and it does so in a job that never touched a broken wheel.  So the
    lock must be carried in the EMITTED zip and listed in the artifact manifest
    under the digest the harness recomputes over the extracted bytes -- a stale
    or truncated copy is as useless as an absent one.

    This is checked on EVERY successful run, not only on plans that declare
    generated publication material, because every such run built a wheel.
    """
    lock = extracted / WHEELHOUSE_LOCK
    if not lock.is_file():
        return (
            f"emitted bundle carries the candidate wheel but no {WHEELHOUSE_LOCK}, "
            "so the retained offline wheelhouse is incomplete"
        )
    manifest_path = extracted / "artifact-manifest.json"
    if not manifest_path.is_file():
        return "emitted bundle has no artifact-manifest.json"
    manifest = {
        item.get("file"): item
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(item, dict)
    }
    item = manifest.get(WHEELHOUSE_LOCK)
    if item is None:
        return f"{WHEELHOUSE_LOCK} is absent from the artifact manifest"
    recomputed = hashlib.sha256(lock.read_bytes()).hexdigest()
    if item.get("sha256") != recomputed:
        return (
            f"manifest sha256 {item.get('sha256')!r} for {WHEELHOUSE_LOCK} is not the "
            f"digest {recomputed} of the bytes the bundle carries"
        )
    return None


def broken_reason(run: Run, *, repo_root: Path = REPO_ROOT) -> str | None:
    """Return why the promise is broken, or None when it is held."""
    from scripts.release.experimental_migration_decision import (
        projected_candidate,
        validate_predecessor_metadata,
    )
    from scripts.release.release_migration_decision import decode_decision

    if run.returncode != 0:
        return f"command exited {run.returncode}; stderr: {run.stderr.strip()[:400] or '(empty)'}"
    fields = _operator_lines(run.stdout)
    missing = [
        key
        for key in (
            "CANDIDATE",
            "BUNDLE",
            "DECISION-SHA256",
            "VALIDATED",
            "PREDECESSOR",
            "DESTINATION",
            "VALIDATED-PREDECESSOR",
            "LOCAL-SCOPE",
            "REVIEW",
        )
        if key not in fields
    ]
    if missing:
        return f"stdout lacks operator line(s) {', '.join(missing)}"
    if not run.bundle_exists:
        return f"no bundle was written at {run.output}"
    if fields["BUNDLE"] != str(run.output.absolute()):
        return (
            f"printed bundle path {fields['BUNDLE']!r} is not the requested output "
            f"{str(run.output.absolute())!r}"
        )

    expected = projected_candidate(repo_root, run.source_sha)
    with tempfile.TemporaryDirectory(prefix="promise-extract-") as raw:
        extracted = Path(raw)
        with zipfile.ZipFile(run.output) as bundle:
            for member in bundle.infolist():
                relative = Path(member.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    return f"unsafe bundle member {member.filename!r}"
            bundle.extractall(extracted)
        wheelhouse = wheelhouse_reason(extracted)
        if wheelhouse is not None:
            return wheelhouse
        record = extracted / "decision.json"
        if not record.is_file():
            return "emitted bundle has no decision.json"
        decision = decode_decision(record, repo_root)
        observed = (
            decision.candidate.source_sha,
            decision.candidate.name,
            decision.candidate.version,
        )
        projected = (expected.source_sha, expected.name, expected.version)
        if observed != projected:
            return f"bundled candidate {observed} is not the projected {projected}"
        wheel = extracted / decision.candidate.wheel["file"]
        if not wheel.is_file():
            return "bundle does not carry the candidate wheel it names"
        if _wheel_metadata(wheel) != (expected.name, expected.version):
            return (
                f"carried wheel METADATA {_wheel_metadata(wheel)} is not the built "
                f"candidate {(expected.name, expected.version)}"
            )
        digest = hashlib.sha256(record.read_bytes()).hexdigest()
        if fields["DECISION-SHA256"] != digest:
            return (
                f"printed digest {fields['DECISION-SHA256']} is not the emitted "
                f"decision.json digest {digest}"
            )
        channel = json.loads(record.read_text(encoding="utf-8")).get("channel")
        if channel != CHANNEL:
            return f"bundled channel is {channel!r}, not {CHANNEL!r}"

        # --- the predecessor must be the one PUBLISHED on the destination ---
        commit, name, version = observed_predecessor_independently(run.destination)
        if decision.predecessor is None:
            return "emitted bundle carries no predecessor at all"
        bound = (
            decision.predecessor.distribution_name,
            decision.predecessor.version,
        )
        if bound != (name, version):
            return (
                f"bundled predecessor identity {bound} is not the identity published "
                f"on the destination {(name, version)}"
            )
        leases = [
            unit.body.get("predecessor")
            for unit in decision.units
            if unit.kind == "git_branch" and unit.body.get("branch") == TARGET_BRANCH
        ]
        if len(leases) != 1:
            return (
                f"emitted bundle declares {len(leases)} git_branch units for "
                f"{TARGET_BRANCH!r}, not exactly one"
            )
        if leases[0] != commit:
            return (
                f"bundled CAS lease {leases[0]!r} is not the destination's published "
                f"head {commit!r}"
            )
        raw = record.read_text(encoding="utf-8")
        leaked = [
            guess for guess in (GUESS_NAME, GUESS_VERSION, GUESS_LEASE) if guess in raw
        ]
        if leaked:
            return (
                f"the operator's hand-supplied guess {leaked} survived into the "
                "emitted decision.json"
            )
        try:
            validate_predecessor_metadata(
                commit,
                _git(
                    "--git-dir",
                    str(run.destination),
                    "show",
                    f"{commit}:pyproject.toml",
                ),
                decision,
                leases[0],
            )
        except Exception as error:
            return f"the publisher's own predecessor gate rejects the bundle: {error}"

        predecessor_line = f"{name} {version} @ {commit}"
        if fields["PREDECESSOR"] != predecessor_line:
            return (
                f"printed predecessor {fields['PREDECESSOR']!r} is not "
                f"{predecessor_line!r}"
            )
        if str(run.destination) not in fields["DESTINATION"]:
            return (
                f"printed destination {fields['DESTINATION']!r} does not name the "
                f"observed destination {str(run.destination)!r}"
            )

        # --- the bundle must carry the generated publication material ---
        material = generated_material_reason(
            extracted, decision, commit, run.source_sha, run.destination
        )
        if material is not None:
            return material
        generated = next(
            unit for unit in decision.units if unit.kind == "generated_commit"
        )
        review_line = (
            f"{generated.body['id']} tree {generated.body['tree_oid']} on "
            f"{generated.body['parent_oid']} -- {TREE_REVIEW}, {PATCH_REVIEW}"
        )
        if fields["REVIEW"] != review_line:
            return f"printed review {fields['REVIEW']!r} is not {review_line!r}"
        order = [
            line.split(":", 1)[0]
            for line in run.stdout.splitlines()
            if line.split(":", 1)[0] in {"DESTINATION", "REVIEW", "BUNDLE"}
        ]
        if order != ["DESTINATION", "REVIEW", "BUNDLE"]:
            return (
                f"operator lines are ordered {order}, not DESTINATION, REVIEW, BUNDLE"
            )

    candidate_line = f"{expected.name} {expected.version} @ {run.source_sha}"
    if fields["CANDIDATE"] != candidate_line:
        return f"printed candidate {fields['CANDIDATE']!r} is not {candidate_line!r}"
    if run.status_after != run.status_before:
        return "the run changed the working tree"
    if run.destination_after != run.destination_before:
        return "the run wrote to the destination it was only asked to observe"
    if run.gh_calls:
        return (
            "the run reached for `gh`, the only way this tree creates or publishes "
            f"a release: {run.gh_calls}"
        )
    if run.output_listing != [run.output.name]:
        return (
            f"a successful run left {run.output_listing} beside its output, not "
            f"exactly {[run.output.name]}"
        )
    return None


def refusal_broken_reason(run: Run) -> str | None:
    """Return why the REFUSAL promise is broken, or None when it is held.

    The stimulus is an operator plan whose generated unit declares a commit
    other than the sha this run was asked to bind.  Nothing faithful to that sha
    can be built from it, so the command must refuse, and the refusal must be
    usable: ONE operator-visible line naming the offending unit and BOTH shas,
    so the operator can see which of their two declarations to correct without
    reading the implementation.  It must also be cheap and clean -- no partial
    output whatsoever in the output directory -- and it must leave the
    destination exactly as it found it, having created or published nothing.
    """
    if run.returncode != 2:
        return (
            f"an unfaithful plan exited {run.returncode}, not the refusal status 2; "
            f"stdout: {run.stdout.strip()[:400] or '(empty)'}"
        )
    refusals = [
        line for line in run.stderr.splitlines() if line.startswith("REFUSAL: ")
    ]
    if len(refusals) != 1:
        return (
            f"the refusal is {len(refusals)} REFUSAL line(s), not exactly one; "
            f"stderr: {run.stderr.strip()[:400] or '(empty)'}"
        )
    line = refusals[0]
    if " WHY: " not in line or " HOW: " not in line:
        return f"refusal line {line!r} lacks a WHY and a HOW"
    why = line.split(" WHY: ", 1)[1].rsplit(" HOW: ", 1)[0]
    for what, value in (
        ("the offending unit id", GENERATED_UNIT),
        ("the sha the plan declared", run.plan_source_sha),
        ("the sha the run resolved", run.source_sha),
    ):
        if value not in why:
            return f"the refusal reason {why!r} does not name {what} {value!r}"
    if run.bundle_exists:
        return f"the refusal left a bundle at {run.output}"
    if run.output_listing:
        return (
            f"the refusal left partial output {run.output_listing} in "
            f"{run.output.parent}"
        )
    if run.destination_after != run.destination_before:
        return "the refused run wrote to the destination it was only asked to observe"
    if run.gh_calls:
        return (
            "the refused run reached for `gh`, the only way this tree creates or "
            f"publishes a release: {run.gh_calls}"
        )
    return None


def other_commit(repo_root: Path = REPO_ROOT, revision: str = "HEAD") -> str:
    """A real commit of this repository that is NOT the one a run will bind.

    The unfaithful stimulus needs a sha that is well-formed and genuinely
    resolvable -- so the refusal is about faithfulness, not about a malformed
    field -- yet different from the candidate sha.  The candidate's own parent
    is exactly that.
    """
    return _git(
        "rev-parse", "--verify", f"{revision}~1^{{commit}}", repo_root=repo_root
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="decision-bundle-promise-") as raw:
        work = Path(raw)
        run = produce(work / "success")
        sys.stdout.write(run.stdout)
        sys.stdout.write(run.stderr)
        sys.stdout.flush()
        reason = broken_reason(run)

        refused = produce(work / "refusal", plan_source_sha=other_commit())
        sys.stdout.write(refused.stdout)
        sys.stdout.write(refused.stderr)
        sys.stdout.flush()
        refusal_reason = refusal_broken_reason(refused)
    if reason is None and refusal_reason is None:
        print("PROMISE: held")
        return 0
    print(f"PROMISE: broken -- {reason or refusal_reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
