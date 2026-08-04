"""Composition root for dispatch-template-ssot-reconciliation slice-04
(dispatch-ref coherence gate).

DRIVING SURFACE (Core Principle 7 -- in-process is the DEFAULT; subprocess-e2e is
RESERVED for exactly one ``@walking_skeleton`` scenario per command):

  * Layer 2 in-process (DEFAULT, used by AT-2, both AT-3 variants, AT-4, AT-4b,
    AT-5) -- the real ``des.cli.verify_dispatch_ref_coherence.main(argv)`` entry
    called DIRECTLY (no interpreter fork), stdout/stderr captured via
    ``contextlib.redirect_stdout``/``redirect_stderr`` over ``io.StringIO()``.
    Mirrors the in-process active-RED pattern in
    ``tests/des/acceptance/at_in_process_port_default/steps/composition.py``
    (P1-P4): the module is imported LAZILY, inside the When method, never at
    module top -- importing the absent name at collection time would raise
    ``ImportError`` during COLLECTION (a BROKEN test), not active-RED.

  * Layer 3 subprocess (RESERVED, used by exactly two scenarios):
      - AT-1 (``@walking_skeleton``) -- the ONE scenario per feature that proves
        ``des verify-dispatch-ref-coherence`` is wired end-to-end through the
        REAL installed ``des`` dispatcher (``python -m des <sub>``), not just
        importable. This is the wiring proof in-process cannot give: an
        in-process call bypasses argv parsing, subcommand registration, and the
        installed entry point entirely.
      - AT-6 (git-absent-from-PATH) -- STAYS on subprocess because the property
        under test is OS-level PATH lookup by a child process. An in-process
        call runs inside THIS interpreter's already-resolved process image; it
        cannot exercise "does the gate itself spawn a child that fails to find
        `git` on PATH" without spawning that child for real. Subprocess is the
        only surface that can observe this property at all.

  Both surfaces read two real on-disk artifacts -- the target SKILL file
  (markdown, carrying the ``dispatch-ref`` pointer) and the real
  ``nWave/dispatch/atdd_pure.yaml`` dispatch registry -- and emit a §17
  ``GateVerdict`` token on JSON-stdout (the five existing verdicts, no sixth).
  The observable is that verdict token. Mandate-14 @real-io: real filesystem
  reads on both surfaces; AT-1/AT-6 additionally spawn a real OS subprocess --
  those two ATs would fail if the dispatcher or the registry file were absent.

No production module is imported-and-called at the step boundary for its
business logic on EITHER surface -- in-process calls reach only the stable
``main`` entry point (never internals), subprocess calls reach only the
installed CLI. The fixture authoring below sets up PRECONDITIONS (the
skill-file INPUT + the process environment), never the expected OUTPUT verdict
(Critical Rule 7 -- no fixture theater; the verdict is the SUT's own emission,
not a value the test fabricated).

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the design's §4 component
decomposition declares the load-bearing net-new seam:

  ``src/des/cli/verify_dispatch_ref_coherence.py`` -- a new ``des`` CLI module +
  its ``_SubcommandRow`` registration in ``src/des/cli/__main__.py`` (mirroring
  ``verify-wave-contract-coherence``'s registration in that same table). Each
  slice-04 AT NAMES that subcommand seam and drives it through a REAL surface
  (in-process function call or the installed dispatcher), asserting an
  observable effect (the emitted verdict token) -- never a name/protocol match.

CONTRACT THIS AT SET DEFINES (the gate does not exist yet -- these ATs are the
executable spec the crafter implements against, induced from design Decision 5 +
§4/§7 slice-04 row):

  * Module: ``des.cli.verify_dispatch_ref_coherence`` exposing
    ``main(argv: list[str] | None = None) -> int``.
  * CLI: ``des verify-dispatch-ref-coherence --skill <path> --dispatch-yaml <path>``
    (``--dispatch-yaml`` optional, default ``nWave/dispatch/atdd_pure.yaml``).
  * Pointer marker: a single HTML-comment anchor carrying the pointed-at
    ``mode``/``lane`` PAIR -- ``<!-- dispatch-ref: mode=<mode> lane=<lane> -->`` --
    the "anchor pair" the feature-delta names. ``mode`` resolves against the
    registry's top-level ``mode:`` key; ``lane`` resolves against a
    ``profiles.lane.<lane>:`` entry in the SAME registry (both real, shipped
    keys in ``nWave/dispatch/atdd_pure.yaml`` -- cited by KEY PATH, not line
    number, so the citation cannot rot when Slice 2 deletes fields around them:
    top-level ``mode:``, and ``profiles.lane.{prefactoring,bugfix,charter}:``).
  * Inline-restatement rule (concept reused from ``verify_wave_contract_coherence``
    Shape 3, NOT its list-diff algorithm per design Decision 5): >=2 CONSECUTIVE
    canonical dispatch section-id bullet items in the skill prose is the
    dispatch-content re-enumerated inline instead of pointed-at. A SINGLE
    section-id mention is explicitly NOT a restatement (AT-4b, the near-miss
    boundary) -- the rule triggers on the enumeration shape, not on naming one
    section in passing prose.
  * Output: one JSON line on stdout ``{"verdict": <token>, "diagnostic": <str>}``
    (mirrors ``verify_wave_contract_coherence.main`` verbatim).

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD
``src/des/cli/verify_dispatch_ref_coherence.py`` does NOT exist. Per-scenario RED
reason (stated plainly, per the reviewer's ask -- the two surfaces fail
DIFFERENTLY):

  * AT-1, AT-6 (subprocess): the installed ``des`` dispatcher rejects the unknown
    subcommand at ARGV-PARSE time (``des: error: argument subcommand: invalid
    choice: 'verify-dispatch-ref-coherence'``, exit code 2) -- no JSON line is
    printed, so ``_parse_verdict`` returns ``None``, and
    ``then_gate_emits_verdict`` raises a semantic ``AssertionError`` naming the
    missing subcommand. This is a REAL subprocess exit, not a collection error.
  * AT-2, AT-3 (both variants), AT-4, AT-4b, AT-5 (in-process): the lazy
    ``from des.cli.verify_dispatch_ref_coherence import main`` INSIDE the When
    method raises ``ModuleNotFoundError`` (an ``ImportError`` subclass) at
    RUNTIME (never at collection -- the module-level imports above name only
    stdlib + the sibling gate's already-shipped parsing helpers). The When
    method catches it, records ``verdict=None`` with the exception text in
    ``stderr``, and the SAME ``then_gate_emits_verdict`` fires the identical
    semantic ``AssertionError`` for the identical reason (no verdict token
    emitted) -- just via a different failure inside the call, not a different
    Then assertion. Once DELIVER ships the module, both surfaces reach the same
    §17 ``GateVerdict`` emission and diverge only in HOW they reached it.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .domain_types import DispatchRefVerdict


# tests/des/acceptance/dispatch_ref_coherence_gate/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The operator-visible dispatch-ref coherence subcommand (the DESIGN-declared
# net-new seam, design §4/§7 slice-04 row). Driven as the REAL `des <sub>` kebab
# dispatch (AT-1/AT-6 only -- see module docstring).
_GATE_SUBCOMMAND = "verify-dispatch-ref-coherence"

# The REAL, shipped dispatch registry the gate must resolve mode/lane against --
# NOT a hand-rolled stub (mirrors the sibling gate copying the real DISCUSS
# registry). A precondition input, never the expected output.
_DISPATCH_YAML = REPO_ROOT / "nWave" / "dispatch" / "atdd_pure.yaml"

# A real, shipped lane name that resolves in `_DISPATCH_YAML`
# (`profiles.lane.bugfix:` key path) -- used for the well-formed / PASS-shaped
# fixtures.
_RESOLVABLE_LANE = "bugfix"

# A lane name verified ABSENT from `_DISPATCH_YAML`'s `profiles.lane.*` keys --
# the unresolvable-lane FAIL case (Property 3).
_UNRESOLVABLE_LANE = "not-a-real-lane"

# A mode name verified ABSENT from `_DISPATCH_YAML`'s top-level `mode:` key
# (which is `atdd_pure`, singular) -- the unresolvable-mode FAIL case (Property 3
# variant).
_UNRESOLVABLE_MODE = "not-a-real-mode"

# Two REAL, consecutive canonical dispatch section ids (`_DISPATCH_YAML`'s
# `sections:` key path -- cited by key, not line number, so the citation cannot
# rot when fields around it are deleted/reordered) -- restating BOTH as a bullet
# list is the inline-restatement drift surface (Property 4), reusing the
# `verify_wave_contract_coherence` Shape-3 concept (>=2 consecutive bare-id
# bullet items), not its list-diff algorithm (design Decision 5).
_RESTATED_SECTION_ID = "DES_METADATA"
_RESTATED_SECTION_ID_2 = "AGENT_IDENTITY"

# The near-miss boundary (MEDIUM finding): naming this SAME section id exactly
# ONCE, in passing prose (no bullet, no second id), must NOT trigger the
# restatement rule -- AT-4b.
_SINGLE_MENTION_SECTION_ID = _RESTATED_SECTION_ID


@dataclass(frozen=True)
class _GateInvocation:
    """The observable boundary DTO of one dispatch-ref-coherence gate run.

    ``verdict``    -- the §17 GateVerdict token parsed from JSON-stdout, or None
                      when the gate emitted no parseable verdict (the RED at
                      HEAD -- see module docstring for the per-channel reason).
    ``stdout`` / ``stderr`` / ``exit_code`` -- raw observables for diagnostics.
    ``channel``    -- ``"subprocess"`` or ``"in-process"``, so a diagnostic
                      states plainly which surface produced this observable.
    """

    verdict: str | None
    stdout: str
    stderr: str
    exit_code: int
    channel: str


@dataclass
class DispatchRefCoherenceComposition:
    """Drives the dispatch-ref-coherence gate through a REAL surface.

    Builds a real on-disk skill-file fixture under a per-scenario tmp dir, then
    invokes the gate either in-process (default) or via the installed `des`
    subprocess (AT-1 walking-skeleton + AT-6 git-boundary only), exposing the
    emitted verdict token for the Then assertions.
    """

    tmp_path: Path
    _skill_path: Path | None = field(default=None)
    _dispatch_yaml: Path = field(default=_DISPATCH_YAML)
    _env_overrides: dict[str, str] | None = field(default=None)
    _invocation: _GateInvocation | None = field(default=None)

    # ---- given: skill-file preconditions ------------------------------------

    def given_skill_with_valid_pointer_zero_restatement(self) -> None:
        """A skill file with a well-formed `dispatch-ref` pointer and ZERO
        inline restatement (Property 1 / Property 6's PASS-shaped fixture).

        Carries the `dispatch-ref` anchor naming a mode + lane that both
        resolve in the real `_DISPATCH_YAML`, and NARRATES intent only --
        no section-id enumeration.
        """
        self._skill_path = self.tmp_path / "nw-example-skill.md"
        self._skill_path.write_text(
            "# Example Skill\n\n"
            f"<!-- dispatch-ref: mode=atdd_pure lane={_RESOLVABLE_LANE} -->\n\n"
            "This skill delegates the bugfix dispatch template to the SSOT -- see "
            "`des dispatch --mode atdd_pure --lane bugfix` for the generated "
            "content. This prose narrates intent and restates neither the mode "
            "nor the lane's rendered sections inline.\n",
            encoding="utf-8",
        )

    def given_skill_with_no_pointer(self) -> None:
        """A skill file carrying NO `dispatch-ref` marker at all (Property 2)."""
        self._skill_path = self.tmp_path / "nw-example-skill.md"
        self._skill_path.write_text(
            "# Example Skill\n\n"
            "This skill talks about dispatch generally but carries no coherence "
            "pointer at all.\n",
            encoding="utf-8",
        )

    def given_skill_with_unresolvable_lane(self) -> None:
        """A `dispatch-ref` pointer naming a lane absent from `_DISPATCH_YAML`'s
        `profiles.lane.*` keys (Property 3)."""
        self._skill_path = self.tmp_path / "nw-example-skill.md"
        self._skill_path.write_text(
            "# Example Skill\n\n"
            f"<!-- dispatch-ref: mode=atdd_pure lane={_UNRESOLVABLE_LANE} -->\n\n"
            "This pointer names a lane that does not exist in the registry.\n",
            encoding="utf-8",
        )

    def given_skill_with_unresolvable_mode(self) -> None:
        """A `dispatch-ref` pointer naming a mode absent from `_DISPATCH_YAML`'s
        top-level `mode:` key (Property 3, mode variant)."""
        self._skill_path = self.tmp_path / "nw-example-skill.md"
        self._skill_path.write_text(
            "# Example Skill\n\n"
            f"<!-- dispatch-ref: mode={_UNRESOLVABLE_MODE} lane={_RESOLVABLE_LANE} -->\n\n"
            "This pointer names a mode that does not exist in the registry.\n",
            encoding="utf-8",
        )

    def given_skill_with_valid_pointer_and_inline_restatement(self) -> None:
        """A well-formed `dispatch-ref` pointer that ALSO inline-restates dispatch
        section bodies -- a bullet list of >=2 consecutive canonical section ids
        pasted verbatim instead of pointing (Property 4)."""
        self._skill_path = self.tmp_path / "nw-example-skill.md"
        self._skill_path.write_text(
            "# Example Skill\n\n"
            f"<!-- dispatch-ref: mode=atdd_pure lane={_RESOLVABLE_LANE} -->\n\n"
            "The dispatch renders these sections:\n"
            f"- {_RESTATED_SECTION_ID}\n"
            f"- {_RESTATED_SECTION_ID_2}\n",
            encoding="utf-8",
        )

    def given_skill_with_valid_pointer_and_single_section_mention(self) -> None:
        """A well-formed `dispatch-ref` pointer that mentions EXACTLY ONE
        canonical section id, in passing prose -- the near-miss boundary
        (AT-4b, MEDIUM finding). No bullet list, no second id: this must PASS,
        never trigger the restatement rule that `>=2 consecutive` items does."""
        self._skill_path = self.tmp_path / "nw-example-skill.md"
        self._skill_path.write_text(
            "# Example Skill\n\n"
            f"<!-- dispatch-ref: mode=atdd_pure lane={_RESOLVABLE_LANE} -->\n\n"
            f"This skill's identity block maps to the `{_SINGLE_MENTION_SECTION_ID}` "
            "section the dispatch renders -- named once, in passing, not "
            "enumerated.\n",
            encoding="utf-8",
        )

    def given_skill_path_that_does_not_exist(self) -> None:
        """Point the gate at an ABSENT skill file -- the unreadable case
        (Property 5)."""
        self._skill_path = self.tmp_path / "does-not-exist-nw-example-skill.md"

    # ---- given: process-environment preconditions ---------------------------

    def given_no_git_reachable_on_path(self) -> None:
        """Strip PATH down to a directory verified to contain no `git`
        executable -- proves the gate is filesystem+import only (Property 6):
        if the implementation ever shelled out to `git`, this environment makes
        that call raise/fail, and the gate must still emit its verdict. Requires
        the subprocess surface (see module docstring: AT-6 justification)."""
        self._env_overrides = {"PATH": "/nonexistent-bin-dir-no-git-here"}

    # ---- when: drive the REAL gate, subprocess surface (AT-1 WS + AT-6) -----

    def when_maintainer_runs_dispatch_ref_coherence_gate_via_installed_command(
        self,
    ) -> None:
        """Invoke the REAL ``des verify-dispatch-ref-coherence`` subprocess --
        RESERVED for AT-1 (``@walking_skeleton``, proves end-to-end dispatcher
        wiring) and AT-6 (git-absent-from-PATH, needs a real child process to
        observe PATH lookup). See module docstring for the reservation rationale
        -- every other scenario uses the in-process surface below.

        Drives the shipped ``des`` dispatcher (``python -m des <sub>``) over the
        staged skill file + the real dispatch registry, capturing
        stdout/stderr/exit. At HEAD the subcommand does not exist -> the
        dispatcher emits an ``invalid choice`` usage error and NO verdict token
        -> ``verdict`` is None (the RED; see module docstring's per-channel
        RED-reason statement).
        """
        assert self._skill_path is not None, (
            "a skill-file path must be staged (Given) before running the gate (When)"
        )
        argv = [
            sys.executable,
            "-m",
            "des",
            _GATE_SUBCOMMAND,
            "--skill",
            str(self._skill_path),
            "--dispatch-yaml",
            str(self._dispatch_yaml),
        ]
        env = dict(os.environ)
        if self._env_overrides is not None:
            env.update(self._env_overrides)
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
            env=env,
        )
        self._invocation = _GateInvocation(
            verdict=_parse_verdict(completed.stdout),
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            channel="subprocess",
        )

    # ---- when: drive the REAL gate, in-process surface (the default) -------

    def when_maintainer_runs_dispatch_ref_coherence_gate_in_process(self) -> None:
        """Invoke the REAL ``verify_dispatch_ref_coherence.main(argv)`` entry
        DIRECTLY, in-process -- the DEFAULT surface (Core Principle 7), used by
        every scenario except AT-1/AT-6 (see module docstring).

        LAZY import inside this method, NEVER at module top (P1 of the
        in-process active-RED pattern, ``at_in_process_port_default`` exemplar):
        the module does not exist at HEAD, so importing it here raises
        ``ModuleNotFoundError`` at RUNTIME inside this call -- caught below and
        recorded as ``verdict=None`` -- never a collection-time ``ImportError``
        that would make the test BROKEN instead of active-RED.
        """
        assert self._skill_path is not None, (
            "a skill-file path must be staged (Given) before running the gate (When)"
        )
        argv = [
            "--skill",
            str(self._skill_path),
            "--dispatch-yaml",
            str(self._dispatch_yaml),
        ]
        out, err = io.StringIO(), io.StringIO()
        exit_code = -1
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                # Lazy, in-method import -- absent at HEAD (see docstring above).
                from des.cli.verify_dispatch_ref_coherence import (
                    main,
                )
            except ImportError as exc:
                print(f"ModuleNotFoundError: {exc}", file=err)
            else:
                try:
                    exit_code = main(argv)
                except SystemExit as exc:
                    exit_code = int(exc.code) if isinstance(exc.code, int) else 2
        self._invocation = _GateInvocation(
            verdict=_parse_verdict(out.getvalue()),
            stdout=out.getvalue(),
            stderr=err.getvalue(),
            exit_code=exit_code,
            channel="in-process",
        )

    # ---- then: the emitted verdict token ------------------------------------

    def then_gate_emits_verdict(self, expected: DispatchRefVerdict) -> None:
        """The gate emitted the expected §17 verdict token on JSON-stdout.

        Seam-named oracle (Mandate-15): the observable is the verdict the REAL
        gate emits, on WHICHEVER surface this scenario uses (``inv.channel``
        names it). RED at HEAD on BOTH surfaces -- for two DIFFERENT reasons
        (module docstring's per-channel statement): subprocess sees the
        dispatcher's ``invalid choice`` usage error; in-process sees a lazy
        ``ModuleNotFoundError`` inside the When call. Either way ``verdict`` is
        None -> the SAME semantic AssertionError naming the missing module.
        """
        inv = self._require_invocation()
        assert inv.verdict is not None, (
            "the dispatch-ref coherence gate must emit a §17 GateVerdict token "
            f"on JSON-stdout via the {inv.channel!r} surface -- it emitted none. "
            "The gate does not exist yet: DELIVER slice-04 must ship "
            "src/des/cli/verify_dispatch_ref_coherence.py (+ its _SubcommandRow "
            "registration in src/des/cli/__main__.py for the subprocess surface). "
            f"{self._observed()}"
        )
        assert inv.verdict == expected.value, (
            f"the dispatch-ref coherence gate must emit the {expected.value!r} "
            f"verdict for this case; it emitted {inv.verdict!r}. {self._observed()}"
        )

    def then_missing_pointer_diagnostic_is_self_explaining(self) -> None:
        """The FAIL diagnostic for a missing `dispatch-ref` pointer names WHAT is
        missing, WHY it matters (point, don't restate), and HOW to fix it by
        running `des dispatch` -- never a manual repair (Property 2)."""
        inv = self._require_invocation()
        diagnostic = self._require_diagnostic()
        assert "dispatch-ref" in diagnostic, (
            "the FAIL diagnostic must name WHAT is missing -- the `dispatch-ref` "
            f"pointer itself; got diagnostic={diagnostic!r}. {self._observed()}"
        )
        assert "des dispatch" in diagnostic, (
            "the FAIL diagnostic's HOW must name `des dispatch` as the producing "
            f"tool, never a manual repair; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )
        _ = inv

    def then_unresolvable_lane_diagnostic_is_self_explaining(self) -> None:
        """The FAIL diagnostic for an unresolvable lane names the offending lane
        value, WHY it matters, and HOW to fix it via `des dispatch` (Property 3)."""
        diagnostic = self._require_diagnostic()
        assert _UNRESOLVABLE_LANE in diagnostic, (
            "the FAIL diagnostic must name the unresolvable lane "
            f"{_UNRESOLVABLE_LANE!r} it found; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )
        assert "des dispatch" in diagnostic, (
            "the FAIL diagnostic's HOW must name `des dispatch` as the producing "
            f"tool, never a manual repair; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )

    def then_unresolvable_mode_diagnostic_is_self_explaining(self) -> None:
        """The FAIL diagnostic for an unresolvable mode names the offending mode
        value, WHY it matters, and HOW to fix it via `des dispatch` (Property 3,
        mode variant)."""
        diagnostic = self._require_diagnostic()
        assert _UNRESOLVABLE_MODE in diagnostic, (
            "the FAIL diagnostic must name the unresolvable mode "
            f"{_UNRESOLVABLE_MODE!r} it found; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )
        assert "des dispatch" in diagnostic, (
            "the FAIL diagnostic's HOW must name `des dispatch` as the producing "
            f"tool, never a manual repair; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )

    def then_restatement_diagnostic_is_self_explaining(self) -> None:
        """The FAIL diagnostic for an inline restatement names the restated
        section id it found, WHY it matters, and HOW to fix it via `des dispatch`
        (Property 4)."""
        diagnostic = self._require_diagnostic()
        assert _RESTATED_SECTION_ID in diagnostic, (
            "the FAIL diagnostic must name the restated section body "
            f"{_RESTATED_SECTION_ID!r} it found; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )
        assert "des dispatch" in diagnostic, (
            "the FAIL diagnostic's HOW must name `des dispatch` as the producing "
            f"tool, never a manual repair; got diagnostic={diagnostic!r}. "
            f"{self._observed()}"
        )

    def then_indeterminate_diagnostic_names_missing_skill_file(self) -> None:
        """The INDETERMINATE diagnostic names the missing skill file (Property 5).

        Degrade-LOUD (Invariant 2): the refusal-to-decide must be VISIBLE -- the
        diagnostic states the skill file could not be read. RED at HEAD: no
        verdict, no diagnostic -> semantic AssertionError.
        """
        diagnostic = self._require_diagnostic()
        assert self._skill_path is not None
        assert (
            str(self._skill_path) in diagnostic or self._skill_path.name in diagnostic
        ), (
            "the INDETERMINATE diagnostic must name the missing skill file "
            f"({self._skill_path}) -- a LOUD refusal-to-decide, never a silent "
            f"pass; got diagnostic={diagnostic!r}. {self._observed()}"
        )

    # ---- helpers --------------------------------------------------------------

    def _require_invocation(self) -> _GateInvocation:
        assert self._invocation is not None, (
            "the dispatch-ref coherence gate must run (When) before asserting (Then)"
        )
        return self._invocation

    def _require_diagnostic(self) -> str:
        inv = self._require_invocation()
        diagnostic = _parse_diagnostic(inv.stdout)
        assert diagnostic is not None, (
            "the gate must emit a `diagnostic` string alongside its verdict on "
            f"JSON-stdout; it emitted none. {self._observed()}"
        )
        return diagnostic

    def _observed(self) -> str:
        inv = self._invocation
        channel = inv.channel if inv else None
        exit_code = inv.exit_code if inv else None
        stdout = repr(inv.stdout) if inv else None
        stderr = repr(inv.stderr) if inv else None
        return (
            f"gate_subcommand={_GATE_SUBCOMMAND!r}; channel={channel!r}; "
            f"skill={self._skill_path}; dispatch_yaml={self._dispatch_yaml}; "
            f"env_overrides={self._env_overrides}; "
            f"exit_code={exit_code}; stdout={stdout}; stderr={stderr}"
        )


def _parse_verdict(stdout: str) -> str | None:
    """Parse the ``verdict`` token from the gate's JSON-stdout line.

    The shipped gate-CLI convention (e.g. ``des verify-wave-contract-coherence``)
    prints one JSON line ``{"verdict": <token>, "diagnostic": <str>}``. Tolerate
    extra non-JSON lines (the dev-checkout freshness banner). Return None when no
    JSON line carries a verdict -- the RED at HEAD (neither surface emits one;
    see module docstring for the per-channel reason).
    """
    payload = _last_json_object(stdout)
    if payload is None:
        return None
    verdict = payload.get("verdict")
    return verdict if isinstance(verdict, str) else None


def _parse_diagnostic(stdout: str) -> str | None:
    """Parse the ``diagnostic`` string from the gate's JSON-stdout line."""
    payload = _last_json_object(stdout)
    if payload is None:
        return None
    diagnostic = payload.get("diagnostic")
    return diagnostic if isinstance(diagnostic, str) else None


def _last_json_object(stdout: str) -> dict[str, object] | None:
    """Return the last line of stdout that parses as a JSON object, else None."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
