#!/usr/bin/env python3
"""Run the WHOLE K4 chain with the model calls replaced by something inert.

    offline_chain_probe.py --root <dir> [--pairs 3] [--stages a,b,c] [--wheel W]

Stratification, which is the whole point: a K4 campaign has a DETERMINISTIC
layer -- paths, permissions, environment, argument shape, handoffs, artifact
writing, scorers, verdict -- and a JUDGMENT layer only a model can produce. The
first is provable offline at ~zero cost; three consecutive paid runs were each
stopped by a different deterministic cause, and one offline pass would have
found all three. This is that pass, and it is meant to be rerun before every
paid campaign.

Every `claude` invocation in the chain -- the liveness ping, the per-arm
headroom probe, and the timed delivery itself -- resolves to `inert_claude.py`
through a PATH shim this probe stages and then
VERIFIES by resolution, never by assumption. Zero provider calls, verified by a
ledger every shim invocation appends to.

## READ THIS BEFORE RERUNNING -- three facts, in this order

1. This probe is a bench for the CHAIN, NEVER for nWave's COST. The inert
   runner REMOVES the treatment mechanism, so there is no cost left to
   measure here.
2. The treatment is real and was measured on the PAID campaign, not here.
   nWave arm: 28 successful hook fires (14 of one kind + 14 of another)
   plus 14 context injections. Control arm: zero and zero, and it does not
   carry the hook configuration file at all, while the nWave arm does.
   Offline both arms read zero BY CONSTRUCTION -- an offline zero is not a
   refutation of the treatment, it is its absence.
3. Most important: the ratios this probe reports are DESIGNED, not
   measured. The factors are literal values inside the inert runner
   (`inert_claude._ARM_FACTORS`). The verdict agreeing with them proves the
   chain COMPUTES correctly; it says nothing about what nWave costs. Read
   without this line, those numbers look like a measurement. They are not.

## The stages, and what each one must produce

| stage      | runs                                   | must produce                    |
|------------|----------------------------------------|---------------------------------|
| shims      | stages `claude` -> `inert_claude.py`   | bin/claude, resolvable first    |
| mirror     | `git clone --mirror` of the real SUT   | a mirror carrying the real pin  |
| preflight  | `preflight.main`, `_SUT` -> mirror     | `arms.json`                     |
| campaign   | `paired_campaign.main`                 | `campaign.json`, pair payloads  |
| acceptance | `run_acceptance.main`                  | `verdicts.json`                 |
| seal       | `blind_review seal`                    | packets + the sealed map        |
| score      | the INERT reviewer (see `_score`)      | `scored.json`                   |
| unseal     | `blind_review unseal`                  | `rubric.json`                   |
| verdict    | `admission_verdict.main --json`        | `admission.json`                |

## Where this probe is SIMPLER than a paid campaign

Named here because these are exactly the things it does NOT prove:

1. **The entire judgment layer.** No model reasons about anything. The rubric
   scores come from a hash of the sealed packet (`_score`), so the quality axis
   exercises the join, the shape validation and the ordering arithmetic -- and
   says nothing whatever about delivery quality.
2. **The SUT is cloned from a LOCAL MIRROR of the real remote**, not from the
   remote itself. Objects, history and the pinned revision are the real ones --
   what is not exercised is the network clone and its failure modes.
3. **The delivery diff is fixed and does not implement the feature**, so the
   hidden acceptance oracle is expected to REJECT both arms. That exercises
   `Delivery.DELIVERED_REJECTED`; it does not exercise
   `DELIVERED_ACCEPTED`, and the quality GATE therefore reads BREACH for a
   reason that is a property of this probe, not of any arm.
4. **Both arms are the same inert runner.** A real campaign's arms differ in
   what nWave does to the delivery; here they differ only in the fixed
   multipliers `inert_claude._ARM_FACTORS` applies, so the ratios are designed,
   not measured. What is proved is that the chain COMPUTES a ratio from
   artifacts it produced and compares it against the bound.
5. **Both arms reach the same inert delivery.** The arms differ in a setup step
   (`preflight.TREATMENT_INSTALL_STEP`), not in what they invoke, so offline the
   inert runner answers both the same way. What that proves is the CHAIN over
   two comparable payloads; it does not exercise the DES step loop, because the
   inert agent invokes no `des` command. The step loop is proved separately and
   at zero spend by
   `tests/scripts/analysis/test_k4_inert_replay_drives_the_real_runner.py`,
   which walks `des state` -> `po` -> `design` -> `oracle` -> `craft` ->
   `verify` by following each step's own `NEXT` line against recorded envelopes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analysis.k4 import (  # noqa: E402
    admission_verdict,
    inert_claude,
    quality_rubric,
)
from scripts.analysis.k4 import preflight as k4_preflight  # noqa: E402
from scripts.analysis.k4 import subject as k4_subject  # noqa: E402


STAGES = (
    "shims",
    "mirror",
    "preflight",
    "campaign",
    "acceptance",
    "seal",
    "score",
    "unseal",
    "verdict",
)

_SHIM_SOURCE = '''#!/usr/bin/env python3
"""Generated by offline_chain_probe.py -- resolves `claude` to the inert runner."""
import runpy
import sys

sys.argv[0] = "claude"
runpy.run_path({target!r}, run_name="__main__")
'''

_PREFLIGHT_BOOTSTRAP = '''#!/usr/bin/env python3
"""Generated by offline_chain_probe.py.

`preflight._SUT` is a module attribute precisely so a caller can point it at a
local throwaway repo without reaching into `subject.py` (see its own docstring).
The PIN is left untouched: the mirror carries the real commit, so
`_base_commit_sha`, `git archive` and the detach step all run against the real
subject state -- the fidelity point this probe would otherwise lose.
"""
import sys

sys.path.insert(0, {repo!r})

from scripts.analysis.k4 import preflight

preflight._SUT = {sut!r}
raise SystemExit(preflight.main(sys.argv[1:]))
'''


@dataclass
class StageResult:
    name: str
    status: str
    seconds: float
    detail: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


#: What an all-PASS run of this probe does NOT establish, printed beside the
#: greens every time and carried in the report. A chain that is green on what it
#: can reach, and silent about what it cannot, is read as a chain that measured
#: everything -- and this probe exists precisely so nobody spends a paid
#: campaign on a false reading.
NOT_COVERED = (
    "the ratio axes. The inert delivery does not implement the feature, so the "
    "hidden oracle rejects BOTH arms, the pair is correctly excluded, and cost "
    "/ tokens / wall stay INDETERMINATE. A green here is the chain computing, "
    "never a measured ratio.",
    "the DES step loop. Offline the inert agent invokes no `des` command, so "
    "the nWave arm exercises the harness and not the steps. The step loop is "
    "proved separately at zero spend by "
    "tests/scripts/analysis/test_k4_inert_replay_drives_the_real_runner.py.",
    "the judgment layer. Rubric scores come from a hash of the sealed packet, "
    "so the quality axis exercises the join and the arithmetic and says nothing "
    "about delivery quality.",
)


def _log(message: str) -> None:
    print(message, flush=True)


def _run(
    argv: list[str], *, cwd: Path, log_path: Path, timeout: int
) -> tuple[int, str]:
    """One stage subprocess, its whole output persisted, its tail returned."""
    started = time.monotonic()
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(argv)}\n\n")
        handle.flush()
        try:
            done = subprocess.run(
                argv,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            code = done.returncode
        except subprocess.TimeoutExpired:
            handle.write(f"\nTIMEOUT after {timeout}s\n")
            code = 124
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-2500:]
    _log(f"    ({time.monotonic() - started:.0f}s, exit {code}) log: {log_path}")
    return code, tail


# --- stage: shims ------------------------------------------------------------


def stage_shims(root: Path) -> StageResult:
    """Stage the inert `claude` and PROVE it is what PATH resolves.

    Proving it by resolution rather than by "we prepended the directory" is
    the difference between a claim about intent and a claim about the property
    the chain will actually act on: every consumer resolves `claude` off PATH
    at spawn time, so PATH resolution IS the fact.
    """
    started = time.monotonic()
    bin_dir = root / "inert-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = Path(inert_claude.__file__).resolve()
    shim = bin_dir / "claude"
    shim.write_text(_SHIM_SOURCE.format(target=str(target)), encoding="utf-8")
    shim.chmod(0o755)

    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    ledger = root / "inert-claude-ledger.jsonl"
    ledger.touch()
    os.environ["K4_INERT_CLAUDE_LEDGER"] = str(ledger)

    problems: list[str] = []
    resolved = shutil.which("claude")
    if resolved is None or Path(resolved).resolve() != shim.resolve():
        problems.append(f"PATH resolves `claude` to {resolved}, not the shim {shim}")
    missing = k4_preflight.missing_sandbox_prerequisites()
    if missing:
        problems.append(f"still missing on PATH after staging: {missing}")

    # The shim must actually run, right here, before a stage depends on it.
    done = subprocess.run(
        [str(shim), "-p", "Reply with exactly: OK", "--output-format", "json"],
        capture_output=True,
        text=True,
        cwd=root,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    try:
        probe = json.loads(done.stdout)
    except json.JSONDecodeError:
        probe = {}
        problems.append(f"the shim did not emit JSON: {done.stdout[:200]!r}")
    if probe.get("result") != "OK":
        problems.append(f"the shim's ping answered {probe.get('result')!r}")

    return StageResult(
        "shims",
        "FAIL" if problems else "PASS",
        time.monotonic() - started,
        "; ".join(problems),
        {"bin": str(bin_dir), "ledger": str(ledger), "shim": str(shim)},
    )


# --- stage: mirror -----------------------------------------------------------


def stage_mirror(root: Path, cache: Path) -> StageResult:
    """A local `--mirror` of the real SUT, carrying the real pinned revision."""
    started = time.monotonic()
    if not (cache / "HEAD").is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        code, tail = _run(
            ["git", "clone", "--mirror", k4_subject.SUT_URL, str(cache)],
            cwd=root,
            log_path=root / "logs" / "mirror.log",
            timeout=1800,
        )
        if code != 0:
            return StageResult(
                "mirror", "FAIL", time.monotonic() - started, tail[-400:]
            )
    pinned = subprocess.run(
        ["git", "cat-file", "-t", k4_subject.SUT_PINNED_REV],
        cwd=cache,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if pinned.stdout.strip() != "commit":
        return StageResult(
            "mirror",
            "FAIL",
            time.monotonic() - started,
            f"the mirror does not carry the pin {k4_subject.SUT_PINNED_REV}: "
            f"{pinned.stdout.strip() or pinned.stderr.strip()}",
        )
    return StageResult(
        "mirror",
        "PASS",
        time.monotonic() - started,
        f"pin {k4_subject.SUT_PINNED_REV} present",
        {"mirror": str(cache)},
    )


# --- stage: preflight --------------------------------------------------------


def stage_preflight(
    root: Path,
    mirror: Path,
    wheel: Path | None,
    wall_clock_minutes: int,
    checkout: Path,
) -> StageResult:
    """`preflight.main` -- the SAME producer the paid campaign runs.

    `checkout` is the nwave-dev tree the nWave arm's wheel is BUILT from, and
    `preflight.resolve_clean_commit_sha` refuses a dirty one so provenance
    binds to an exact SHA. It is a parameter rather than `REPO_ROOT` because
    on a shared box the working checkout is routinely dirty with other lanes'
    uncommitted work and `git stash` is banned: without this, the probe is
    unrunnable there for a reason that has nothing to do with the chain.
    Point it at a clean clone of the commit under test.
    """
    started = time.monotonic()
    bootstrap = root / "_preflight_bootstrap.py"
    bootstrap.write_text(
        _PREFLIGHT_BOOTSTRAP.format(repo=str(REPO_ROOT), sut=str(mirror)),
        encoding="utf-8",
    )
    argv = [
        sys.executable,
        str(bootstrap),
        "--root",
        str(root / "preflight"),
        "--checkout",
        str(checkout),
        "--task-file",
        str(Path(k4_preflight.__file__).resolve().parent / "task.txt"),
        "--wall-clock-minutes",
        str(wall_clock_minutes),
    ]
    if wheel is not None:
        argv += ["--wheel", str(wheel)]
    code, tail = _run(
        argv, cwd=REPO_ROOT, log_path=root / "logs" / "preflight.log", timeout=5400
    )
    arms = root / "preflight" / "arms.json"
    if code != 0 or not arms.is_file():
        return StageResult(
            "preflight",
            "FAIL",
            time.monotonic() - started,
            f"exit {code}; arms.json {'present' if arms.is_file() else 'ABSENT'}. "
            + tail[-1200:],
        )
    return StageResult(
        "preflight",
        "PASS",
        time.monotonic() - started,
        "",
        {"arms": str(arms)},
    )


# --- stage: campaign ---------------------------------------------------------


def stage_campaign(root: Path, pairs: int) -> StageResult:
    started = time.monotonic()
    arms = root / "preflight" / "arms.json"
    out = root / "campaign"
    argv = [
        sys.executable,
        "-m",
        "scripts.analysis.paired_campaign",
        "--arms",
        str(arms),
        "--pairs",
        str(pairs),
        "--out",
        str(out),
        # The inert delivery returns in milliseconds; a 90-minute ceiling would
        # only hide a hang. Short enough to fail fast, long enough that the
        # per-arm SETUP (clone + fixture venv) is never the thing it cuts.
        "--timeout",
        "1800",
    ]
    code, tail = _run(
        argv, cwd=REPO_ROOT, log_path=root / "logs" / "campaign.log", timeout=10800
    )
    payloads = sorted(out.glob("pair-*/*.json"))
    delivered = [p for p in payloads if not p.stem.endswith(".setup")]
    ok = code == 0 and (out / "campaign.json").is_file() and len(delivered) == 2 * pairs
    return StageResult(
        "campaign",
        "PASS" if ok else "FAIL",
        time.monotonic() - started,
        ""
        if ok
        else f"exit {code}; {len(delivered)} delivery payloads for {pairs} pairs. "
        + tail[-1200:],
        {"campaign": str(out), "payloads": str(len(delivered))},
    )


# --- stage: acceptance -------------------------------------------------------


def stage_acceptance(root: Path, suite: Path) -> StageResult:
    started = time.monotonic()
    out = root / "verdicts.json"
    argv = [
        sys.executable,
        "-m",
        "scripts.analysis.k4.run_acceptance",
        "--campaign",
        str(root / "campaign"),
        "--suite",
        str(suite),
        "--out",
        str(out),
    ]
    code, tail = _run(
        argv, cwd=REPO_ROOT, log_path=root / "logs" / "acceptance.log", timeout=21600
    )
    if not out.is_file():
        return StageResult(
            "acceptance",
            "FAIL",
            time.monotonic() - started,
            f"exit {code}; no verdicts.json. " + tail[-1200:],
        )
    verdicts = json.loads(out.read_text(encoding="utf-8"))
    # `run_acceptance` exits 1 when a payload carries no session_id -- a real
    # failure. A REJECTED delivery is not one: this probe's inert arm is
    # expected to be rejected, and that is a computed verdict, not an error.
    return StageResult(
        "acceptance",
        "PASS" if verdicts else "FAIL",
        time.monotonic() - started,
        f"exit {code}; {len(verdicts)} session-keyed verdicts",
        {"verdicts": str(out)},
    )


# --- stage: seal / score / unseal -------------------------------------------


def stage_seal(root: Path) -> StageResult:
    started = time.monotonic()
    sealed = root / "sealed"
    map_path = root / "seal-map.json"
    if sealed.exists():
        shutil.rmtree(sealed)
    argv = [
        sys.executable,
        "-m",
        "scripts.analysis.blind_review",
        "seal",
        "--campaign",
        str(root / "campaign"),
        "--out",
        str(sealed),
        "--map",
        str(map_path),
    ]
    code, tail = _run(
        argv, cwd=REPO_ROOT, log_path=root / "logs" / "seal.log", timeout=3600
    )
    listing = sealed / "REVIEW-THESE.txt"
    ok = code == 0 and listing.is_file() and map_path.is_file()
    return StageResult(
        "seal",
        "PASS" if ok else "FAIL",
        time.monotonic() - started,
        "" if ok else f"exit {code}. " + tail[-1200:],
        {"sealed": str(sealed), "map": str(map_path)},
    )


def _score(packet: Path) -> dict:
    """The INERT reviewer: a rubric verdict derived from the packet's BYTES.

    Source-blind by construction and by ignorance -- it cannot see the arm, and
    it cannot see meaning either. Deriving the scores from a digest of the
    packet keeps two properties the downstream stages actually depend on: the
    verdict is shape-valid (`blind_review.validate_verdict_shape`), and two
    different deliveries score differently, so the quality ORDERING arithmetic
    in `admission_verdict.quality_axis` is exercised on a real delta rather
    than on a constant.
    """
    material = b"".join(
        path.read_bytes() for path in sorted(packet.iterdir()) if path.is_file()
    )
    digest = hashlib.sha256(material).digest()
    keys = sorted(quality_rubric.CRITERIA_KEYS, key=int)
    criteria = {}
    for index, key in enumerate(keys):
        score = digest[index % len(digest)] % 3
        criteria[key] = {
            "score": score,
            "evidence": (
                "INERT reviewer: score derived from the packet digest, not from "
                "judgment. This carries no opinion about the delivery."
            ),
        }
    return {
        "criteria": criteria,
        "total": sum(c["score"] for c in criteria.values()),
        "blocking_quality_findings": [],
        "summary": "INERT reviewer -- no judgment was performed.",
    }


#: An opaque delivery id is `sha256(f"{salt}:{session_id}")[:12]`
#: (`blind_review.opaque_id`): exactly twelve lowercase hex characters. This is
#: the ONLY token shape `REVIEW-THESE.txt` may carry in its id block.
_OPAQUE_ID_RE = re.compile(r"\A[0-9a-f]{12}\Z")


class ReviewListingError(RuntimeError):
    """`REVIEW-THESE.txt` did not have the shape `blind_review.seal` writes."""


def parse_review_listing(text: str) -> list[str]:
    """The opaque ids of `REVIEW-THESE.txt`, or a LOUD refusal.

    The file `blind_review.seal` writes is not a bare id list: it opens with two
    lines of instruction prose, then a blank line, then one id per line. This
    stage used to read it with `text.split()`, which whitespace-splits the WHOLE
    file -- so the very first token it tried to score was the word `One`, and the
    stage died looking for `deliveries/One`. The seal was correct all along; the
    reader was not.

    The obvious repair -- skip anything that does not resolve to a directory --
    is the WRONG one, and is the same defect class this probe exists to catch: a
    reader that silently drops what it does not understand turns a listing whose
    shape has drifted into a review of FEWER deliveries that still reports PASS.
    That is an axis present with a null ratio passing as green, one layer up.

    So: the shape is asserted, never inferred. Everything before the first blank
    line is the declared header block and must contain NO id; everything after it
    must be an id and NOTHING else. Any other byte is a refusal naming the line.
    """
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    separators = [index for index, line in enumerate(lines) if not line.strip()]
    if not separators:
        raise ReviewListingError(
            "WHAT: REVIEW-THESE.txt carries no blank line between its header prose\n"
            "      and its id block.\n"
            "WHY:  the header is where `blind_review.seal` states how to score; the\n"
            "      blank line is the only structural boundary telling a reader where\n"
            "      prose stops and ids start. Without it the reader must GUESS, and a\n"
            "      guessing reader either scores the word `One` or silently drops a\n"
            "      delivery -- this stage has already done the first.\n"
            "HOW:  `blind_review.seal` writes that blank line; if the file has none,\n"
            "      the writer changed and this parser must be changed with it. Re-seal\n"
            "      and compare against `blind_review.seal`'s own writer.\n"
            f"FILE: {len(lines)} non-blank line(s)"
            + (f", first is {lines[0]!r}\n" if lines else " -- the file is empty\n")
        )
    boundary = separators[0]
    header, body = lines[:boundary], lines[boundary + 1 :]

    problems: list[str] = []
    for offset, line in enumerate(header, start=1):
        if _OPAQUE_ID_RE.match(line.strip()):
            problems.append(
                f"line {offset}: {line.strip()!r} has the shape of an opaque id but "
                "sits in the header block, before the blank separator -- reading the "
                "body alone would silently drop this delivery"
            )
    ids: list[str] = []
    for offset, line in enumerate(body, start=boundary + 2):
        token = line.strip()
        if not token:
            problems.append(
                f"line {offset}: blank line inside the id block; the block is one id "
                "per line with no gaps"
            )
        elif not _OPAQUE_ID_RE.match(token):
            problems.append(
                f"line {offset}: {token!r} is not an opaque id (expected exactly 12 "
                "lowercase hex characters, `blind_review.opaque_id`)"
            )
        elif token in ids:
            problems.append(f"line {offset}: {token!r} is listed twice")
        else:
            ids.append(token)
    if not ids and not problems:
        problems.append(
            "the id block is empty: scoring nothing produces a review that looks "
            "conducted"
        )
    if problems:
        raise ReviewListingError(
            "WHAT: REVIEW-THESE.txt does not have the shape `blind_review.seal`\n"
            "      writes.\n"
            + "".join(f"      - {problem}\n" for problem in problems)
            + "WHY:  this reader REFUSES rather than skips. Skipping the lines it does\n"
            "      not understand is how a listing of six ids becomes a review of\n"
            "      five that still reports PASS -- an axis present with nothing\n"
            "      behind it, which is the exact defect class this probe exists to\n"
            "      catch.\n"
            "HOW:  the id block is `blind_review.seal`'s own output; if it changed\n"
            "      shape, change it there and change this parser with it. Do not\n"
            "      loosen this parser to make one bad file pass.\n"
        )
    return ids


def stage_score(root: Path) -> StageResult:
    started = time.monotonic()
    sealed = root / "sealed"
    listing = sealed / "REVIEW-THESE.txt"
    if not listing.is_file():
        return StageResult("score", "FAIL", time.monotonic() - started, f"no {listing}")
    try:
        opaque_ids = parse_review_listing(listing.read_text(encoding="utf-8"))
    except ReviewListingError as exc:
        return StageResult("score", "FAIL", time.monotonic() - started, str(exc))

    # The count check the previous reader could not make: the ids the listing
    # names and the packets on disk are ONE set, not two that happen to overlap.
    # A listing naming a packet that is absent is a review that cannot be
    # conducted; a packet no listing names is a delivery that would be reviewed
    # by nobody and never noticed.
    deliveries = sealed / "deliveries"
    on_disk = (
        {path.name for path in deliveries.iterdir() if path.is_dir()}
        if deliveries.is_dir()
        else set()
    )
    listed = set(opaque_ids)
    if listed != on_disk:
        return StageResult(
            "score",
            "FAIL",
            time.monotonic() - started,
            f"WHAT: REVIEW-THESE.txt names {len(listed)} id(s); {deliveries} holds "
            f"{len(on_disk)} packet(s), and the two sets differ.\n"
            f"      - listed with no packet: {sorted(listed - on_disk)}\n"
            f"      - packet with no listing: {sorted(on_disk - listed)}\n"
            "WHY:  a delivery no listing names is reviewed by nobody, and nothing\n"
            "      downstream would report its absence.\n"
            "HOW:  re-run the `seal` stage; both files are written by the same\n"
            "      `blind_review.seal` call and cannot legitimately disagree.\n",
        )

    scored: dict[str, dict] = {}
    for opaque in opaque_ids:
        scored[opaque] = _score(deliveries / opaque)
    out = root / "scored.json"
    out.write_text(json.dumps(scored, indent=1) + "\n", encoding="utf-8")
    from scripts.analysis import blind_review

    problems = blind_review.validate_verdict_shape(scored)
    return StageResult(
        "score",
        "FAIL" if problems else "PASS",
        time.monotonic() - started,
        "; ".join(problems[:5]) if problems else f"{len(scored)} inert verdicts",
        {"scored": str(out)},
    )


def stage_unseal(root: Path) -> StageResult:
    started = time.monotonic()
    out = root / "rubric.json"
    argv = [
        sys.executable,
        "-m",
        "scripts.analysis.blind_review",
        "unseal",
        "--sealed",
        str(root / "seal-map.json"),
        "--verdicts",
        str(root / "scored.json"),
        "--out",
        str(out),
    ]
    code, tail = _run(
        argv, cwd=REPO_ROOT, log_path=root / "logs" / "unseal.log", timeout=600
    )
    ok = code == 0 and out.is_file()
    return StageResult(
        "unseal",
        "PASS" if ok else "FAIL",
        time.monotonic() - started,
        "" if ok else f"exit {code}. " + tail[-1200:],
        {"rubric": str(out)},
    )


# --- stage: verdict ----------------------------------------------------------

#: The axes `admission_verdict` computes a RATIO for. `quality` is deliberately
#: absent: it is not a ratio and has no bound (`admission_verdict.QualityAxis`),
#: so demanding a number from it would be a category error.
RATIO_AXES = ("cost", "tokens", "wall")


def axes_of(computed: dict) -> dict[str, dict]:
    """The axis rows of an `admission_verdict --json` document, keyed by name.

    `_as_dict` emits `axes` as a MAPPING name -> row (`admission_verdict.
    _as_dict`); this probe previously read a non-existent top-level `ratios`
    LIST and keyed it by a non-existent `axis` field, so `.get(...)` returned
    `[]` and every axis read as absent. A shape this stage merely GUESSES is
    the same class of defect this probe exists to catch, so the shape is
    asserted here rather than assumed: anything that is not a mapping yields
    no axes at all, and the caller reports every axis uncomputed.
    """
    axes = computed.get("axes")
    if not isinstance(axes, dict):
        return {}
    return {name: row for name, row in axes.items() if isinstance(row, dict)}


def uncomputed_axes(axes: dict[str, dict]) -> list[str]:
    """Axes that carry NO number -- absent, or present with a null ratio.

    The second half is the point, and it outranks the shape fix. `ratio_axis`
    returns a row with `ratio=None` whenever every pair was excluded (no valid
    figure on either arm), and that row is still emitted under `axes`. A
    presence-only check therefore reads three axes, finds all three, and
    reports a verdict "with every axis carrying a number" when not one of them
    does -- a green that measured nothing. An axis is computed only when its
    `ratio` is an actual number; `None`, a string, or a bool is not one.
    """
    uncomputed = []
    for name in RATIO_AXES:
        row = axes.get(name)
        if row is None:
            uncomputed.append(f"{name}(absent)")
            continue
        ratio = row.get("ratio")
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
            uncomputed.append(f"{name}(ratio={ratio!r})")
    return uncomputed


def unevaluated_arms(computed: dict) -> list[str]:
    """Arms whose delivery outcome was never ESTABLISHED, named `pair-N/arm`.

    THE PROPERTY THIS STAGE ACTUALLY DECIDES ON, and the reason it is not "does
    every axis carry a number". MEASURED 2026-09-06: with both arms running, the
    inert delivery is rejected on both sides -- the diff is fixed and does not
    implement the feature, exactly as this module's own limit 3 says -- so
    `admission_verdict` correctly excludes the pair and every axis is
    INDETERMINATE. A criterion demanding a number could therefore NEVER pass
    while the delivery stays inert, which makes it a criterion about the fixture
    rather than about the chain.

    What separates a working chain from a broken one is in the report as data:
    an arm reading `NOT_RUN` or `UNSCORED` (`admission_verdict.UNEVALUATED`) is
    an arm that produced no evidence, which is a chain defect; `DELIVERED_
    REJECTED` on both arms is the chain having produced a finding. Both shapes
    were observed on this box within one hour, so the discriminator is not
    hypothetical.

    A report carrying no `deliveries` block at all is treated as unevaluated
    rather than as clean: an absent measurement is not a passing one.
    """
    rows = computed.get("deliveries")
    if not isinstance(rows, list) or not rows:
        return ["deliveries(absent)"]
    unevaluated = {item.value for item in admission_verdict.UNEVALUATED}
    named: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            named.append("deliveries(malformed)")
            continue
        for arm in ("nwave", "control"):
            if row.get(arm) in unevaluated:
                named.append(f"pair-{row.get('pair')}/{arm}={row.get(arm)}")
    return named


def stage_verdict(root: Path) -> StageResult:
    """The admission verdict, COMPUTED on this chain's own artifacts.

    A nonzero exit is NOT a stage failure here: `admission_verdict` exits 1 on
    a BREACH and 2 on INDETERMINATE, and this probe's designed wall factor
    breaches deliberately. The stage's own question is narrower and is the one
    the mandate asks: did the chain PRODUCE the evidence a verdict is computed
    from, on every arm of every pair?

    Nothing here reads or moves a bound. `admission_verdict` owns the
    thresholds and the exclusion rule; this stage only asks whether it was
    given something to decide on.
    """
    started = time.monotonic()
    out = root / "admission.json"
    argv = [
        sys.executable,
        "-m",
        "scripts.analysis.k4.admission_verdict",
        "--campaign",
        str(root / "campaign"),
        "--verdicts",
        str(root / "verdicts.json"),
        "--rubric",
        str(root / "rubric.json"),
        "--json",
    ]
    log_path = root / "logs" / "verdict.log"
    with open(log_path, "w", encoding="utf-8") as handle:
        done = subprocess.run(
            argv,
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        handle.write(f"$ {' '.join(argv)}\n\nexit {done.returncode}\n")
        handle.write(done.stdout)
        handle.write(done.stderr)
    try:
        computed = json.loads(done.stdout)
    except json.JSONDecodeError:
        return StageResult(
            "verdict",
            "FAIL",
            time.monotonic() - started,
            f"exit {done.returncode}; stdout is not JSON: {done.stdout[:400]!r} "
            f"{done.stderr[-600:]}",
        )
    out.write_text(json.dumps(computed, indent=1) + "\n", encoding="utf-8")
    axes = axes_of(computed)
    unevaluated = unevaluated_arms(computed)
    detail = f"verdict={computed.get('verdict')} exit={done.returncode} " + " ".join(
        f"{name}={axes[name].get('ratio')}({axes[name].get('status')})"
        for name in sorted(axes)
    )
    deliveries = computed.get("deliveries")
    if isinstance(deliveries, list):
        detail += " deliveries=" + " ".join(
            f"p{row.get('pair')}:nwave={row.get('nwave')},control={row.get('control')}"
            for row in deliveries
            if isinstance(row, dict)
        )
    # Still REPORTED, no longer the pass criterion: which axes carry no number
    # is what a reader wants to see, and `uncomputed_axes` keeps intercepting
    # the presence-only false green its own tests pin. What it cannot do is
    # decide this stage, because an inert delivery can never be accepted.
    uncomputed = uncomputed_axes(axes)
    if uncomputed:
        detail += f" -- axes without a number {uncomputed}"
    if unevaluated:
        detail += f" -- ARMS WITH NO ESTABLISHED OUTCOME {unevaluated}"
    if not axes:
        detail += " -- NO AXES IN THE REPORT"
    return StageResult(
        "verdict",
        "FAIL" if unevaluated or not axes or not computed.get("verdict") else "PASS",
        time.monotonic() - started,
        detail,
        {"admission": str(out)},
    )


# --- ledger --------------------------------------------------------------


def spend_report(root: Path) -> dict:
    """What the inert runner was asked to do, and by whom. The evidence that
    no provider call happened is this ledger PLUS the resolution check in
    `stage_shims` -- a claim of zero spend with neither is just a promise."""
    ledger = root / "inert-claude-ledger.jsonl"
    records = []
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    by_kind: dict[str, int] = {}
    for record in records:
        by_kind[record["kind"]] = by_kind.get(record["kind"], 0) + 1
    return {
        "inert_invocations": len(records),
        "by_kind": by_kind,
        "provider_calls": 0,
        "usd_spent": 0.0,
        "errors": [r for r in records if r.get("is_error")],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument(
        "--stages",
        default=",".join(STAGES),
        help=f"comma-separated subset of {','.join(STAGES)}",
    )
    parser.add_argument(
        "--mirror",
        type=Path,
        default=None,
        help="local --mirror clone of the SUT; created if absent "
        "(default <root>/../sut-mirror.git)",
    )
    parser.add_argument(
        "--checkout",
        type=Path,
        default=REPO_ROOT,
        help="the nwave-dev tree the nWave arm's wheel is built from; MUST be "
        "clean (preflight refuses a dirty tree so the wheel's provenance binds "
        "to an exact SHA). Default: this checkout.",
    )
    parser.add_argument("--wheel", type=Path, default=None)
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="attempt every requested stage even after one FAILs, instead of "
        "stopping at the first. The reason this probe exists is that THREE "
        "consecutive paid campaigns were each stopped by a DIFFERENT "
        "deterministic cause; a run that halts at the first defect surfaces "
        "one per pass and buys three passes' worth of latency to find three "
        "defects. A stage failing only because its input was never produced "
        "is not a second finding -- read the failures in stage order.",
    )
    parser.add_argument("--wall-clock-minutes", type=int, default=60)
    parser.add_argument(
        "--suite",
        type=Path,
        default=Path(__file__).resolve().parent / "acceptance_maintenance_windows.py",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    (root / "logs").mkdir(parents=True, exist_ok=True)
    mirror = (args.mirror or root.parent / "sut-mirror.git").resolve()
    requested = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in requested if s not in STAGES]
    if unknown:
        sys.stderr.write(
            f"WHAT: unknown stage(s) {unknown}.\n"
            f"WHY:  a typo would silently skip the stage it named.\n"
            f"HOW:  choose from {','.join(STAGES)}.\n"
        )
        return 2

    # `shims` is never optional: every later stage spawns `claude` off PATH, so
    # skipping it would run the REAL binary and spend money. Forced in, always.
    if "shims" not in requested:
        requested.insert(0, "shims")

    results: list[StageResult] = []
    for name in STAGES:
        if name not in requested:
            continue
        _log(f"--- stage {name} ---")
        if name == "shims":
            result = stage_shims(root)
        elif name == "mirror":
            result = stage_mirror(root, mirror)
        elif name == "preflight":
            result = stage_preflight(
                root,
                mirror,
                args.wheel,
                args.wall_clock_minutes,
                args.checkout.resolve(),
            )
        elif name == "campaign":
            result = stage_campaign(root, args.pairs)
        elif name == "acceptance":
            result = stage_acceptance(root, args.suite.resolve())
        elif name == "seal":
            result = stage_seal(root)
        elif name == "score":
            result = stage_score(root)
        elif name == "unseal":
            result = stage_unseal(root)
        else:
            result = stage_verdict(root)
        results.append(result)
        _log(f"    {result.status}: {result.detail[:400]}")
        if result.status == "FAIL":
            if not args.keep_going:
                _log(
                    f"\nSTOPPED at stage `{name}` -- the chain does not reach the "
                    "stages after it. That location IS the finding. Re-run with "
                    "--keep-going to collect every remaining deterministic defect "
                    "in ONE pass instead of one per pass."
                )
                break
            _log(
                f"\n--keep-going: stage `{name}` FAILED and the run CONTINUES. "
                "Every later stage now runs against an input this stage did not "
                "produce, so a later FAIL may be this one cascading rather than a "
                "second finding. Read the failures in stage order."
            )

    report = {
        "root": str(root),
        "pairs": args.pairs,
        "sut": {
            "url": k4_subject.SUT_URL,
            "pinned_rev": k4_subject.SUT_PINNED_REV,
            "mirror": str(mirror),
        },
        "keep_going": args.keep_going,
        "stages": [asdict(r) for r in results],
        "failed_stages": [r.name for r in results if r.status == "FAIL"],
        # Carried in the machine record too, not only printed: a consumer that
        # reads `failed_stages == []` and stops has read half the result.
        "not_covered": list(NOT_COVERED),
        "spend": spend_report(root),
    }
    (root / "offline-chain-probe.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8"
    )
    _log("\n=== offline chain probe ===")
    for result in results:
        _log(
            f"{result.status:5s} {result.name:11s} {result.seconds:7.0f}s {result.detail[:160]}"
        )
    _log(f"spend: {json.dumps(report['spend']['by_kind'])} inert invocations, USD 0.00")
    for line in NOT_COVERED:
        _log(f"NOT COVERED: {line}")
    _log(f"report: {root / 'offline-chain-probe.json'}")
    return 0 if all(r.status == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
