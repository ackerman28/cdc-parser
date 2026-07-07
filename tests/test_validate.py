"""
test_validate.py — Confidence checks for the validator.

Run from project root:
    python tests/test_validate.py    (plain asserts, no pytest needed)
    python -m pytest tests/          (if you have pytest)

Each test builds a tiny dataframe with a KNOWN problem and confirms the validator
flags exactly that. If a future edit breaks a check, these fail loudly instead of
letting bad data slip through silently.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import validate  # noqa: E402


def _base_row():
    """One clean, valid row. Each test corrupts a single field."""
    return {
        "Report Date": "2025-07-15",
        "Agent/Syndrome": "Cholera",
        "Country": "Nigeria",
        "Risk Human": "High",
        "Risk Animal": "none",
        "Type": "Human",
        "tot_suspected": 100.0, "new_suspected": 5.0,
        "tot_probable": 0.0, "new_probable": 0.0,
        "tot_confirmed": 20.0, "new_confirmed": 2.0,
        "tot_deaths": 3.0, "new_deaths": 0.0,
        "tot_susceptible": None, "new_susceptible": None,
    }


def test_clean_row_passes():
    report = validate.validate(pd.DataFrame([_base_row()]))
    assert report.n_errors == 0, "A clean row should produce no errors"


def test_unknown_country_flagged():
    r = _base_row(); r["Country"] = "Wakanda"
    report = validate.validate(pd.DataFrame([r]))
    assert "country_unknown" in set(report.issues["check"])


def test_garbled_type_flagged():
    r = _base_row(); r["Type"] = "e"
    report = validate.validate(pd.DataFrame([r]))
    assert "type_garbled" in set(report.issues["check"])


def test_new_exceeds_total_flagged():
    r = _base_row(); r["new_confirmed"] = 999.0
    report = validate.validate(pd.DataFrame([r]))
    assert "new_exceeds_total" in set(report.issues["check"])


def test_negative_count_flagged():
    r = _base_row(); r["tot_deaths"] = -4.0
    report = validate.validate(pd.DataFrame([r]))
    assert "negative_count" in set(report.issues["check"])


def test_non_numeric_flagged():
    r = _base_row(); r["tot_confirmed"] = "12O"  # letter O, not zero
    report = validate.validate(pd.DataFrame([r]))
    assert "non_numeric_value" in set(report.issues["check"])


def test_bad_date_flagged():
    r = _base_row(); r["Report Date"] = "July 2025"
    report = validate.validate(pd.DataFrame([r]))
    assert "bad_date" in set(report.issues["check"])


def test_confirmed_gt_suspected_is_warning():
    r = _base_row(); r["tot_confirmed"] = 500.0
    report = validate.validate(pd.DataFrame([r]))
    iss = report.issues
    row = iss[iss["check"] == "confirmed_gt_suspected"]
    assert len(row) == 1 and row.iloc[0]["severity"] == "WARNING"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")