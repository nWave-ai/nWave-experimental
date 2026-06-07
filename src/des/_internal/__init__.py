"""Internal stdlib-only helpers shared across the DES bundle.

This package is the home for utilities the DES bundle needs that would
otherwise drag external dependencies into the installed plugin. The
DES-bundle hygiene contract (`tests/build/acceptance/plugin/steps/
test_des_bundle_steps.py::des_no_external_deps`) forbids `yaml`,
`pyyaml`, `toml`, `tomli`, `pydantic`, `requests` inside the bundled
`des/` module. Any helper added here MUST remain stdlib-only.

Underscore prefix signals "internal to des, no public API guarantee".
External callers must NOT import from `des._internal.*`.
"""
