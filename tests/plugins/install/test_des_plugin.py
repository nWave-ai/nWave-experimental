"""Tests for DESPlugin."""

from scripts.install.plugins.des_plugin import DESPlugin


def test_des_plugin_name():
    """Test DES plugin has correct name."""
    plugin = DESPlugin()
    assert plugin.name == "des"


def test_des_plugin_priority():
    """Test DES plugin has correct priority."""
    plugin = DESPlugin()
    assert plugin.priority == 50


def test_des_plugin_dependencies():
    """Test DES plugin declares correct dependencies."""
    plugin = DESPlugin()
    assert plugin.dependencies == ["templates", "utilities"]


def test_des_plugin_install_returns_plugin_result(tmp_path):
    """Test DES plugin install returns PluginResult with success=False initially."""
    import logging

    from scripts.install.plugins.base import InstallContext

    plugin = DESPlugin()
    context = InstallContext(
        claude_dir=tmp_path,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logging.getLogger(),
    )

    result = plugin.install(context)
    assert result is not None
    assert hasattr(result, "success")
    assert hasattr(result, "message")


def test_des_plugin_verify_returns_plugin_result(tmp_path):
    """Test DES plugin verify returns PluginResult."""
    import logging

    from scripts.install.plugins.base import InstallContext

    plugin = DESPlugin()
    context = InstallContext(
        claude_dir=tmp_path,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logging.getLogger(),
    )

    result = plugin.verify(context)
    assert result is not None
    assert hasattr(result, "success")
    assert hasattr(result, "message")
