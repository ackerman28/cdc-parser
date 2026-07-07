"""
pipeline.py — Full pipeline: OCR -> extract -> clean -> validate, over every
bulletin in PDF_FOLDER, writing one combined dataset plus a validation report.

Run from the project root:
    python -m src.pipeline

The steps:
  1. OCR   (ocr.py)      -- add a text layer to each scanned bulletin (cached)
  2. EXTRACT (extract.py)-- pull the "Events Highlighted This Week" table
  3. CLEAN  (clean.py)   -- repair OCR/column-drift, standardize columns
  4. VALIDATE (validate.py) -- flag any remaining bad rows into a report
"""

import os
import pandas as pd

from src.config import PDF_FOLDER, OCR_CACHE, OUTPUT_FILE, VALIDATION_REPORT
from src.ocr import ensure_searchable, is_searchable
from src.extract import extract_date_from_filename, extract_highlighted_table
from src.clean import clean_dataframe
from src.validate import validate


def run():
    master_dfs = []

    for filename in sorted(os.listdir(PDF_FOLDER)):
        if not filename.lower().endswith(".pdf"):
            continue

        raw_path = os.path.join(PDF_FOLDER, filename)
        print("Processing:", filename)

        # STEP 1: make sure the PDF has a text layer (OCR if needed, cached)
        if is_searchable(raw_path):
            pdf_path = raw_path            # already has text, use as-is
        else:
            pdf_path = ensure_searchable(raw_path, OCR_CACHE)

        # STEP 2: extract the highlighted table
        report_date = extract_date_from_filename(filename)
        df = extract_highlighted_table(str(pdf_path))

        if df is None:
            print("  [warning] No table detected even after OCR")
            continue

        # STEP 3: clean
        df = clean_dataframe(df)
        df.insert(0, "Report Date", report_date)
        master_dfs.append(df)

    if len(master_dfs) == 0:
        raise Exception("No tables extracted from any PDFs.")

    master_df = pd.concat(master_dfs, ignore_index=True)
    master_df.sort_values("Report Date", inplace=True)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    master_df.to_excel(OUTPUT_FILE, index=False)
    print("\nMASTER DATASET CREATED:", OUTPUT_FILE)
    print("Rows:", len(master_df))

    # STEP 4: validate and write the quality report
    report = validate(master_df)
    report.print_summary()
    report.to_excel(str(VALIDATION_REPORT))


if __name__ == "__main__":
    run()