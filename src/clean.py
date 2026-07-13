"""
clean2.py — Turn the raw coordinate-extracted table into the final analysis schema.

Replaces the long chain of post-hoc OCR patches in the old clean.py. Because
extract2.py now recovers the table structure from page geometry, the columns
arrive in the right places and cleaning becomes simple and predictable:

  1. strip the OCR'd disease ICONS from the Agent/Syndrome names
     (Tesseract reads the little coloured glyphs as junk: "ad Dengue virus",
      "$8 Measles virus", "* Mpox virus")
  2. forward-fill the disease name down its country rows
     (the bulletin prints the disease once, then lists countries beneath it)
  3. split the "1,234 (56)" cells into a cumulative total and a new count
  4. normalize risk labels and country names
"""

import re
import pandas as pd


# Diseases that appear in the bulletins. We match the disease name inside the
# OCR'd string and discard whatever icon-junk sits around it.
KNOWN_DISEASES = [
    "Vibrio cholerae", "Cholera", "Measles virus", "Measles", "Mpox virus", "Mpox",
    "Dengue virus", "Dengue", "Meningitis (Bacterial)", "Meningitis",
    "Chikungunya virus", "Chikungunya", "Ebola virus", "Ebola",
    "Corynebacterium diphtheriae", "Diphtheria", "Polio", "Yellow fever",
    "Lassa fever", "Marburg", "Rift Valley fever", "Anthrax", "Hepatitis",
    "COVID-19", "Influenza", "Malaria", "Typhoid", "Rabies", "Plague",
]

VALID_RISK = ["Very High", "Very Low", "Moderate", "High", "Low"]


def _clean_disease(s):
    """Recover the disease name from an OCR'd cell like '$8 Measles virus'."""
    if not isinstance(s, str) or not s.strip():
        return None
    for d in KNOWN_DISEASES:                 # longest names first (list is ordered)
        if re.search(re.escape(d), s, flags=re.I):
            return d
    return None                              # unrecognized -> leave blank, validator flags it


def _clean_risk(s):
    """Recover a risk level from a cell, tolerating OCR truncation and bleed.

    Like the country column, this cell can be contaminated when column positions
    shift between bulletin layouts, so we search for a risk level INSIDE the text
    rather than requiring the whole cell to be exactly one.
    """
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()

    for r in VALID_RISK:                     # exact match first
        if s.lower() == r.lower():
            return r

    # a risk level sitting inside a contaminated cell ("Angola High")
    # NOTE: "Very High"/"Very Low" are checked before "High"/"Low" because
    # VALID_RISK is ordered longest-first.
    for r in VALID_RISK:
        if re.search(r"\b" + re.escape(r) + r"\b", s, flags=re.I):
            return r

    for r in VALID_RISK:                     # prefix match for truncations ("Mode")
        if r.lower().startswith(s.lower()) and len(s) >= 3:
            return r

    if s.upper() in {"N/A", "NA", "NONE"}:
        return None
    return None


def _split_count(s):
    """'1,234 (56)' -> (1234, 56).  '0 (0)' -> (0, 0).  '' -> (None, None).

    The bulletins report each figure as: cumulative-total (new-since-last-report).
    """
    if not isinstance(s, str) or not s.strip():
        return (None, None)
    txt = s.replace(" ", "")
    m = re.match(r"^([\d,]+)\(([\d,]+)\)$", txt)
    if m:
        tot = int(m.group(1).replace(",", ""))
        new = int(m.group(2).replace(",", ""))
        return (tot, new)
    # sometimes only the total is present
    m2 = re.match(r"^([\d,]+)$", txt)
    if m2:
        return (int(m2.group(1).replace(",", "")), None)
    return (None, None)


def clean_table(df):
    """Raw extracted table -> tidy analysis-ready rows."""
    df = df.copy()

    # 1. disease name: strip icons, then forward-fill down the country rows
    df["Agent/Syndrome"] = df["Agent/Syndrome"].apply(_clean_disease)
    df["Agent/Syndrome"] = df["Agent/Syndrome"].ffill()

    # 2. risk levels.
    #    If a layout shift pushed the risk level into the Country cell
    #    ("Angola High"), recover it from there before Country is normalized.
    if "Risk:Human" in df.columns and "Country" in df.columns:
        spill = df["Risk:Human"].isna() | (df["Risk:Human"].astype(str).str.strip() == "")
        recovered = df.loc[spill, "Country"].apply(_clean_risk)
        df.loc[spill, "Risk:Human"] = df.loc[spill, "Risk:Human"].where(
            recovered.isna(), recovered)

    for col in ["Risk:Human", "Risk:Animal"]:
        if col in df.columns:
            df[col] = df[col].apply(_clean_risk)

    # 3. split "total (new)" into two numeric columns each
    for col, base in [("Suspected", "suspected"), ("Probable", "probable"),
                      ("Confirmed", "confirmed"), ("Deaths", "deaths")]:
        if col not in df.columns:
            continue
        pairs = df[col].apply(_split_count)
        df[f"tot_{base}"] = [p[0] for p in pairs]
        df[f"new_{base}"] = [p[1] for p in pairs]
        df.drop(columns=[col], inplace=True)

    # 4. country: tidy whitespace; leave name-matching to the validator/lookup
    df["Country"] = df["Country"].astype(str).str.strip().replace({"": None, "nan": None})
    df["Country"] = df["Country"].apply(_norm_country)

    # 5. drop the Type column -- it holds only the OCR'd event-type ICON, never
    #    real text, so it cannot be recovered from the scan. (This is the
    #    'type_garbled on every row' finding from the validation work.)
    if "Type" in df.columns:
        df.drop(columns=["Type"], inplace=True)

    # 6. drop rows with no country (page furniture / stray words)
    df = df[df["Country"].notna()].reset_index(drop=True)

    df.rename(columns={"Risk:Human": "Risk Human",
                       "Risk:Animal": "Risk Animal"}, inplace=True)
    return df


# ---------- COUNTRY NORMALIZATION ----------
# OCR mangles accents and truncates long names at the column edge.
# We map whatever comes out to the canonical AU member-state name.

AU_COUNTRIES = [
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
]

# Known OCR mangles / bulletin shorthands -> canonical name
COUNTRY_ALIASES = {
    "congo republic": "Republic of the Congo",
    "congo": "Republic of the Congo",
    "drc": "Democratic Republic of the Congo",
    "car": "Central African Republic",
    "cote divoire": "Côte d'Ivoire",
    "cote d ivoire": "Côte d'Ivoire",
    "tanzania united republic of": "Tanzania",
}


def _norm_country(s):
    """Map an OCR'd country string to a canonical AU member-state name.

    The cell can pick up neighbouring text when a bulletin's column positions
    shift between report years -- e.g. the risk level bleeding in from the right
    ("Angola High") or the tail of a long disease name bleeding in from the left
    ("(Bacterial) Mali"). Rather than hand-tuning pixel boundaries for every
    layout, we simply SEARCH FOR A KNOWN COUNTRY NAME INSIDE the cell. That is
    layout-independent, so it survives format changes.
    """
    if not isinstance(s, str) or not s.strip():
        return None
    raw = s.strip()

    # exact match wins
    for c in AU_COUNTRIES:
        if raw.lower() == c.lower():
            return c

    # --- contaminated cell: look for a country name inside it ---
    # Longest names first, so "Central African Republic" wins over "Republic...".
    for c in sorted(AU_COUNTRIES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(c) + r"\b", raw, flags=re.I):
            return c

    key = re.sub(r"[^a-z ]", "", raw.lower()).strip()
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]

    # truncated at the column edge, e.g. "Democratic Republic of the Con"
    for c in AU_COUNTRIES:
        if len(key) >= 6 and c.lower().startswith(key[:len(key)]):
            return c

    # accent/character mangles, e.g. "Céte d'Ivoire" -> "Côte d'Ivoire".
    # compare letters-only, allowing a couple of wrong characters.
    from difflib import get_close_matches
    letters = re.sub(r"[^a-z]", "", raw.lower())
    cands = {re.sub(r"[^a-z]", "", c.lower()): c for c in AU_COUNTRIES}
    m = get_close_matches(letters, list(cands), n=1, cutoff=0.82)
    if m:
        return cands[m[0]]

    return raw   # unrecognized -> keep as-is; the validator will flag it