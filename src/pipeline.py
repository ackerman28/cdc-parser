"""
pipeline.py — Run the full extract -> clean process over every PDF in PDF_FOLDER
and write one combined dataset.

This is Camellia's master loop (bottom of her Stage 0 cell), reorganized to import
from extract.py and clean.py and to use the paths in config.py. LOGIC UNCHANGED.

Run from the project root with:
    python -m src.pipeline
"""

import os
import pandas as pd

from src.config import PDF_FOLDER, OUTPUT_FILE
from src.extract import extract_date_from_filename, extract_highlighted_table
from src.clean import clean_dataframe


def run():
    master_dfs = []

    for filename in os.listdir(PDF_FOLDER):

        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(PDF_FOLDER, filename)
        print("Processing:", filename)

        report_date = extract_date_from_filename(filename)
        df = extract_highlighted_table(pdf_path)

        if df is None:
            print("  [warning] No table detected (file may need OCR)")
            continue

        df = clean_dataframe(df)
        df.insert(0, "Report Date", report_date)
        master_dfs.append(df)

    if len(master_dfs) == 0:
        raise Exception(
            "No tables extracted from any PDFs. "
            "Raw CDC bulletins have no text layer -- they must be OCR'd first."
        )

    master_df = pd.concat(master_dfs, ignore_index=True)
    master_df.sort_values("Report Date", inplace=True)

    # Make sure the output folder exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    master_df.to_excel(OUTPUT_FILE, index=False)

    print("MASTER DATASET CREATED:", OUTPUT_FILE)
    print("Rows:", len(master_df))


if __name__ == "__main__":
    run()
