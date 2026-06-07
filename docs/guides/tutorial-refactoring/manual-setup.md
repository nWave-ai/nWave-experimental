# Manual Setup: Tutorial 11 — Safe Refactoring with Mikado

If you'd rather run commands by hand instead of using `setup.py`, follow these steps. Run them from a directory where you want the tutorial project created (e.g. `~/projects` or `cd $(mktemp -d)`).

## 1. Create the project skeleton

```bash
mkdir -p expense-tracker/src expense-tracker/tests
cd expense-tracker
```

## 2. Create `src/expenses.py`

The expense tracker is **intentionally messy** — you'll analyze the code smells in Step 2 of the tutorial and refactor them later. Don't clean it up by hand.

```python
# src/expenses.py
import json
from datetime import datetime

class ExpenseManager:

    def __init__(self):
        self.expenses = []
        self.tax_rate = 0.21  # hardcoded tax rate
        self.currency = "USD"  # hardcoded currency

    def add_expense(self, amount, category, description=""):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if category not in ["food", "transport", "office", "other"]:
            raise ValueError("Invalid category")
        expense = {
            "amount": amount,
            "category": category,
            "description": description,
            "date": datetime.now().isoformat(),
            "amount_with_tax": round(amount * (1 + 0.21), 2),  # duplicated tax rate
        }
        self.expenses.append(expense)
        return expense

    def get_total(self):
        total = 0
        for e in self.expenses:
            total += e["amount"]
        return total

    def get_total_with_tax(self):
        total = 0
        for e in self.expenses:
            total += e["amount"] * (1 + 0.21)  # duplicated tax rate again
        return round(total, 2)

    def get_report(self):
        lines = []
        lines.append("=== Expense Report ===")
        lines.append(f"Currency: USD")  # hardcoded currency again
        for e in self.expenses:
            lines.append(f"  {e['category']:12s} ${e['amount']:.2f}  {e['description']}")
        lines.append(f"  {'SUBTOTAL':12s} ${self.get_total():.2f}")
        lines.append(f"  {'TAX (21%)':12s} ${self.get_total() * 0.21:.2f}")  # duplicated
        lines.append(f"  {'TOTAL':12s} ${self.get_total_with_tax():.2f}")
        lines.append("=" * 22)
        return "\n".join(lines)

    def save_to_file(self, path):
        with open(path, "w") as f:
            json.dump(self.expenses, f, indent=2)

    def load_from_file(self, path):
        with open(path) as f:
            self.expenses = json.load(f)

    def get_by_category(self, category):
        result = []
        for e in self.expenses:
            if e["category"] == category:
                result.append(e)
        return result

    def get_category_total(self, category):
        total = 0
        for e in self.expenses:
            if e["category"] == category:
                total += e["amount"]
        return total

    def get_category_total_with_tax(self, category):
        total = 0
        for e in self.expenses:
            if e["category"] == category:
                total += e["amount"] * (1 + 0.21)  # duplicated tax rate yet again
        return round(total, 2)
```

## 3. Create `tests/test_expenses.py`

```python
# tests/test_expenses.py
import pytest
from src.expenses import ExpenseManager

@pytest.fixture
def manager():
    em = ExpenseManager()
    em.add_expense(10.00, "food", "Lunch")
    em.add_expense(25.50, "transport", "Taxi")
    em.add_expense(5.00, "food", "Coffee")
    return em

def test_add_expense(manager):
    assert len(manager.expenses) == 3

def test_add_expense_negative_raises():
    em = ExpenseManager()
    with pytest.raises(ValueError, match="positive"):
        em.add_expense(-5, "food")

def test_add_expense_invalid_category():
    em = ExpenseManager()
    with pytest.raises(ValueError, match="Invalid category"):
        em.add_expense(10, "vacation")

def test_get_total(manager):
    assert manager.get_total() == 40.50

def test_get_total_with_tax(manager):
    # The mathematical answer is 49.005; IEEE 754 rounding can land on
    # either 49.00 or 49.01 depending on the platform — use approx to be robust.
    assert manager.get_total_with_tax() == pytest.approx(49.005, abs=0.01)

def test_get_by_category(manager):
    food = manager.get_by_category("food")
    assert len(food) == 2

def test_get_category_total(manager):
    assert manager.get_category_total("food") == 15.00

def test_get_category_total_with_tax(manager):
    assert manager.get_category_total_with_tax("food") == 18.15

def test_get_report(manager):
    report = manager.get_report()
    assert "Expense Report" in report
    assert "TOTAL" in report
    # Compute the expected string dynamically — the report formats whatever
    # get_total_with_tax() returns (49.00 or 49.01 depending on float rounding).
    assert f"${manager.get_total_with_tax():.2f}" in report
```

## 4. Create `conftest.py`

So pytest can find the `src` module:

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

## 6. Initialize git with the messy starting state

```bash
echo ".venv/" > .gitignore
echo "__pycache__/" >> .gitignore
git init
git add -A
git commit -m "feat: messy expense tracker (starting point for refactoring)"
```

## Verify

Run the tests — all 9 should pass:

```bash
pytest tests/ -v --no-header
```

You should now have:

- An `expense-tracker/` directory with `src/expenses.py`, `tests/test_expenses.py`, `conftest.py`, `pyproject`-free Python layout
- A `.venv/` virtual environment with `pytest` installed
- A clean git repository with one initial commit
- 9 passing tests

You're ready to start the refactoring tutorial.
