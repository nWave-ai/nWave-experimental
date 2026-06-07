# Manual Setup: Tutorial 15 — Creating Quality Documentation

If you'd rather run commands by hand instead of using `setup.py`, follow these steps. Run them from a directory where you want the tutorial project created (e.g. `~/projects` or `cd $(mktemp -d)`).

## 1. Create the project directory

```bash
mkdir -p string-utils
cd string-utils
```

## 2. Create `string_utils.py`

```python
"""String utility functions for common text transformations."""


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Lowercases the text, replaces spaces with hyphens,
    and removes non-alphanumeric characters (except hyphens).

    Args:
        text: The input string to slugify.

    Returns:
        A lowercase, hyphen-separated string safe for URLs.
    """
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length, adding a suffix if truncated.

    If the text is shorter than max_length, it is returned unchanged.
    Otherwise, it is cut at max_length minus the suffix length, and
    the suffix is appended.

    Args:
        text: The input string to truncate.
        max_length: Maximum allowed length (default 100).
        suffix: String to append when truncating (default "...").

    Returns:
        The original or truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def word_count(text: str) -> int:
    """Count the number of words in a string.

    Words are separated by whitespace. Empty strings return 0.

    Args:
        text: The input string.

    Returns:
        The number of words.
    """
    return len(text.split()) if text.strip() else 0
```

## Verify

You should now have:

- A `string-utils/` directory with `string_utils.py` containing three functions: `slugify`, `truncate`, `word_count`
- Each function has docstrings — `/nw-document` will use these as input but produce DIVIO-compliant docs around them

You're ready to start the documentation tutorial.
