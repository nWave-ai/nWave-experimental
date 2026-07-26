"""Witness for the identity->document leg of the flavor dispatcher.

The dispatcher used to fuse two questions in one body: *is this mode one this
build executes* (an IDENTITY question, answered against a registry) and *what
does its declaration compose* (a DOCUMENT question, answered by reading a file).
Separating them moved the registry guard into
`resolve_executable_flavor_path`, and moved composition behind
`compose_lifecycle_event`, which takes a `Path` and therefore CANNOT consult the
registry -- it is never handed an identity to consult it with.

That separation has a cost the design named out loud: the three synthetic
walking-skeleton scenarios (`demo_single`, `demo_block`, `demo_warn`) now drive
the document entry, so they stopped being witnesses for the identity leg. This
file is where that cost is paid. Without it the refactor would have LOOKED
green while quietly proving less than the suite proved before -- which is the
failure mode worth guarding against, because a narrowed suite reports the same
colour as an intact one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application.flavor_dispatcher import (
    ACTIVE_MODES,
    FlavorFileAbsent,
    FlavorNotExecutable,
    resolve_executable_flavor_path,
)


_RETIRED = "classic"


def _flavors_dir(tmp_path: Path, *flavor_ids: str) -> Path:
    d = tmp_path / "flavors"
    d.mkdir()
    for flavor_id in flavor_ids:
        (d / f"{flavor_id}.yaml").write_text("lifecycle_events: {}\n")
    return d


@pytest.mark.parametrize("flavor_id", sorted(ACTIVE_MODES))
def test_an_executable_identity_resolves_to_its_document(
    tmp_path: Path, flavor_id: str
) -> None:
    """Every mode the build declares executable resolves to its own file.

    Parametrised over the registry itself rather than over a hardcoded
    `"atdd_pure"`: a mode added to `ACTIVE_MODES` tomorrow is covered the moment
    it is added, without anyone remembering to extend this test. A literal here
    would have made the test agree with the registry only by coincidence.
    """
    flavors_dir = _flavors_dir(tmp_path, flavor_id)

    assert resolve_executable_flavor_path(flavor_id, flavors_dir) == (
        flavors_dir / f"{flavor_id}.yaml"
    )


def test_a_retired_identity_is_refused_before_any_file_is_read(
    tmp_path: Path,
) -> None:
    """A retired mode is refused on IDENTITY, even when its document exists.

    The file is deliberately PRESENT. If the guard were ordered after the read,
    or keyed on the file's existence rather than on the registry, this scenario
    would resolve happily and the retired mode would execute. Writing the file
    is what makes the assertion mean "refused because retired" instead of
    "refused because absent" -- two verdicts a weaker fixture cannot tell apart.
    """
    assert _RETIRED not in ACTIVE_MODES, (
        f"this witness assumes {_RETIRED!r} is retired; if it was reinstated, "
        "pick another retired identity rather than deleting the scenario"
    )
    flavors_dir = _flavors_dir(tmp_path, _RETIRED)

    with pytest.raises(FlavorNotExecutable) as caught:
        resolve_executable_flavor_path(_RETIRED, flavors_dir)

    message = str(caught.value)
    assert _RETIRED in message, (
        f"the refusal must name the identity it turned away; got {message!r}"
    )


def test_an_executable_identity_with_no_document_is_a_DIFFERENT_refusal(
    tmp_path: Path,
) -> None:
    """A missing file is reported as missing, never as "not executable".

    These two failures ask for opposite repairs: one says migrate off a retired
    mode, the other says restore a file for a mode that is perfectly current.
    Collapsing them into a single message would send a reader to migrate away
    from a mode that never needed migrating -- so the distinction is asserted on
    the TYPE, not on message wording that a later edit could drift.
    """
    executable = next(iter(sorted(ACTIVE_MODES)))
    empty_dir = tmp_path / "flavors"
    empty_dir.mkdir()

    with pytest.raises(FlavorFileAbsent) as caught:
        resolve_executable_flavor_path(executable, empty_dir)

    assert not isinstance(caught.value, FlavorNotExecutable), (
        "an absent document must not be reported as a retired identity"
    )
    assert str(empty_dir / f"{executable}.yaml") in str(caught.value), (
        "the refusal must name the path it looked at, so the reader can check "
        "whether the file or the directory is what is wrong"
    )


def test_both_refusals_remain_catchable_as_ValueError(tmp_path: Path) -> None:
    """Existing callers catching `ValueError` keep working after the split.

    The two new exception types earn their existence by being distinguishable;
    they must not earn it by breaking every caller that already handled the
    single `ValueError` this code used to raise. Both properties are worth
    holding at once, and only asserting them together shows they do not
    conflict.
    """
    flavors_dir = _flavors_dir(tmp_path, _RETIRED)
    executable = next(iter(sorted(ACTIVE_MODES)))

    with pytest.raises(ValueError):
        resolve_executable_flavor_path(_RETIRED, flavors_dir)
    with pytest.raises(ValueError):
        resolve_executable_flavor_path(executable, flavors_dir)
