"""K4 language-vs-runner projection (2026-08-12).

Confirmed defect: root dispatched ATD with an unevidenced "Python/pytest"
assertion, matching the ATD spec's own manifest table which mapped a Python
manifest directly to pytest/pytest-bdd/Hypothesis — conflating language
(manifest-evidenced) with test runner (target: Django, native runner
`manage.py test`, not pytest). ATD then burned its single pass exploring
pytest/Hypothesis and editing requirements-dev.txt without ever producing a
contract.

Two tests, one per independently useful projection:
1. nw-auto/SKILL.md forbids root from naming/guessing language or test
   runner in the ATD dispatch prompt, and delegates evidence discovery to ATD.
2. nw-acceptance-designer.md separates language detection (manifest-evidenced)
   from test-runner discovery (repository-owned executable evidence only),
   and forbids generic-example-driven dependency edits.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"


def _norm(text: str) -> str:
    return " ".join(text.split())


def _sibling_dispatch_bullet() -> str:
    body = (NWAVE_DIR / "skills" / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")
    start = body.index("`nw-acceptance-designer`: receives immutable value seed")
    end = body.index("2. **Join:")
    return _norm(body[start:end])


def _language_convention_frame() -> str:
    body = (NWAVE_DIR / "agents" / "nw-acceptance-designer.md").read_text(
        encoding="utf-8"
    )
    start = body.index("## Language Convention Frame")
    end = body.index("## Reasoning Mandate")
    return _norm(body[start:end])


def test_root_never_names_language_or_runner_and_delegates_to_atd():
    section = _sibling_dispatch_bullet()
    required = (
        "never a root-named or root-guessed language or test runner/framework "
        "in the dispatch prompt",
        "ATD alone owns the bounded pre-authoring evidence window "
        "defined by its own route contract",
    )
    for token in required:
        assert token in section, f"Missing root-delegation projection: {token!r}"


def test_atd_separates_manifest_language_evidence_from_runner_evidence():
    frame = _language_convention_frame()
    required = (
        "evidence for LANGUAGE ONLY",
        "never sufficient evidence for the test runner",
        "discover the project-native test command from repository-owned",
        "EXECUTABLE evidence",
        "that convention always wins over any",
        "Never add or change a test dependency merely because",
        "repository authority",
    )
    for token in required:
        assert token in frame, (
            f"Missing language/runner separation projection: {token!r}"
        )

    table_line = frame[
        frame.index("Before authoring ATs") : frame.index("A manifest is evidence")
    ]
    for leaked_framework in ("pytest-bdd", "hypothesis", "cucumber-js", "godog"):
        assert leaked_framework not in table_line.lower(), (
            f"Manifest table still prescribes a runner: {leaked_framework}"
        )
