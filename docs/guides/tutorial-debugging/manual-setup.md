# Manual Setup: Tutorial 12 — Debugging with 5 Whys

If you'd rather run commands by hand instead of using `setup.py`, follow these steps. Run them from a directory where you want the tutorial project created (e.g. `~/projects` or `cd $(mktemp -d)`).

## 1. Create the project skeleton

```bash
mkdir -p csv-processor/src csv-processor/tests
cd csv-processor
```

## 2. Create `src/processor.py`

The processor has an **intentional bug** you will investigate in Step 4 of the tutorial.

```python
# src/processor.py
# This file has TWO intentional bugs you will discover during the tutorial.
# Don't fix them by reading -- let /nw-root-why walk you through the investigation.


def process_csv(input_text: str) -> list[dict]:
    lines = input_text.strip().split("\n")
    header = lines[0].split(",")
    results = []
    for line in lines[1:-1]:
        parts = line.split(",")
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        if not row.get("amount"):
            continue
        row["amount"] = float(row["amount"])
        results.append(row)
    return results


def summarize(rows: list[dict]) -> dict:
    return {
        "count": len(rows),
        "total": round(sum(r["amount"] for r in rows), 2),
    }
```

## 3. Create `tests/sample.csv`

```bash
cat > tests/sample.csv << 'EOF'
name,amount,category
Alice,50.00,food
Bob,30.00,transport
Carol,20.00,food
Dave,,transport
Eve,15.00,office
Frank,10.00,"food, drinks"
Grace,25.00,transport
Heidi,40.00,food
EOF
```

## 4. Create `tests/test_processor.py`

```python
# tests/test_processor.py
import pytest
from src.processor import process_csv, summarize


SAMPLE_CSV = open("tests/sample.csv").read()


def test_process_csv_row_count():
    """8 rows in CSV, 1 has empty amount, so 7 should remain."""
    rows = process_csv(SAMPLE_CSV)
    assert len(rows) == 7, f"Expected 7 rows, got {len(rows)}: {[r['name'] for r in rows]}"


def test_process_csv_skips_empty_amount():
    rows = process_csv(SAMPLE_CSV)
    names = [r["name"] for r in rows]
    assert "Dave" not in names, "Dave has empty amount and should be skipped"


def test_summarize_total():
    rows = process_csv(SAMPLE_CSV)
    result = summarize(rows)
    assert result["total"] == 190.00, f"Expected 190.00, got {result['total']}"


def test_summarize_count():
    rows = process_csv(SAMPLE_CSV)
    result = summarize(rows)
    assert result["count"] == 7
```

## 5. Create `conftest.py`

So pytest can find the `src` module:

```bash
echo 'import sys; sys.path.insert(0, ".")' > conftest.py
```

## 6. Create the virtualenv and install pytest

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
```

> **Windows users**: Replace `source .venv/bin/activate` with `.venv\Scripts\activate`.

## 7. Initialize git with the buggy starting state

```bash
echo ".venv/" > .gitignore
echo "__pycache__/" >> .gitignore
git init
git add -A
git commit -m "feat: csv processor with intentional bug (starting point for debugging)"
```

## Verify

Run the tests — 3 should fail. **That's expected**: the failing tests are the bug you will investigate during the tutorial.

```bash
pytest tests/ -v --no-header
```

You should now have:

- A `csv-processor/` directory with `src/processor.py`, `tests/sample.csv`, `tests/test_processor.py`, `conftest.py`, `.gitignore`
- A `.venv/` virtual environment with `pytest` installed
- A clean git repository with one initial commit
- A failing test suite (3 failures) — exactly the symptom you will trace during the tutorial

You're ready to start the debugging tutorial.
