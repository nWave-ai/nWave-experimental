"""Unit tests preserving DesMarkerParser's pure parsing contract."""

import pytest

from des.domain.des_marker_parser import DesMarkerParser, DesMarkers


# ===========================================================================
# DesMarkerParser tests
# ===========================================================================


class TestDesMarkerParser:
    """Tests for DesMarkerParser.parse()."""

    def test_parse_detects_des_validation_marker(self):
        parser = DesMarkerParser()
        result = parser.parse("Some text <!-- DES-VALIDATION : required --> more text")
        assert result.is_des_task is True

    def test_parse_returns_false_without_des_marker(self):
        parser = DesMarkerParser()
        result = parser.parse("Just a normal prompt without markers")
        assert result.is_des_task is False
        assert result.is_orchestrator_mode is False
        assert result.project_id is None
        assert result.step_id is None

    def test_parse_detects_orchestrator_mode(self):
        parser = DesMarkerParser()
        result = parser.parse(
            "<!-- DES-VALIDATION : required -->\n<!-- DES-MODE : orchestrator -->"
        )
        assert result.is_des_task is True
        assert result.is_orchestrator_mode is False

    def test_parse_extracts_project_id(self):
        parser = DesMarkerParser()
        result = parser.parse("<!-- DES-PROJECT-ID : my-project -->")
        assert result.project_id == "my-project"

    def test_parse_extracts_step_id(self):
        parser = DesMarkerParser()
        result = parser.parse("<!-- DES-STEP-ID : 01-03 -->")
        assert result.step_id == "01-03"

    def test_parse_handles_varied_whitespace(self):
        parser = DesMarkerParser()
        result = parser.parse("<!--DES-VALIDATION:required-->")
        assert result.is_des_task is True

    def test_parse_full_prompt_with_all_markers(self):
        parser = DesMarkerParser()
        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : orchestrator -->\n"
            "<!-- DES-PROJECT-ID : auth-upgrade -->\n"
            "<!-- DES-STEP-ID : 02-01 -->\n"
            "Some prompt content..."
        )
        result = parser.parse(prompt)

        assert result.is_des_task is True
        assert result.is_orchestrator_mode is False
        assert result.project_id == "auth-upgrade"
        assert result.step_id == "02-01"

    def test_des_markers_is_frozen(self):
        markers = DesMarkers(is_des_task=True, is_orchestrator_mode=False)
        with pytest.raises(AttributeError):
            markers.is_des_task = False  # type: ignore[misc]
