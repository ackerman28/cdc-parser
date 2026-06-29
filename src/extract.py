"""
extract.py — Pull the "Events Highlighted This Week" table out of an Africa CDC
EBS bulletin PDF.

Ported faithfully from Camellia's master notebook (Stage 0: Extraction).
LOGIC UNCHANGED. Only difference from the notebook: no Google Drive / Colab code,
and the file paths are configured in pipeline.py instead of hard-coded here.

NOTE: These functions assume the PDF already has a text layer (i.e. OCR has been
run). Raw CDC bulletins are scanned images with no text layer, so extraction will
return None on a raw file. Automated OCR is added in a later stage of the project.
"""

import os
import re
import pdfplumber
import pandas as pd


def extract_date_from_filename(filename):
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", filename)
    return m.group(1) if m else None


# ---------- OCR NORMALIZATION ----------
def normalize_ocr_text(text):
    if text is None:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


# ---------- HEADER DETECTION ----------
def is_header_row(row):

    row_text = " ".join([str(x) for x in row if x is not None])
    norm = normalize_ocr_text(row_text)

    header_signals = [
        "agent",
        "syndrome",
        "country",
        "risk",
        "suspected",
        "confirmed",
        "deaths",
        "new"
    ]

    score = sum(word in norm for word in header_signals)
    return score >= 2


# ---------- FIND "EVENTS HIGHLIGHTED" SECTION ----------
def find_highlighted_start_page(pdf):

    phrase = "eventshighlightedthisweek"

    # Skip cover page, start checking from page 2 onward
    for i in range(1, len(pdf.pages)):

        text = pdf.pages[i].extract_text()
        norm = normalize_ocr_text(text)

        if phrase in norm:
            return i

    return None


# ---------- VALIDATE THAT TABLE IS REAL ----------
def is_real_highlighted_table(df):

    if df is None or len(df) < 2:
        return False

    joined = " ".join(df.astype(str).fillna("").values.flatten())
    norm = normalize_ocr_text(joined)

    required_terms = ["agent", "country", "risk", "syndrome", "deaths", "confirmed", "suspected", "new"]
    score = sum(term in norm for term in required_terms)

    return score >= 2 and df.shape[1] >= 5


# ---------- EXTRACT HIGHLIGHTED TABLE ----------
def extract_highlighted_table(pdf_path):

    with pdfplumber.open(pdf_path) as pdf:

        start_idx = find_highlighted_start_page(pdf)

        # No highlighted section exists → skip this PDF
        if start_idx is None:
            return None

        df = None

        # Search the section page and the following page
        for idx in [start_idx, start_idx + 1]:

            if idx >= len(pdf.pages):
                continue

            page = pdf.pages[idx]

            tables = page.extract_tables({
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "intersection_tolerance": 5
            })

            if len(tables) == 0:
                continue

            candidate = pd.DataFrame(tables[0])

            if is_real_highlighted_table(candidate):
                df = candidate
                break

        if df is None:
            return None

    # ---------- CLEAN USING YOUR ORIGINAL HEADER LOGIC ----------
    header_rows = []
    for i, row in df.iterrows():
        if is_header_row(row):
            header_rows.append(i)

    if len(header_rows) >= 2:
        df = df.iloc[header_rows[1] + 1:].reset_index(drop=True)
    elif len(header_rows) == 1:
        df = df.iloc[header_rows[0] + 1:].reset_index(drop=True)

    df = df[~df.apply(is_header_row, axis=1)].reset_index(drop=True)

    return df
