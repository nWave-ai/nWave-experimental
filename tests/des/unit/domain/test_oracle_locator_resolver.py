"""Unit tests for the acceptance-oracle locator CONVENTION
(`des compile-contract`'s oracle-locator decision, never ATD's or root's)."""

from __future__ import annotations

from pathlib import Path

from des.domain.oracle_locator_resolver import (
    is_test_shaped_path,
    oracle_slug,
    resolve_cited_oracle_locator,
    resolve_existing_oracle_locator,
    resolve_oracle_locator,
    resolve_oracle_test_dir,
)


def test_slug_converts_kebab_delivery_id_to_snake_case() -> None:
    assert oracle_slug("k4-maintenance-windows") == "k4_maintenance_windows"


def test_prefers_sibling_tests_dir_next_to_primary_target(tmp_path: Path) -> None:
    (tmp_path / "hc" / "api" / "tests").mkdir(parents=True)
    assert resolve_oracle_test_dir(tmp_path, "hc/api/models.py") == "hc/api/tests"


def test_falls_back_to_repository_root_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "pkg/widget.py") == "tests"


def test_sibling_dir_wins_over_repository_root_when_both_exist(
    tmp_path: Path,
) -> None:
    (tmp_path / "hc" / "api" / "tests").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "hc/api/models.py") == "hc/api/tests"


def test_returns_none_when_no_test_dir_convention_exists(tmp_path: Path) -> None:
    (tmp_path / "hc" / "api").mkdir(parents=True)
    assert resolve_oracle_test_dir(tmp_path, "hc/api/models.py") is None


def test_root_level_target_resolves_a_bare_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "widget.py") == "tests"


def test_resolve_oracle_locator_composes_dir_and_slug(tmp_path: Path) -> None:
    (tmp_path / "hc" / "api" / "tests").mkdir(parents=True)
    assert (
        resolve_oracle_locator(tmp_path, "hc/api/models.py", "k4-maintenance-windows")
        == "hc/api/tests/test_k4_maintenance_windows.py"
    )


def test_resolve_oracle_locator_none_when_undiscoverable(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    assert resolve_oracle_locator(tmp_path, "pkg/widget.py", "widget-color") is None


# -- resolve_existing_oracle_locator (GREEN_TO_GREEN) -- SF friction report
# 2026-08-20, item 2a: GREEN_TO_GREEN must bind an ALREADY-EXISTING,
# already-committed oracle -- never project an unauthored, possibly
# wrong-language path the way `resolve_oracle_locator` (RED_TO_GREEN) does.


def test_picks_the_first_existing_test_shaped_citation(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "widget_test.go").write_text("package pkg\n", encoding="utf-8")
    citations = {
        "pkg/widget.go": ["pkg/widget.go:3"],
        "pkg/widget_test.go": ["pkg/widget_test.go:5"],
    }
    assert resolve_existing_oracle_locator(tmp_path, citations) == "pkg/widget_test.go"


def test_recognizes_a_spec_shaped_citation_too(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "widget.spec.ts").write_text("", encoding="utf-8")
    citations = {"pkg/widget.spec.ts": ["pkg/widget.spec.ts:1"]}
    assert resolve_existing_oracle_locator(tmp_path, citations) == "pkg/widget.spec.ts"


def test_none_when_a_test_shaped_citation_is_cited_but_does_not_exist_on_disk(
    tmp_path: Path,
) -> None:
    # Never invent/trust a cited path that is not actually committed --
    # the SAME "already exists" requirement RED_TO_GREEN's own conventional
    # path is exempt from (it projects a not-yet-existing path on purpose).
    citations = {"pkg/widget_test.go": ["pkg/widget_test.go:5"]}
    assert resolve_existing_oracle_locator(tmp_path, citations) is None


def test_none_when_no_citation_reads_as_a_test_or_spec_file(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "widget.go").write_text("package pkg\n", encoding="utf-8")
    citations = {"pkg/widget.go": ["pkg/widget.go:3"]}
    assert resolve_existing_oracle_locator(tmp_path, citations) is None


def test_existing_oracle_citation_with_selector_binds_verbatim(
    tmp_path: Path,
) -> None:
    # GREEN_TO_GREEN with a `path::Selector` citation: existence is checked
    # on the FILE part, the returned locator preserves the selector.
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "widget_test.go").write_text("package pkg\n", encoding="utf-8")
    citations = ["pkg/widget_test.go::TestWidget"]
    assert (
        resolve_existing_oracle_locator(tmp_path, citations)
        == "pkg/widget_test.go::TestWidget"
    )


def test_cited_oracle_locator_binds_first_citation_without_existence(
    tmp_path: Path,
) -> None:
    # RED_TO_GREEN: an explicitly cited oracle binds even before ATD has
    # authored it -- the citation is the author's chosen path.
    assert (
        resolve_cited_oracle_locator(["pkg/widget_test.go::TestWidget"])
        == "pkg/widget_test.go::TestWidget"
    )
    assert resolve_cited_oracle_locator([]) is None


# -- is_test_shaped_path word-boundary conventions -- review BLOCK
# 2026-08-20: the substring rule ("test" in stem) swallowed genuine
# production files (contest.go, latest_config.go, attestation.py) into
# the oracle-candidate set and OUT of the contract targets.


def test_production_files_with_embedded_test_substring_are_not_test_shaped() -> None:
    assert not is_test_shaped_path("pkg/contest.go")
    assert not is_test_shaped_path("pkg/latest_config.go")
    assert not is_test_shaped_path("pkg/attestation.py")
    assert not is_test_shaped_path("pkg/protester.rs")
    assert not is_test_shaped_path("src/Latest.java")
    assert not is_test_shaped_path("lib/inspection.rb")


def test_language_native_test_conventions_are_test_shaped() -> None:
    assert is_test_shaped_path("pkg/widget_test.go")
    assert is_test_shaped_path("src/widget_test.rs")
    assert is_test_shaped_path("tests/test_widget.py")
    assert is_test_shaped_path("tests/widget_test.py")
    assert is_test_shaped_path("src/widget.test.ts")
    assert is_test_shaped_path("src/widget.spec.ts")
    assert is_test_shaped_path("src/widget.test.js")
    assert is_test_shaped_path("src/widget.spec.js")
    assert is_test_shaped_path("spec/widget_spec.rb")
    assert is_test_shaped_path("src/WidgetTest.java")
    assert is_test_shaped_path("src/WidgetTest.kt")


def test_unknown_extension_is_never_test_shaped() -> None:
    assert not is_test_shaped_path("scripts/test_runner.sh")


# -- oracle choice precedence -- review BLOCK 2026-08-20: the first
# oracle-candidate entry won verbatim, so a mis-admitted production file
# (contest.go) beat the brief's own explicit ::selector citation.


def test_cited_oracle_first_public_citation_beats_later_selector() -> None:
    assert (
        resolve_cited_oracle_locator(
            ["pkg/widget_test.go", "pkg/other_test.go::TestOther"]
        )
        == "pkg/widget_test.go"
    )


def test_cited_oracle_ties_break_on_the_first_test_shaped_citation() -> None:
    assert (
        resolve_cited_oracle_locator(["pkg/first_test.go", "pkg/second_test.go"])
        == "pkg/first_test.go"
    )


def test_cited_oracle_never_binds_a_non_test_shaped_file() -> None:
    assert resolve_cited_oracle_locator(["pkg/contest.go"]) is None
    assert resolve_cited_oracle_locator(["pkg/contest.go::TestX"]) is None
    assert (
        resolve_cited_oracle_locator(["pkg/contest.go", "pkg/widget_test.go"])
        == "pkg/widget_test.go"
    )


def test_existing_oracle_first_public_citation_beats_later_selector(
    tmp_path: Path,
) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "widget_test.go").write_text("package pkg\n", encoding="utf-8")
    (tmp_path / "pkg" / "other_test.go").write_text("package pkg\n", encoding="utf-8")
    citations = ["pkg/widget_test.go", "pkg/other_test.go::TestOther"]
    assert resolve_existing_oracle_locator(tmp_path, citations) == "pkg/widget_test.go"


# -- tiered tests-root convention (second occurrence 2026-08-21: two
# auto-compiled slices in a row emitted a top-level tests/test_auto_<id>.py
# locator that the subject repo's own conftest collection guard refuses --
# the producer must OBSERVE the subject's placement convention, never
# hardcode any repo's layout).


def test_tiered_tests_root_places_oracle_in_the_observed_tier(
    tmp_path: Path,
) -> None:
    # The incident shape: a conftest guard at the tests root, every real
    # test living under a tier subdirectory, none directly at top level.
    tests = tmp_path / "tests"
    (tests / "unit").mkdir(parents=True)
    (tests / "conftest.py").write_text("# top-level guard\n", encoding="utf-8")
    (tests / "unit" / "test_existing.py").write_text("", encoding="utf-8")
    assert resolve_oracle_test_dir(tmp_path, "src/pkg/widget.py") == "tests/unit"


def test_tier_choice_mirrors_the_primary_target_package_path(
    tmp_path: Path,
) -> None:
    # Same-nature observation: the tier whose path segments mirror the
    # primary target's own package path wins over a merely more populated
    # sibling tier.
    tests = tmp_path / "tests"
    (tests / "des" / "unit" / "application").mkdir(parents=True)
    (tests / "plugins" / "unit").mkdir(parents=True)
    (tests / "des" / "unit" / "application" / "test_a.py").write_text(
        "", encoding="utf-8"
    )
    (tests / "plugins" / "unit" / "test_b.py").write_text("", encoding="utf-8")
    (tests / "plugins" / "unit" / "test_c.py").write_text("", encoding="utf-8")
    assert (
        resolve_oracle_test_dir(tmp_path, "src/des/application/mod.py")
        == "tests/des/unit/application"
    )


def test_legacy_stragglers_do_not_outvote_a_tiered_convention(
    tmp_path: Path,
) -> None:
    # A handful of pre-migration top-level modules (the real subject repo
    # allowlists exactly such stragglers) must not read as a flat
    # convention when the tiered population dominates.
    tests = tmp_path / "tests"
    (tests / "unit").mkdir(parents=True)
    (tests / "test_legacy.py").write_text("", encoding="utf-8")
    (tests / "unit" / "test_a.py").write_text("", encoding="utf-8")
    (tests / "unit" / "test_b.py").write_text("", encoding="utf-8")
    assert resolve_oracle_test_dir(tmp_path, "src/pkg/widget.py") == "tests/unit"


def test_flat_tests_root_keeps_the_top_level_convention(tmp_path: Path) -> None:
    # No discoverable tiered convention -- behavior unchanged.
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_existing.py").write_text("", encoding="utf-8")
    assert resolve_oracle_test_dir(tmp_path, "src/pkg/widget.py") == "tests"


def test_empty_tests_root_keeps_the_top_level_convention(tmp_path: Path) -> None:
    # A brand-new tests/ holds no observable convention at all -- ATD
    # authors the first oracle right there, exactly as before.
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "src/pkg/widget.py") == "tests"


def test_non_python_tests_do_not_steer_the_python_oracle_tier(
    tmp_path: Path,
) -> None:
    # The projected oracle is pytest -- only the subject's PYTHON test
    # placement is the same-nature convention; a better-populated Go tier
    # is not.
    tests = tmp_path / "tests"
    (tests / "golang").mkdir(parents=True)
    (tests / "unit").mkdir(parents=True)
    (tests / "golang" / "widget_test.go").write_text("", encoding="utf-8")
    (tests / "golang" / "other_test.go").write_text("", encoding="utf-8")
    (tests / "unit" / "test_a.py").write_text("", encoding="utf-8")
    assert resolve_oracle_test_dir(tmp_path, "src/pkg/widget.py") == "tests/unit"


def test_resolve_oracle_locator_composes_the_observed_tier(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    (tests / "unit").mkdir(parents=True)
    (tests / "unit" / "test_existing.py").write_text("", encoding="utf-8")
    assert (
        resolve_oracle_locator(tmp_path, "src/pkg/widget.py", "widget-color")
        == "tests/unit/test_widget_color.py"
    )
