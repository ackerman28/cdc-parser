"""
pipeline.py — Full pipeline: OCR -> extract -> clean -> validate.

Run from the project root:
    python -m src.pipeline

WHAT CHANGED IN WEEK 4
----------------------
Extraction is now COORDINATE-BASED (extract.py), not flat-text based. Tesseract
reads a table in column-blocks, so reading its output as flat text detached the
case counts from their rows -- the numbers came out as garbage. We now read every
word WITH ITS X/Y POSITION and rebuild the table from the page geometry.

Because the columns now land in the right places, the long chain of post-hoc OCR
patches is no longer needed: clean.py is short and predictable.

Note: extract.py OCRs the page images itself, so it works directly on the RAW
scanned bulletin. A separate OCR'd PDF is no longer required.
"""

import os
import pandas as pd

from src.config import PDF_FOLDER, OUTPUT_FILE, VALIDATION_REPORT
from src.extract import extract_highlighted_table, extract_date_from_filename
from src.clean import clean_table
from src.validate import validate


def run():
    master_dfs = []
    failed = []

    for filename in sorted(os.listdir(PDF_FOLDER)):
        if not filename.lower().endswith(".pdf"):
            continue

        path = os.path.join(PDF_FOLDER, filename)
        print("Processing:", filename)

        try:
            raw = extract_highlighted_table(path)
        except Exception as e:
            print(f"  [error] {e}")
            failed.append(filename)
            continue

        if raw is None or raw.empty:
            print("  [warning] no highlighted-events table found")
            failed.append(filename)
            continue

        df = clean_table(raw)
        df.insert(0, "Report Date", extract_date_from_filename(filename))
        master_dfs.append(df)
        print(f"  -> {len(df)} rows")

    if not master_dfs:
        raise Exception("No tables extracted from any PDFs.")

    master = pd.concat(master_dfs, ignore_index=True)
    master.sort_values(["Report Date", "Agent/Syndrome", "Country"], inplace=True)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    master.to_excel(OUTPUT_FILE, index=False)

    print(f"\nMASTER DATASET: {OUTPUT_FILE}")
    print(f"Rows: {len(master)}   Bulletins parsed: {len(master_dfs)}")
    if failed:
        print(f"Bulletins that produced no table ({len(failed)}): {failed}")

    report = validate(master)
    report.print_summary()
    report.to_excel(str(VALIDATION_REPORT))


if __name__ == "__main__":
    run()