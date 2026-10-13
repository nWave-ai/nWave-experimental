"""Live attestation runs portably without rewriting historical evidence.

Driving port: the existing supplied-attestation journey and its real DES CLI.
@contract-shape: real-io. The observer forwards every native call unchanged;
it reads the handover and caller context actually supplied to that call.
L-substitution-scope is a finite observation of one frozen fixture, not a
limit on future declaration counts. L-identity, L-bound and L-repeat retain
their existing assertions in the journey; versioning remains in its incumbent
exact-original-input oracle. No second prompt renderer or execution copy is
constructed here. Missing PATH support is observed through the same real CLI.
"""

from __future__ import annotations

import copy
import json
import shutil
from functools import reduce
from operator import getitem
from pathlib import Path

import pytest
from tests.des.acceptance.atd_prompt_dedup import (
    test_role_receives_lossless_facts as attestation,
)


LIVE_EXECUTABLE_PATHS = (
    *(
        ("values", value, "authority", "verification", command, 0)
        for value in range(3)
        for command in range(2)
    ),
    *(("shared_design", "design", "verification", command, 0) for command in range(2)),
)


def _assert_portable_live_attestation(tmp_path: Path, monkeypatch) -> None:
    frozen_bytes = (attestation.RUN5 / attestation.STATE).read_bytes()
    frozen_root = attestation.RUN5_ROOT.read_bytes()
    frozen = json.loads(frozen_bytes)
    real_native = attestation._native
    supplied_inputs = []

    def observe_native(args: list[str], *, process: bool = False):
        repository = Path(args[args.index("--repo-root") + 1]).resolve()
        root_context = Path(args[args.index("--root-context") + 1])
        if not root_context.is_absolute():
            root_context = repository / root_context
        supplied_inputs.append(
            (
                tuple(args),
                repository,
                json.loads((repository / attestation.STATE).read_bytes()),
                root_context.read_bytes(),
                process,
            )
        )
        return real_native(args, process=process)

    # This is an observer, not a stub: the incumbent retains all success,
    # exact-identity, prompt-fit and paired-render assertions over real output.
    with monkeypatch.context() as observer:
        observer.setattr(attestation, "_native", observe_native)
        attestation.ReceivingRoleJourney(
            tmp_path
        ).supplied_prompt_fits_attestation_and_repeats()

    assert supplied_inputs, (
        "WHAT: the attestation supplied no observable native input. "
        "WHY: a skipped journey cannot establish live executable portability. "
        "HOW: retain the existing real native prompt renders in the journey."
    )
    expected = copy.deepcopy(frozen)
    for path in LIVE_EXECUTABLE_PATHS:
        reduce(getitem, path[:-1], expected)[path[-1]] = "python3"

    for args, repository, live, root_context, process in supplied_inputs:
        executables = {
            path: reduce(getitem, path, live) for path in LIVE_EXECUTABLE_PATHS
        }
        assert executables == dict.fromkeys(LIVE_EXECUTABLE_PATHS, "python3"), (
            f"WHAT: live verification executables are {executables!r}; expected "
            "PATH python3 at every member of the eight declared live slots. "
            "WHY: machine-absolute interpreters make the frozen attestation "
            "depend on the originating workstation and fail in CI. "
            "HOW: derive a temporary driving copy and replace only the live "
            "verification executable elements with literal python3."
        )
        assert live == expected, (
            f"WHAT: live handover supplied to {args!r} differs from the frozen "
            "facts beyond the eight allowed executable substitutions. "
            "WHY: command arguments, historical receipt argv, locators and "
            "every other fact must retain their original meaning. "
            "HOW: restrict the driving-copy adaptation to those live argv[0] "
            "elements; never normalize receipts or derived identities."
        )
        assert repository.is_relative_to(tmp_path.resolve()), (
            f"WHAT: live attestation uses {repository}, not a temporary copy. "
            "WHY: the frozen original is read-only historical evidence. "
            "HOW: render from the journey's temporary driving repository."
        )
        assert root_context == frozen_root and process, (
            f"WHAT: native input for {repository} changed caller bytes or "
            f"bypassed the real process boundary (process={process}). "
            "WHY: portability must preserve the original caller context and "
            "actually exercise the native prompt consumer. "
            "HOW: supply the exact original caller bytes to the real CLI."
        )

    # Observe the complete declared invocation population, not an unbound count;
    # prompt-byte determinism and the size bound remain owned by the journey.
    expected_renders = [
        (role.value, position)
        for role, position in (
            (attestation.Role.DESIGNER, "1"),
            (attestation.Role.DESIGNER, "2"),
            (attestation.Role.DESIGNER, "3"),
            (attestation.Role.ARCHITECT, None),
        )
        for _ in range(2)
    ]
    actual_renders = [
        (
            args[args.index("--role") + 1],
            args[args.index("--value") + 1] if "--value" in args else None,
        )
        for args, *_ in supplied_inputs
    ]
    assert actual_renders == expected_renders, (
        f"WHAT: observed render population is {actual_renders!r}, expected "
        f"{expected_renders!r}. "
        "WHY: dropping a supplied role or repeat would weaken the attestation. "
        "HOW: retain both native renders for each of the three designer "
        "positions and the shared architect prompt."
    )

    # Keep real Git available for support admission while withholding Python;
    # the interpreter launching DES remains the incumbent's real interpreter.
    git_only_path = tmp_path / "git-only"
    git_only_path.mkdir()
    (git_only_path / "git").symlink_to(shutil.which("git"))
    with monkeypatch.context() as unavailable_path:
        unavailable_path.setenv("PATH", str(git_only_path))
        refused = real_native(list(supplied_inputs[0][0]), process=True)
    assert (
        refused.exit != 0
        and b"VerificationExecutableUnresolvable" in refused.stderr
        and b"python3" in refused.stderr
    ), (
        f"WHAT: missing PATH python3 yielded exit={refused.exit}, "
        f"stderr={refused.stderr!r}; expected an explicit executable refusal. "
        "WHY: portability does not authorize fallback or silent error acceptance. "
        "HOW: retain the native unresolvable-executable refusal naming python3."
    )
    assert (
        (attestation.RUN5 / attestation.STATE).read_bytes() == frozen_bytes
        and attestation.RUN5_ROOT.read_bytes() == frozen_root
    ), (
        "WHAT: frozen evidence changed during the live portability observations. "
        "WHY: the attestation promises exact original inputs, including on refusal. "
        "HOW: keep every adaptation confined to the temporary driving copy."
    )


@pytest.mark.acceptance
@pytest.mark.integration
def test_live_attestation_uses_path_python_and_preserves_frozen_evidence(
    tmp_path, monkeypatch
):
    """L-substitution-scope; inherited L-identity, L-bound and L-repeat."""
    _assert_portable_live_attestation(tmp_path, monkeypatch)
