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
# Disease names as they appear in the bulletins. Order matters: we match the
# LONGEST names first so "Meningitis (Bacterial)" wins over bare "Meningitis"
# and "Corynebacterium diphtheriae" is not mistaken for something shorter.
#
# Each entry maps a pattern found in the OCR'd cell -> the canonical name we store.
# A long name can WRAP ONTO TWO LINES in the PDF (e.g. "Corynebacterium" on one
# line, "diphtheriae" on the next), so we must recognise EITHER fragment on its own.
DISEASE_PATTERNS = [
    # --- multi-word / most specific FIRST ---
    ("Corynebacterium diphtheriae", "Diphtheria"),
    ("Corynebacterium",             "Diphtheria"),   # first line of a wrapped name
    ("diphtheriae",                 "Diphtheria"),   # second line of a wrapped name
    ("Diphtheria",                  "Diphtheria"),
    ("Meningitis (Bacterial)",      "Meningitis (Bacterial)"),
    ("Meningitis",                  "Meningitis (Bacterial)"),
    ("Polio virus (vaccine-derived)", "Polio (vaccine-derived)"),
    ("vaccine-derived",             "Polio (vaccine-derived)"),
    ("Poliovirus",                  "Polio (vaccine-derived)"),
    ("Polio",                       "Polio (vaccine-derived)"),
    ("Rift Valley Fever virus",     "Rift Valley fever"),
    ("Rift Valley",                 "Rift Valley fever"),
    ("Sudan Ebola virus",           "Ebola"),
    ("Sudan Ebola",                 "Ebola"),
    ("Ebola",                       "Ebola"),
    ("Vibrio cholerae",             "Cholera"),
    ("cholerae",                    "Cholera"),
    ("Cholera",                     "Cholera"),
    ("Lassa virus",                 "Lassa fever"),
    ("Lassa",                       "Lassa fever"),
    ("West Nile virus",             "West Nile"),
    ("West Nile",                   "West Nile"),
    ("Influenza H5N1",              "Influenza H5N1"),
    ("H5N1",                        "Influenza H5N1"),
    ("Yellow fever",                "Yellow fever"),
    ("Marburg",                     "Marburg"),
    ("Chikungunya",                 "Chikungunya"),
    ("Measles",                     "Measles"),
    ("Mpox",                        "Mpox"),
    ("Monkeypox",                   "Mpox"),
    ("Dengue",                      "Dengue"),
    ("Anthrax",                     "Anthrax"),
    ("Hepatitis",                   "Hepatitis"),
    ("COVID-19",                    "COVID-19"),
    ("SARS-CoV-2",                  "COVID-19"),
    ("Influenza",                   "Influenza"),
    ("Malaria",                     "Malaria"),
    ("Typhoid",                     "Typhoid"),
    ("Rabies",                      "Rabies"),
    ("Plague",                      "Plague"),
]

KNOWN_DISEASES = [canonical for _, canonical in DISEASE_PATTERNS]

VALID_RISK = ["Very High", "Very Low", "Moderate", "High", "Low"]


def _clean_disease(s):
    """Recover the canonical disease name from an OCR'd cell.

    The cell arrives with the disease ICON glued on ("$8 Measles virus", "* mpox")
    and long names may be split across two lines, so we search for any known
    disease pattern inside the text and map it to a canonical name.
    """
    if not isinstance(s, str) or not s.strip():
        return None
    for pattern, canonical in DISEASE_PATTERNS:   # ordered longest/most-specific first
        if re.search(re.escape(pattern), s, flags=re.I):
            return canonical
    return None                              # unrecognized -> blank; validator flags it


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


# Columns the extractor is expected to hand us. If a bulletin's layout means one
# was never detected, we create it EMPTY rather than crashing -- the validator's
# missing/blank checks will then surface it as a data problem instead of the whole
# bulletin dying with a KeyError.
REQUIRED_INPUT_COLUMNS = [
    "Agent/Syndrome", "Country", "Risk:Human", "Risk:Animal",
    "Type", "Suspected", "Probable", "Confirmed", "Deaths",
]


REQUIRED_RAW_COLUMNS = ["Agent/Syndrome", "Country"]


def clean_table(df):
    """Raw extracted table -> tidy analysis-ready rows.

    Returns an EMPTY dataframe if the extracted table lacks the columns we need.
    Some bulletins contain a different table (e.g. only "New events since last
    issue") whose header does not include Agent/Syndrome; previously that raised
    a KeyError and crashed the whole batch run.
    """
    df = df.copy()

    missing = [c for c in REQUIRED_RAW_COLUMNS if c not in df.columns]
    if missing:
        return pd.DataFrame()

    # Defensive: never assume a column exists. Bulletin layouts vary by year, and
    # a missing header used to crash the whole file (KeyError: 'Agent/Syndrome').
    for col in REQUIRED_INPUT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # 1. disease name: strip icons, then forward-fill down the country rows.
    #
    #    IMPORTANT: forward-fill is only correct for the bulletin's real layout,
    #    where a disease is printed once and its countries listed beneath it. If a
    #    disease name fails to be RECOGNIZED, a naive ffill would paste the
    #    PREVIOUS disease over it -- silently mislabelling the row (this is how
    #    "Corynebacterium diphtheriae / Mali" once became "Cholera / Mali").
    #    So we distinguish "blank because it continues the row above" from
    #    "non-blank but unrecognized", and flag the latter as UNKNOWN so the
    #    validator can catch it rather than letting it pass as valid data.
    raw_names = df["Agent/Syndrome"]
    cleaned = raw_names.apply(_clean_disease)

    had_text = raw_names.notna() & (raw_names.astype(str).str.strip() != "")
    unrecognized = had_text & cleaned.isna()
    # Keep the ORIGINAL OCR text alongside the marker, so the validation report
    # tells you exactly what to add to DISEASE_PATTERNS instead of just "UNKNOWN".
    cleaned = cleaned.mask(
        unrecognized,
        "UNKNOWN: " + raw_names.where(unrecognized).astype(str).str.strip()
    )

    df["Agent/Syndrome"] = cleaned.ffill()

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

    # 3. repair counts that OCR packed into the wrong column (multi-word
    #    country names push figures sideways), then split "total (new)".
    df = _repair_shifted_counts(df)

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


# ---------- COLUMN-SHIFT REPAIR ----------
# A multi-word country name ("South Africa", "Central African Republic") is wider
# than the Country column, so it pushes the first count into the neighbouring
# cell. The result is a cell holding TWO "n (n)" figures while the next column is
# empty. We detect that and push the surplus figure back where it belongs.

_COUNT_TOKEN = re.compile(r"[\d,]+\s*\(\s*[\d,]+\s*\)")

COUNT_COLUMNS = ["Suspected", "Probable", "Confirmed", "Deaths"]


def _repair_shifted_counts(df):
    """Redistribute count figures that OCR packed into the wrong column."""
    cols = [c for c in COUNT_COLUMNS if c in df.columns]
    if len(cols) < 2:
        return df

    for i in df.index:
        # walk left-to-right; if a cell holds >1 figure, push the extras right
        for j, col in enumerate(cols):
            val = df.at[i, col]
            if not isinstance(val, str):
                continue
            found = _COUNT_TOKEN.findall(val)
            if len(found) <= 1:
                continue

            # keep the first figure here, cascade the rest into the columns to
            # the right -- but only into cells that are currently empty, so we
            # never overwrite a genuine value.
            df.at[i, col] = found[0]
            surplus = found[1:]
            for nxt in cols[j + 1:]:
                if not surplus:
                    break
                cur = df.at[i, nxt]
                if not isinstance(cur, str) or not _COUNT_TOKEN.search(str(cur)):
                    df.at[i, nxt] = surplus.pop(0)
    return df