"""
clean_new_2026.py — Post-process the combined 2026 extraction:
  1. Drop ghost rows (country-fragment rows with no case counts at all)
  2. Recover real disease names embedded in 'UNKNOWN: ...' labels
  3. Report anything still UNKNOWN so nothing is silently mislabeled

Works on the saved CSV — no OCR, runs instantly.

    python analysis\\clean_new_2026.py

In : analysis/new_2026_rows.csv
Out: analysis/new_2026_clean.csv
"""
import re
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
src = HERE / "new_2026_rows.csv"
df = pd.read_csv(src)

print(f"Loaded {len(df)} rows")

count_cols = [c for c in df.columns if c.startswith(("tot_", "new_"))]

# --- 1. Drop ghost rows: all count columns NaN AND country looks like a fragment ---
before = len(df)
all_nan_counts = df[count_cols].isna().all(axis=1)
df = df[~all_nan_counts].copy()
print(f"Dropped {before - len(df)} ghost rows (all counts NaN) -> {len(df)} rows")

# --- 2. Recover disease names embedded in 'UNKNOWN: ...' strings ---
# Map: a keyword found inside the UNKNOWN string -> the correct disease label.
RECOVER = {
    r"cchf|crimean": "CCHF",
    r"bundibugyo": "Bundibugyo",
    r"flood": "Floods",
    r"landslide": "Landslides",
    r"derriv|derived|polio": "Polio (vaccine-derived)",
    r"lassa": "Lassa fever",
    r"rift": "Rift Valley Fever",
    r"yellow": "Yellow fever",
    r"marburg": "Marburg",
    r"anthrax": "Anthrax",
    r"diphther": "Diphtheria",
    r"measles": "Measles",
    r"cholera": "Cholera",
    r"mpox|monkeypox": "Mpox",
    r"dengue": "Dengue",
    r"chikungunya": "Chikungunya",
    r"hepatitis": "Hepatitis E",
}

def recover(label):
    if not isinstance(label, str) or not label.upper().startswith("UNKNOWN"):
        return label, False
    low = label.lower()
    for pat, name in RECOVER.items():
        if re.search(pat, low):
            return name, True
    return label, False

recovered = 0
new_labels = []
still_unknown = []
for _, row in df.iterrows():
    lab, changed = recover(row["Agent/Syndrome"])
    new_labels.append(lab)
    if changed:
        recovered += 1
    elif isinstance(row["Agent/Syndrome"], str) and row["Agent/Syndrome"].upper().startswith("UNKNOWN"):
        still_unknown.append((row.get("Report Date"), row["Agent/Syndrome"], row.get("Country")))

df["Agent/Syndrome"] = new_labels
print(f"Recovered {recovered} disease labels from UNKNOWN strings")

# --- 3. Report anything still unknown ---
if still_unknown:
    print(f"\n{len(still_unknown)} rows STILL UNKNOWN (need review):")
    for d, lab, c in still_unknown:
        print(f"  {d}  {lab!r}  country={c!r}")
else:
    print("\nNo UNKNOWN rows remain.")

out = HERE / "new_2026_clean.csv"
df.to_csv(out, index=False)
print(f"\nSaved {len(df)} rows -> {out}")

# quick disease tally
print("\nDisease counts:")
print(df["Agent/Syndrome"].value_counts().to_string())