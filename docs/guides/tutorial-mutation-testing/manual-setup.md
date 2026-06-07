# Manual Setup: Tutorial 14 — Validating Your Test Suite

If you'd rather run commands by hand instead of using `setup.py`, follow these steps. Run them from a directory where you want the tutorial project created (e.g. `~/projects` or `cd $(mktemp -d)`).

## 1. Create the project skeleton

```bash
mkdir -p mutation-demo/src mutation-demo/tests
cd mutation-demo
```

## 2. Create `src/calc.py`

```python
# src/calc.py

def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def discount_price(price: float, percent: float) -> float:
    """Apply a percentage discount. Returns the discounted price."""
    if percent < 0 or percent > 100:
        raise ValueError("Percent must be between 0 and 100")
    return price * (1 - percent / 100)
```

## 3. Create `tests/test_calc.py`

These tests are intentionally **weak** — they pass and cover every line, but several assertions don't verify the actual computation. The tutorial uses mutation testing to expose those gaps.

```python
# tests/test_calc.py
from src.calc import add, subtract, multiply, divide, discount_price
import pytest


def test_add():
    result = add(2, 3)
    assert result is not None  # weak: only checks existence


def test_subtract():
    result = subtract(10.0, 4.0)
    assert isinstance(result, float)  # weak: only checks type


def test_multiply():
    result = multiply(3, 4)
    assert result > 0  # weak: many wrong answers are also > 0


def test_divide():
    result = divide(10, 2)
    assert result == 5.0  # strong: checks exact value


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)  # strong: checks error is raised


def test_discount_price():
    result = discount_price(100, 20)
    assert result is not None  # weak: does not check actual price


def test_discount_price_full():
    result = discount_price(100, 100)
    assert result >= 0  # weak: 0 is correct, but so is 50 or 99


def test_discount_invalid_percent():
    with pytest.raises(ValueError):
        discount_price(100, -10)  # strong: checks validation
```

## 4. Create `conftest.py`

```bash
echo 'import sys; sys.path.insert(0, ".")' > conftest.py
```

## 5. Create the virtualenv and install pytest

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
```

> **Windows users**: Replace `source .venv/bin/activate` with `.venv\Scripts\activate`.

## 6. Initialize git

```bash
echo ".venv/" > .gitignore
echo "__pycache__/" >> .gitignore
git init
git add -A
git commit -m "feat: calculator with passing tests (starting point for mutation testing)"
```

## Verify

Run the tests — all 8 should pass:

```bash
pytest tests/ -v --no-header
```

You should now have:

- A `mutation-demo/` directory with `src/calc.py`, `tests/test_calc.py`, `conftest.py`, `.gitignore`
- A `.venv/` virtual environment with `pytest` installed
- A clean git repository with one initial commit
- 8 passing tests (every function tested, every line covered) — the catch is that several assertions are too weak

You're ready to start the mutation testing tutorial.
