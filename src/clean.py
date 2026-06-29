"""
clean.py — Repair and standardize the raw extracted table.

Ported faithfully from Camellia's master notebook (the clean_dataframe logic).
LOGIC UNCHANGED. This is the long sequence of OCR/column-drift repairs she wrote.
In later stages we will move correctness upstream and retire the patches that are
no longer needed, but for now this preserves her exact behavior.
"""

import re
import pandas as pd


def ensure_required_columns(df, required_cols):
    """
    Guarantees required columns exist without altering overflow data.
    Missing ones are created as NA.
    """

    for col in required_cols:
        if col not in df.columns:
            df[col] = pd.NA

    return df

def clean_dataframe(df):

    # ---------- STANDARD CLEAN ----------
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    df.replace(r'^\s*$', pd.NA, regex=True, inplace=True)

    # ---------- DROP EMPTY ----------
    df.dropna(axis=0, how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)

    # ---------- FIX OCR ERROR ----------
    df.replace(r"\(OJ\)?", "(0)", regex=True, inplace=True)
    df.replace(r"OJ", "0)", regex=True, inplace=True)

    df.replace(r"\bNIA\b", "N/A", regex=True, inplace=True)
    df.replace(r"\bN[\/\-\s]?A\b", "N/A", regex=True, inplace=True)

    # ---------- SYMBOL ONLY COL DROP ----------
    def is_symbol_only_column(series):
        s = series.dropna().astype(str)
        if len(s) == 0:
            return True
        return not s.str.contains(r"[A-Za-z0-9]").any()

    cols_to_drop = [c for c in df.columns if is_symbol_only_column(df[c])]
    df.drop(columns=cols_to_drop, inplace=True)



    # ---------- FIX MODER | ATE SPLIT ----------

    cols = list(df.columns)

    for i in range(len(cols) - 1):

        col_left = cols[i]
        col_right = cols[i + 1]

        left_vals = df[col_left].astype(str).str.strip().str.lower()
        right_vals = df[col_right].astype(str).str.strip().str.lower()

        moder_mask = left_vals == "moder"
        ate_mask = right_vals == "ate"

        if (moder_mask & ate_mask).sum() > 0:
            print(f"Fixing Moder | ate split between {col_left} and {col_right}")

            df.loc[moder_mask & ate_mask, col_left] = "Moderate"
            df.drop(columns=[col_right], inplace=True)

            break  # Only expect one such split





    # ---------- MERGE BRACKET COLS ----------
    def is_bracket_number_col(series):
        s = series.dropna().astype(str)
        if len(s) == 0:
            return False
        return s.str.match(r"^\(\d+\)$").mean() > 0.6

    cols = list(df.columns)
    i = 0
    while i < len(cols) - 1:
        if is_bracket_number_col(df[cols[i+1]]):
            df[cols[i]] = (
                df[cols[i]].fillna("").astype(str).str.strip() + " " +
                df[cols[i+1]].fillna("").astype(str).str.strip()
            ).str.strip()

            df.drop(columns=[cols[i+1]], inplace=True)
            cols.pop(i+1)
        else:
            i += 1


    # ---------- MERGE SPLIT BRACKET TOKENS ----------
    def ends_with_open_bracket(series):
        s = series.dropna().astype(str)
        if len(s) == 0:
            return False
        return s.str.strip().str.endswith("(").mean() > 0.5


    def starts_with_number_close_bracket(series):
        s = series.dropna().astype(str)
        if len(s) == 0:
            return False
        return s.str.strip().str.match(r"^\d+\)$").mean() > 0.5


    cols = list(df.columns)
    i = 0

    while i < len(cols) - 1:
        col_left = cols[i]
        col_right = cols[i + 1]

        if ends_with_open_bracket(df[col_left]) and starts_with_number_close_bracket(df[col_right]):
            # Merge like: "116 (" + "29)" → "116 (29)"
            df[col_left] = (
                df[col_left].fillna("").astype(str).str.rstrip() +
                df[col_right].fillna("").astype(str).str.lstrip()
            )

            # Clean accidental double spaces
            df[col_left] = df[col_left].str.replace(r"\s+", " ", regex=True).str.strip()

            df.drop(columns=[col_right], inplace=True)
            cols.pop(i + 1)

        else:
            i += 1


    # ---------- FIX RIGHT-SHIFTED NUMBERS AFTER BRACKETS ----------
    def split_trailing_number(text):
        """
        Detect pattern: '0 (0) 29'
        Returns: ('0 (0)', '29') or (text, None)
        """
        if pd.isna(text):
            return text, None

        text = str(text).strip()

        m = re.match(r"^(.*\(\d+\))\s+(\d+)$", text)
        if m:
            return m.group(1), m.group(2)
        return text, None


    def split_leading_number(text):
        """
        Detect pattern: '9 (153)'
        Returns: ('9', '(153)') or (None, None)
        """
        if pd.isna(text):
            return None, None

        text = str(text).strip()

        m = re.match(r"^(\d+)\s*(\(\d+\))$", text)
        if m:
            return m.group(1), m.group(2)
        return None, None


    cols = list(df.columns)

    for i in range(len(cols) - 1):
        col_left = cols[i]
        col_right = cols[i + 1]

        for idx in df.index:

            left_val = df.at[idx, col_left]
            right_val = df.at[idx, col_right]

            left_main, left_extra = split_trailing_number(left_val)

            if left_extra is not None:
                right_num, right_bracket = split_leading_number(right_val)

                if right_num is not None:
                    # Move digit
                    new_right_num = left_extra + right_num

                    df.at[idx, col_left] = left_main
                    df.at[idx, col_right] = f"{new_right_num} {right_bracket}"


        # ---------- FIX LEFT-STRANDED BRACKET VALUES ----------
    def split_leading_bracket_then_number(text):
        """
        Detect pattern: '(0) 1'
        Returns: ('(0)', '1') or (None, None)
        """
        if pd.isna(text):
            return None, None

        text = str(text).strip()

        m = re.match(r"^(\(\d+\))\s+(\d+.*)$", text)
        if m:
            return m.group(1), m.group(2)

        return None, None


    cols = list(df.columns)

    for i in range(1, len(cols)):  # start from col 1 (needs left column)
        col_left = cols[i - 1]
        col_current = cols[i]

        for idx in df.index:

            current_val = df.at[idx, col_current]

            bracket_part, remaining_part = split_leading_bracket_then_number(current_val)

            if bracket_part is not None:

                # Attach bracket to LEFT column
                left_val = df.at[idx, col_left]

                df.at[idx, col_left] = (
                    str(left_val).strip() + " " + bracket_part
                ).strip()

                # Keep remaining part in current column
                df.at[idx, col_current] = remaining_part.strip()


    # ---------- FINAL NUMBER + BRACKET COLUMN REPAIR ----------
    def is_plain_number(text):
        if pd.isna(text):
            return False
        return bool(re.match(r"^\d+$", str(text).strip()))

    def is_bracket_number(text):
        if pd.isna(text):
            return False
        return bool(re.match(r"^\(\d+\)$", str(text).strip()))

    cols = list(df.columns)

    for i in range(len(cols) - 1):

        col_left = cols[i]
        col_right = cols[i + 1]

        for idx in df.index:

            left_val = df.at[idx, col_left]
            right_val = df.at[idx, col_right]

            if is_plain_number(left_val) and is_bracket_number(right_val):

                df.at[idx, col_left] = f"{left_val} {right_val}"
                df.at[idx, col_right] = pd.NA





    # ---------- DROP SINGLE-ROW TEXT SPILL COLUMNS ----------

    def is_single_text_spill_column(series):

        s = series.dropna().astype(str).str.strip()

        if len(s) == 0:
            return False

        # Only 1–2 populated cells
        if len(s) > 2:
            return False

        # No numbers → likely text spill
        if s.str.contains(r"\d").any():
            return False

        # Contains real text
        if not s.str.contains(r"[A-Za-z]").any():
            return False

        return True


    spill_cols = [c for c in df.columns if is_single_text_spill_column(df[c])]

    if spill_cols:
        print("Dropping single-row spill columns:", spill_cols)
        df.drop(columns=spill_cols, inplace=True)




    # ---------- SOFT SCHEMA (KEEP SPILLOVERS) ----------

    expected_headers = [
        "Agent/Syndrome",
        "Country",
        "Risk Human",
        "Risk Animal",
        "Type",
        "Suspected (new)",
        "Probable (new)",
        "Confirmed (new)",
        "Deaths (new)"
    ]

    current_cols = list(df.columns)

    # Rename what we actually have
    rename_map = {}
    for i in range(min(len(expected_headers), len(current_cols))):
        rename_map[current_cols[i]] = expected_headers[i]

    df.rename(columns=rename_map, inplace=True)

    # Preserve overflow columns
    extra_cols = current_cols[len(expected_headers):]
    for i, col in enumerate(extra_cols):
        df.rename(columns={col: f"__overflow_{i+1}"}, inplace=True)

    # ⭐ Ensure required columns ALWAYS exist (prevents KeyError)
    df = ensure_required_columns(df, expected_headers)


    # ---------- MULTI-LINE ROW REPAIR ENGINE ----------

    def row_has_numbers(row):
        text = " ".join([str(x) for x in row if pd.notna(x)])
        return bool(re.search(r"\d", text))

    def safe_text(val):
        return str(val).strip() if pd.notna(val) else ""

    rows_to_drop = []

    i = 0
    while i < len(df) - 1:

        row_curr = df.iloc[i]
        row_next = df.iloc[i+1]

        curr_has_nums = row_has_numbers(row_curr)
        next_has_nums = row_has_numbers(row_next)

        # =================================================
        # ⭐ AGENT SPLIT CASE
        # Fragment → Data → Fragment
        # =================================================
        if (
            safe_text(row_curr["Agent/Syndrome"]) != ""
            and not curr_has_nums
            and next_has_nums
        ):

            agent_text = safe_text(row_curr["Agent/Syndrome"])

            # Check if trailing fragment exists
            if i+2 < len(df):
                row_next2 = df.iloc[i+2]

                if (
                    safe_text(row_next2["Agent/Syndrome"]) != ""
                    and not row_has_numbers(row_next2)
                ):
                    agent_text += " " + safe_text(row_next2["Agent/Syndrome"])
                    rows_to_drop.append(i+2)

            df.at[df.index[i+1], "Agent/Syndrome"] = agent_text
            rows_to_drop.append(i)

            i += 2
            continue

        # =================================================
        # ⭐ COUNTRY SPLIT CASE
        # =================================================
        if (
            safe_text(row_curr["Country"]) != ""
            and not curr_has_nums
            and next_has_nums
            and safe_text(row_next["Country"]) == ""
        ):

            country_text = safe_text(row_curr["Country"])

            if i+2 < len(df):
                row_next2 = df.iloc[i+2]

                if (
                    safe_text(row_next2["Country"]) != ""
                    and not row_has_numbers(row_next2)
                ):
                    country_text += " " + safe_text(row_next2["Country"])
                    rows_to_drop.append(i+2)

            df.at[df.index[i+1], "Country"] = country_text
            rows_to_drop.append(i)

            i += 2
            continue

        i += 1

    df.drop(df.index[rows_to_drop], inplace=True)
    df.reset_index(drop=True, inplace=True)

        # ---------- GUARD: NULL OUT TAIL-FRAGMENT AGENT VALUES ----------

    agent_series = df["Agent/Syndrome"].astype("string")

    for i in range(1, len(df)):
        curr = str(agent_series.iloc[i]).strip() if pd.notna(agent_series.iloc[i]) else ""
        prev = str(agent_series.iloc[i-1]).strip() if pd.notna(agent_series.iloc[i-1]) else ""

        if curr and prev:
            if (len(curr.split()) == 1) and (len(prev.split()) >= 2) and prev.lower().endswith(curr.lower()):
                df.at[df.index[i], "Agent/Syndrome"] = pd.NA



    # ---------- FORWARD FILL ----------
    df["Agent/Syndrome"] = (
        df["Agent/Syndrome"]
        .replace(["", " ", "<NA>"], pd.NA)
        .ffill()
    )

    # ---------- CLEAN LEADING SYMBOLS ----------
    df["Agent/Syndrome"] = df["Agent/Syndrome"].apply(
        lambda x: re.sub(r"^[^A-Za-z0-9]+", "", str(x)).strip() if pd.notna(x) else x
    )

    # ---------- FINAL TRIM ----------
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    return df
