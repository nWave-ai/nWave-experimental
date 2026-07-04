"""P0.5 doc↔code coherence gate — the observed proofs, pinned as regression.

These tests ARE the evolution-plan P0.5 done-currency, made permanent: the
gate was proven by execution against planted defects of its target class
(a README claiming an npm script that package.json does not declare, and a
repo path that does not exist -- the eval'd repo's docs-overstate-the-code
class), a clean case, and the degrade-LOUD case.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.cli.verify_doc_coherence import main


_README = (
    "# Demo\n\n"
    "Run `npm run e2e:golden` to verify.\n\n"
    "The reconciler lives in `src/reconciler.ts`.\n"
)


def _write_sandbox(repo: Path, *, honest: bool) -> None:
    (repo / "README.md").write_text(_README)
    (repo / "src").mkdir()
    (repo / "src" / "index.ts").write_text("export {};\n")
    scripts = {"build": "tsc"}
    if honest:
        scripts["e2e:golden"] = "node e2e.js"
        (repo / "src" / "reconciler.ts").write_text("export {};\n")
    (repo / "package.json").write_text(json.dumps({"scripts": scripts}))


def test_overstating_docs_are_refused_listing_both_claims(
    tmp_path: Path, capsys: object
) -> None:
    """NEGATIVE proof: absent npm script + absent file path -> exit 1, both listed."""
    _write_sandbox(tmp_path, honest=False)

    assert main(["--repo", str(tmp_path)]) == 1

    out = capsys.readouterr().out  # type: ignore[attr-defined]
    refused = next(
        json.loads(line)
        for line in out.splitlines()
        if line.startswith("{") and "DocCoherenceRefused" in line
    )
    claims = {v["claim"] for v in refused["violations"]}
    assert claims == {"npm run e2e:golden", "src/reconciler.ts"}
    for violation in refused["violations"]:
        assert violation["doc_file"] == "README.md"
        assert violation["line"] > 0
        assert violation["why_false"]
        assert violation["how_to_fix"]


def test_honest_docs_are_verified(tmp_path: Path) -> None:
    """POSITIVE proof: add the script + the file -> the same docs pass (exit 0)."""
    _write_sandbox(tmp_path, honest=True)

    assert main(["--repo", str(tmp_path)]) == 0


def test_no_docs_degrades_loud_indeterminate(tmp_path: Path, capsys: object) -> None:
    """DEGRADE proof: no docs found -> exit 2 with what/why/how, never a pass."""
    (tmp_path / "package.json").write_text("{}")

    assert main(["--repo", str(tmp_path)]) == 2

    out = capsys.readouterr().out  # type: ignore[attr-defined]
    event = json.loads(out.splitlines()[0])
    assert event["event"] == "DocCoherenceIndeterminate"
    assert all(k in event for k in ("what", "why", "how"))
