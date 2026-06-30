"""des.testing — production-side test doubles importable without touching tests/.

Fakes that production code may legitimately reference live here (NOT under tests/),
so production imports never reach into the test tree (F-D-09 clean: production code
must not import from tests/).
"""
