"""Domain types for the pytest-AT comment-tag discovery acceptance slice (slice-01).

carpaccio-pytest-at-comment-tag-binding (Mandate-15 criterion 1). Every domain
noun used in the Gherkin is expressed once here as a typed enum / NewType --
step bodies and the composition service consume these typed parameters, never
a raw ``str`` where a domain type exists.

Placeholder note (Mandate 12 DISTILL-before-DELIVER timing): ``FeatureId`` is a
thin ``NewType`` wrapper, not a structural redeclaration of any production
type -- ``des.application.feature_at_files.feature_tagged_test_files`` takes a
plain ``str`` feature id, so there is no production counterpart for this
NewType to later import; it stays exactly this shape across DELIVER.
"""

from __future__ import annotations

from typing import NewType


# A kebab-case feature identifier (e.g. "test-binding-1"), the same domain
# noun `feature_tag_files` already keys the Gherkin `.feature`-file discovery
# on -- this NewType is the pytest-AT-discovery mirror.
FeatureId = NewType("FeatureId", str)

# slice-02 (carpaccio-pytest-at-comment-tag-binding): the `@slice-NN` /
# `@covers-Rn` sub-tags a head-tagged pytest file additionally carries --
# the SAME domain nouns `_SLICE_TAG_RE` (slice_at_completeness.py,
# carpaccio_format.py) already keys Gherkin scenario-tag resolution on, now
# mirrored for a pytest file's head-comment sub-tags.
SliceId = NewType("SliceId", str)
SpecRowId = NewType("SpecRowId", str)
