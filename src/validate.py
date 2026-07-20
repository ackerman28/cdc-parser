"""
validate.py — Automatic quality checks for the extracted CDC dataset.

WHY THIS EXISTS
---------------
Camellia had to open every bulletin's output by hand and eyeball it for
extraction errors (shifted columns, OCR garbage, merged cells). That manual
check is slow and doesn't scale to ~157 bulletins. This module does that
checking automatically: it takes the dataset the pipeline produces and returns a
report of every suspicious row, so a human only looks at the flagged ones.

DESIGN
------
Two severities:
  ERROR   — almost certainly wrong; the row is unusable as-is.
            (unknown country, non-numeric where a number must be, negative
             counts, a "new" count exceeding its cumulative total, garbled Type)
  WARNING — looks off but might be legitimate; a human should glance at it.
            (confirmed > suspected — in CDC bulletins these are sometimes
             separate case streams, not subsets, so this is not always an error;
             truncated risk labels like "Mode" for "Moderate")

The validator NEVER changes the data. It only reports. Fixing is a separate
concern (that lives in clean.py / the extraction improvements).

USAGE
-----
    from src.validate import validate
    report = validate(df)
    report.print_summary()
    report.to_excel("data/output/validation_report.xlsx")
"""

import re
import pandas as pd


# ---------- REFERENCE DATA ----------

# The 55 African Union member states, in the name forms Africa CDC uses.
# A country value outside this set means the country cell was mis-extracted.
AU_MEMBER_STATES = {
    "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
    "Cabo Verde", "Cameroon", "Central African Republic", "Chad", "Comoros",
    "Republic of the Congo", "Democratic Republic of the Congo", "Côte d'Ivoire",
    "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia",
    "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Kenya", "Lesotho",
    "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius",
    "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria", "Rwanda",
    "Sao Tome and Principe", "Senegal", "Seychelles", "Sierra Leone", "Somalia",
    "South Africa", "South Sudan", "Sudan", "Tanzania", "Togo", "Tunisia",
    "Uganda", "Zambia", "Zimbabwe", "Western Sahara",
}

# Valid values for the "Type" (event type) column in the bulletins.
VALID_TYPES = {"Human", "Animal", "Environment", "Environmental"}

# Valid risk levels. Anything else in a Risk column is truncated/garbled OCR.
VALID_RISK = {"Low", "Very Low", "Moderate", "High", "Very High"}

# Every column the pipeline is expected to produce. If one is MISSING entirely
# (not just empty), that is a silent extraction failure -- e.g. a bulletin whose
# header wording changed, so the column was never created. Without this check a
# vanished column produces "0 errors", because the other checks only look at
# columns that exist.
EXPECTED_COLUMNS = [
    "Report Date", "Agent/Syndrome", "Country",
    "Risk Human", "Risk Animal",
    "tot_suspected", "new_suspected",
    "tot_probable", "new_probable",
    "tot_confirmed", "new_confirmed",
    "tot_deaths", "new_deaths",
]

# The numeric columns that must contain numbers (or be blank), never text.
NUMERIC_COLUMNS = [
    "tot_suspected", "new_suspected", "tot_probable", "new_probable",
    "tot_confirmed", "new_confirmed", "tot_deaths", "new_deaths",
    "tot_susceptible", "new_susceptible",
]

# Matched cumulative/new pairs: a "new" value can never exceed its total.
TOT_NEW_PAIRS = [
    ("tot_suspected", "new_suspected"),
    ("tot_probable", "new_probable"),
    ("tot_confirmed", "new_confirmed"),
    ("tot_deaths", "new_deaths"),
    ("tot_susceptible", "new_susceptible"),
]


# ---------- REPORT OBJECT ----------

class ValidationReport:
    """Holds the flagged rows and prints/exports them."""

    def __init__(self, issues, n_rows):
        # issues: list of dicts {row, severity, column, check, value, message}
        self.issues = pd.DataFrame(issues)
        self.n_rows = n_rows

    @property
    def n_errors(self):
        if self.issues.empty:
            return 0
        return int((self.issues["severity"] == "ERROR").sum())

    @property
    def n_warnings(self):
        if self.issues.empty:
            return 0
        return int((self.issues["severity"] == "WARNING").sum())

    def rows_with_errors(self):
        """The set of dataframe row-indices that have at least one ERROR."""
        if self.issues.empty:
            return set()
        return set(self.issues.loc[self.issues["severity"] == "ERROR", "row"])

    def print_summary(self):
        print("=" * 60)
        print("VALIDATION REPORT")
        print("=" * 60)
        print(f"Rows checked:        {self.n_rows}")
        print(f"Errors:              {self.n_errors}")
        print(f"Warnings:            {self.n_warnings}")
        print(f"Rows with errors:    {len(self.rows_with_errors())}")
        print("-" * 60)
        if self.issues.empty:
            print("No issues found.")
            return
        # Count by check type, most common first
        by_check = (
            self.issues.groupby(["severity", "check"])
            .size()
            .sort_values(ascending=False)
        )
        print("Issues by type:")
        for (sev, check), n in by_check.items():
            print(f"  [{sev:7}] {check:32} {n}")
        print("=" * 60)

    def to_excel(self, path):
        """Write the full list of flagged issues for a human to review."""
        self.issues.to_excel(path, index=False)
        print(f"Validation report written to {path}")


# ---------- INDIVIDUAL CHECKS ----------
# Each check appends dicts to `issues`. They never modify df.

def _is_number(x):
    """True if x is a real number (or blank, which is allowed)."""
    if pd.isna(x):
        return True  # blank is fine; not every count is reported
    if isinstance(x, (int, float)):
        return True
    # a string that isn't a clean number = extraction error
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", str(x).strip()))


def _check_disease(df, issues):
    """Flag rows whose disease name could not be recognized.

    A disease name that OCR mangled beyond recognition is marked UNKNOWN by
    clean.py rather than silently inheriting the previous row's disease. Without
    this check such a row looks perfectly valid (a real country, real numbers)
    while carrying the WRONG disease label.
    """
    if "Agent/Syndrome" not in df.columns:
        return
    for i, val in df["Agent/Syndrome"].items():
        if pd.isna(val) or str(val).strip() == "":
            issues.append(dict(row=i, severity="ERROR", column="Agent/Syndrome",
                               check="disease_missing", value=val,
                               message="Disease name is blank"))
        elif str(val).strip().upper() == "UNKNOWN":
            issues.append(dict(row=i, severity="ERROR", column="Agent/Syndrome",
                               check="disease_unrecognized", value=val,
                               message="Disease name could not be recognized from the "
                                       "OCR'd text - check the bulletin and add the "
                                       "name to DISEASE_PATTERNS in clean.py"))


def _check_country(df, issues):
    for i, val in df["Country"].items():
        if pd.isna(val):
            issues.append(dict(row=i, severity="ERROR", column="Country",
                               check="country_missing", value=val,
                               message="Country is blank"))
        elif str(val).strip() not in AU_MEMBER_STATES:
            issues.append(dict(row=i, severity="ERROR", column="Country",
                               check="country_unknown", value=val,
                               message=f"'{val}' is not a recognized AU member state"))


def _check_type(df, issues):
    if "Type" not in df.columns:
        return
    for i, val in df["Type"].items():
        if pd.isna(val):
            continue
        if str(val).strip() not in VALID_TYPES:
            issues.append(dict(row=i, severity="ERROR", column="Type",
                               check="type_garbled", value=val,
                               message=f"Type '{val}' is not Human/Animal/Environment "
                                       f"(likely OCR fragment)"))


def _check_risk(df, issues):
    for col in ["Risk Human", "Risk Animal"]:
        if col not in df.columns:
            continue
        for i, val in df[col].items():
            if pd.isna(val):
                continue
            s = str(val).strip()
            if s.lower() in {"none", "n/a"}:
                continue  # explicitly-absent risk is acceptable
            if s not in VALID_RISK:
                issues.append(dict(row=i, severity="WARNING", column=col,
                                   check="risk_label_garbled", value=val,
                                   message=f"'{val}' is not a clean risk level "
                                           f"(possible truncation, e.g. 'Mode'->'Moderate')"))


def _check_numeric_type(df, issues):
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            continue
        for i, val in df[col].items():
            if not _is_number(val):
                issues.append(dict(row=i, severity="ERROR", column=col,
                                   check="non_numeric_value", value=val,
                                   message=f"{col} = '{val}' is not a number"))


def _check_negatives(df, issues):
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        for i in df.index[s < 0]:
            issues.append(dict(row=i, severity="ERROR", column=col,
                               check="negative_count", value=df.at[i, col],
                               message=f"{col} is negative"))


def _check_new_exceeds_total(df, issues):
    for tot, new in TOT_NEW_PAIRS:
        if tot not in df.columns or new not in df.columns:
            continue
        t = pd.to_numeric(df[tot], errors="coerce")
        n = pd.to_numeric(df[new], errors="coerce")
        mask = t.notna() & n.notna() & (n > t)
        for i in df.index[mask]:
            issues.append(dict(row=i, severity="ERROR", column=new,
                               check="new_exceeds_total", value=df.at[i, new],
                               message=f"{new} ({df.at[i, new]}) > {tot} ({df.at[i, tot]}) "
                                       f"- a new count cannot exceed the cumulative total"))


def _check_confirmed_vs_suspected(df, issues):
    # WARNING only: in CDC bulletins suspected & confirmed are sometimes
    # separate streams, so confirmed > suspected is not always an error.
    if "tot_confirmed" not in df.columns or "tot_suspected" not in df.columns:
        return
    c = pd.to_numeric(df["tot_confirmed"], errors="coerce")
    s = pd.to_numeric(df["tot_suspected"], errors="coerce")
    mask = c.notna() & s.notna() & (s > 0) & (c > s)
    for i in df.index[mask]:
        issues.append(dict(row=i, severity="WARNING", column="tot_confirmed",
                           check="confirmed_gt_suspected", value=df.at[i, "tot_confirmed"],
                           message=f"tot_confirmed ({df.at[i,'tot_confirmed']}) > "
                                   f"tot_suspected ({df.at[i,'tot_suspected']}) - review"))


def _check_schema(df, issues):
    """Flag any expected column that is missing from the dataset entirely."""
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            issues.append(dict(row=-1, severity="ERROR", column=col,
                               check="missing_column", value=None,
                               message=f"Expected column '{col}' is missing from the "
                                       f"dataset - extraction likely failed to find it "
                                       f"(header wording may differ in this bulletin)"))


def _check_date(df, issues):
    if "Report Date" not in df.columns:
        return
    for i, val in df["Report Date"].items():
        if pd.isna(val) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(val).strip()):
            issues.append(dict(row=i, severity="ERROR", column="Report Date",
                               check="bad_date", value=val,
                               message=f"Report Date '{val}' is missing or not YYYY-MM-DD"))


# ---------- MAIN ENTRY POINT ----------

def validate(df):
    """Run all checks on the dataset and return a ValidationReport.

    Does not modify df.
    """
    issues = []
    _check_schema(df, issues)
    _check_date(df, issues)
    _check_country(df, issues)
    _check_disease(df, issues)
    _check_type(df, issues)
    _check_risk(df, issues)
    _check_numeric_type(df, issues)
    _check_negatives(df, issues)
    _check_new_exceeds_total(df, issues)
    _check_confirmed_vs_suspected(df, issues)
    return ValidationReport(issues, n_rows=len(df))


if __name__ == "__main__":
    # Quick manual run against a dataset file.
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/output/africa_cdc_master.xlsx"
    df = pd.read_excel(path)
    report = validate(df)
    report.print_summary()