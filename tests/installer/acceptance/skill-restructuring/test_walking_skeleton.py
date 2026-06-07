"""
Walking Skeleton Acceptance Tests for Skill Restructuring.

These are the first tests to enable -- they prove the complete mechanism
end-to-end with the simplest possible slice (3 troubleshooter skills).

Driving ports: SkillsPlugin.install(), SkillsPlugin.verify()
"""

from pytest_bdd import scenario


@scenario(
    "walking-skeleton.feature",
    "Maintainer installs skills and agent receives them automatically",
)
def test_walking_skeleton_install():
    """Walking skeleton: install 3 skills and verify auto-loading path."""
    pass


@scenario(
    "walking-skeleton.feature",
    "Existing user upgrades and old skill structure is cleaned up",
)
def test_walking_skeleton_upgrade():
    """Walking skeleton: upgrade cleans old namespace."""
    pass


@scenario(
    "walking-skeleton.feature",
    "User's custom skills are preserved during installation",
)
def test_walking_skeleton_custom_preservation():
    """Walking skeleton: custom skills untouched during install."""
    pass
