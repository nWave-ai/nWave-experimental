"""Acceptance tests for DoctorContext dataclass.

Tests enter through the DoctorContext public API (driving port at domain scope).
DoctorContext is a pure value object — its public interface IS the driving port.
"""

from pathlib import Path

from nwave_ai.doctor.context import DoctorContext


def test_defaults_use_path_home():
    """from_defaults() home_dir must equal Path.home() at construction time."""
    context = DoctorContext.from_defaults()
    assert context.home_dir == Path.home()


def test_overrides_preserved():
    """When home_dir is overridden, claude_dir and settings_path derive from it."""
    custom_home = Path("/tmp/x")
    context = DoctorContext(home_dir=custom_home)
    assert context.claude_dir == custom_home / ".claude"
    assert context.settings_path == custom_home / ".claude" / "settings.json"
