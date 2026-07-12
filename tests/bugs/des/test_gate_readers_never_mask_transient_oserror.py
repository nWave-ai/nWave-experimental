"""Regression (GDP-6 silent-wrong): two gate readers swallow EVERY ``OSError``
and return ``None``, collapsing "genuinely absent/corrupt" and "the read
itself transiently failed" into the same silent value.

Charter: ``docs/feature/fix-gate-readers-never-mask-transient-oserror/
feature-delta.md``.

Found in ``src/des/cli/verify_wave_contract_coherence.py`` ``_read`` (~:322-328,
feeding ``_catalog_gate_ids`` ~:290-297) and
``src/des/cli/validate_feature_delta.py`` ``read_wave_output_contract``
(~:1382-1386). Both except tuples carry the bare ``OSError``:

    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return None

Since ``OSError`` is the superclass of every other member in the tuple, this
swallows EVERY resource-class failure (EMFILE, ENOMEM, EAGAIN...) alongside the
two named subtypes -- not just genuine absence/corruption. Under whole-tree
xdist load a transient resource error therefore surfaces as a FABRICATED
content-drift verdict:

* the coherence reader's catalog read fails transiently -> ``_catalog_gate_ids``
  returns an EMPTY set -> every genuine registry ``gate_id`` looks orphaned ->
  ``evaluate_coherence`` emits FAIL "orphan gate_id" for a catalog that is
  actually intact.
* the delta reader's registry read fails transiently -> ``read_wave_output_contract``
  returns ``None`` -> ``_run_require_registry_sections`` degrades to the
  "registry ... is unreadable (absent / garbled)" verdict for a registry that
  is actually intact.

Empirical anchor (2026-07-12, Rex RCA + mock-injection proof): 4 acceptance
tests failed ONLY in whole-tree runs with byte-identical diagnostics to an
injected EMFILE/ENOMEM; the files were valid and untouched (mtimes days old).

The fix direction (charter, NOT implemented here): narrow both except tuples to
``(FileNotFoundError, IsADirectoryError, UnicodeDecodeError)`` -- dropping the
bare ``OSError`` that shadows every other subtype. Any OTHER ``OSError`` then
propagates with its true errno (GDP-3: the WHAT/WHY becomes the real syscall
failure, never a fabricated drift story). Genuine absence, directory-in-place,
and undecodable content keep TODAY's behavior exactly (the two pins below).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default): the
REAL ``des verify-wave-contract-coherence`` / ``des validate-feature-delta``
CLI drivers (``main()``), captured via ``capsys`` -- mirrors the sibling
regression AT ``tests/bugs/des/test_doc_coherence_unreadable_loud.py``. Neither
driver wraps its evaluation in a top-level try/except, so a propagating
``OSError`` surfaces as a raised exception all the way to the caller -- the
witnesses assert on that raise.

Injection idiom (reused from the RCA probe, Rex): ``unittest.mock.patch.object
(Path, "read_text", ...)`` scoped by resolved-path identity to exactly the
target file -- every OTHER ``Path.read_text`` call (fixture plumbing, the
sibling file in the same directory) passes through to the real implementation
untouched, confirmed empirically before use here.
"""

from __future__ import annotations

import contextlib
import errno
import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from des.cli.validate_feature_delta import main as delta_main
from des.cli.verify_wave_contract_coherence import main as coherence_main


# tests/bugs/des/<this file> -> parents[3] = REPO_ROOT (mirrors the production
# constant's own derivation in verify_wave_contract_coherence.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_PATH = _REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"

_VALID_REGISTRY_TEXT = """\
wave: distill
gate_stack:
  gate-out:
    - gate_id: check-slice-at-completeness
      on_failure: block
output_contract:
  ref_sections:
    - id: Some Section
      grade: mandatory
"""

_VALID_PROSE_TEXT = """\
# DISTILL wave

<!-- gates-ref: distill -->
<!-- outputs-ref: distill -->

Some prose describing the wave.
"""

_UNDECODABLE_BYTES = b"\xff\xfe\x00bad-utf8-\x80\x81"


@contextlib.contextmanager
def _inject_oserror_on_read(target_path: Path, error: OSError) -> Iterator[None]:
    """Scope a bare-``OSError`` injection to exactly ``target_path``'s
    ``read_text`` call. Every OTHER ``Path.read_text`` call passes through to
    the real implementation unchanged (confirmed empirically: resolved-path
    identity, not object identity, so a fresh ``Path`` instance built for the
    same file still matches).
    """
    original_read_text = Path.read_text
    resolved_target = target_path.resolve()

    def _side_effect(self: Path, *args: object, **kwargs: object) -> str:
        if self.resolve() == resolved_target:
            raise error
        return original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(Path, "read_text", autospec=True, side_effect=_side_effect):
        yield


def _stdout_json(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip()
    line = out.splitlines()[-1]
    result: dict[str, object] = json.loads(line)
    return result


# ===========================================================================
# NEGATIVE WITNESS A -- coherence reader's catalog read (RED today)
# ===========================================================================


@pytest.mark.negative_at
def test_coherence_reader_never_fabricates_orphan_verdict_from_transient_oserror(
    tmp_path: Path,
) -> None:
    """A resource-class ``OSError`` (EMFILE) on the CATALOG read must propagate
    with its real errno visible -- never be swallowed into the fabricated
    "orphan gate_id" FAIL verdict.

    RED today: ``_read()`` catches the bare ``OSError``, returns ``None``,
    ``_catalog_gate_ids()`` yields an EMPTY set, and every genuine registry
    ``gate_id`` (a real, resolvable catalog entry) then looks orphaned --
    ``evaluate_coherence`` returns FAIL with no exception raised, so this
    ``pytest.raises`` block fails with "DID NOT RAISE" (RED for the right
    reason -- a semantic assertion failure, not a setup/collection error).
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    (waves_dir / "distill.yaml").write_text(_VALID_REGISTRY_TEXT, encoding="utf-8")
    prose = tmp_path / "distill-prose.md"
    prose.write_text(_VALID_PROSE_TEXT, encoding="utf-8")

    injected = OSError(errno.EMFILE, "Too many open files")
    argv = [
        "--wave",
        "distill",
        "--prose",
        str(prose),
        "--waves-dir",
        str(waves_dir),
    ]

    with _inject_oserror_on_read(_CATALOG_PATH, injected):
        with pytest.raises(OSError) as exc_info:
            coherence_main(argv)

    assert exc_info.value.errno == errno.EMFILE, (
        "a resource-class OSError on the catalog read must propagate loudly "
        "with its real errno (EMFILE) -- never collapse into a fabricated "
        f"'orphan gate_id' FAIL verdict; got errno={exc_info.value.errno!r} "
        "(the bare `except OSError` in verify_wave_contract_coherence._read "
        "still swallows it until the except tuple is narrowed to "
        "(FileNotFoundError, IsADirectoryError, UnicodeDecodeError))"
    )


# ===========================================================================
# NEGATIVE WITNESS B -- delta reader's registry read (RED today)
# ===========================================================================


@pytest.mark.negative_at
def test_delta_reader_never_returns_silent_none_from_transient_oserror(
    tmp_path: Path,
) -> None:
    """A resource-class ``OSError`` (ENOMEM) on the REGISTRY read must
    propagate with its real errno visible -- never be swallowed into the
    silent ``None`` that maps to the "registry ... is unreadable (absent /
    garbled)" verdict.

    RED today: ``read_wave_output_contract()`` catches the bare ``OSError``,
    returns ``None``, ``_run_require_registry_sections`` degrades to
    ``_emit_boundary_verdict`` (indeterminate, exit 1) with no exception
    raised, so this ``pytest.raises`` block fails with "DID NOT RAISE" (RED
    for the right reason).
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    registry_path = waves_dir / "distill.yaml"
    registry_path.write_text(_VALID_REGISTRY_TEXT, encoding="utf-8")
    target = tmp_path / "feature-delta.md"
    target.write_text("# Feature Delta\n\nSome content.\n", encoding="utf-8")

    injected = OSError(errno.ENOMEM, "Cannot allocate memory")
    argv = [
        "--require-registry-sections",
        "distill",
        "--waves-dir",
        str(waves_dir),
        "--format=json",
        str(target),
    ]

    with _inject_oserror_on_read(registry_path, injected):
        with pytest.raises(OSError) as exc_info:
            delta_main(argv)

    assert exc_info.value.errno == errno.ENOMEM, (
        "a resource-class OSError on the registry read must propagate loudly "
        "with its real errno (ENOMEM) -- never collapse into the silent None "
        f"that maps to 'registry unreadable (absent / garbled)'; got "
        f"errno={exc_info.value.errno!r} (the bare `except OSError` in "
        "validate_feature_delta.read_wave_output_contract still swallows it "
        "until the except tuple is narrowed to (FileNotFoundError, "
        "IsADirectoryError, UnicodeDecodeError))"
    )


# ===========================================================================
# INVARIANCE PINS -- genuine absence / genuine corruption, GREEN before AND
# after the fix (the narrowed except tuple keeps both subtypes)
# ===========================================================================


@pytest.mark.parametrize(
    "corrupt_registry",
    [
        pytest.param(None, id="absent"),
        pytest.param(_UNDECODABLE_BYTES, id="garbled"),
    ],
)
def test_coherence_reader_genuine_absence_and_garbled_registry_unchanged(
    tmp_path: Path,
    corrupt_registry: bytes | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A genuinely ABSENT registry (no ``distill.yaml``) or a genuinely
    GARBLED one (undecodable bytes) must keep today's INDETERMINATE
    degrade-LOUD behavior exactly -- unaffected by narrowing the except
    tuple, since ``FileNotFoundError``/``UnicodeDecodeError`` stay in it.
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    if corrupt_registry is not None:
        (waves_dir / "distill.yaml").write_bytes(corrupt_registry)
    prose = tmp_path / "distill-prose.md"
    prose.write_text(_VALID_PROSE_TEXT, encoding="utf-8")

    exit_code = coherence_main(
        ["--wave", "distill", "--prose", str(prose), "--waves-dir", str(waves_dir)]
    )
    payload = _stdout_json(capsys)

    assert exit_code == 4, (
        f"a genuinely unreadable registry ({'absent' if corrupt_registry is None else 'garbled'}) "
        f"must degrade LOUD to INDETERMINATE (exit 4) exactly as today -- got "
        f"exit_code={exit_code}, payload={payload!r}"
    )
    assert payload["verdict"] == "indeterminate", (
        f"expected the 'indeterminate' verdict token unchanged -- got {payload!r}"
    )


@pytest.mark.parametrize(
    "corrupt_registry",
    [
        pytest.param(None, id="absent"),
        pytest.param(_UNDECODABLE_BYTES, id="garbled"),
    ],
)
def test_delta_reader_genuine_absence_and_garbled_registry_unchanged(
    tmp_path: Path,
    corrupt_registry: bytes | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A genuinely ABSENT registry (no ``distill.yaml``) or a genuinely
    GARBLED one (undecodable bytes) must keep today's "registry unreadable
    (absent / garbled)" indeterminate-boundary behavior exactly.
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    if corrupt_registry is not None:
        (waves_dir / "distill.yaml").write_bytes(corrupt_registry)
    target = tmp_path / "feature-delta.md"
    target.write_text("# Feature Delta\n\nSome content.\n", encoding="utf-8")

    exit_code = delta_main(
        [
            "--require-registry-sections",
            "distill",
            "--waves-dir",
            str(waves_dir),
            "--format=json",
            str(target),
        ]
    )
    payload = _stdout_json(capsys)

    assert exit_code == 1, (
        f"a genuinely unreadable registry ({'absent' if corrupt_registry is None else 'garbled'}) "
        f"must degrade to the indeterminate boundary verdict (exit 1) exactly "
        f"as today -- got exit_code={exit_code}, payload={payload!r}"
    )
    assert payload["verdict"] == "indeterminate", (
        f"expected the 'indeterminate' verdict token unchanged -- got {payload!r}"
    )
