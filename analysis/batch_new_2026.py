"""
batch_new_2026.py — Run the 20 newly-added 2026 bulletins through the existing
pipeline (OCR -> extract -> clean) and save the combined result for inspection.

Only processes files dated 2026-02-11 onward (i.e. AFTER the current dataset's
last week), so we don't reprocess the 157 files already in Africa_CDC_Merged.xlsx.

Run from the project root:
    python analysis\\batch_new_2026.py

Output: analysis/new_2026_rows.csv  (combined raw extraction of the new files)
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import PDF_FOLDER, OCR_CACHE
from src.ocr import ensure_searchable, is_searchable
from src.extract import extract_highlighted_table, extract_date_from_filename
from src import clean as clean_mod

# Cutoff: only process bulletins AFTER this date (the current data ends ~2026-01-28).
CUTOFF = "2026-02-01"

clean_fn = getattr(clean_mod, "clean_dataframe", None) or getattr(clean_mod, "clean_table", None)

date_re = re.compile(r"(\d{4}-\d{2}-\d{2})")

def new_files():
    out = []
    for p in sorted(Path(PDF_FOLDER).glob("*.pdf")):
        m = date_re.search(p.name)
        if m and m.group(1) >= CUTOFF:
            out.append((m.group(1), p))
    return out

def main():
    files = new_files()
    print(f"Found {len(files)} new bulletins (dated >= {CUTOFF})\n")

    frames, log = [], []
    for date, p in files:
        try:
            if is_searchable(str(p)):
                pdf_path = str(p)
            else:
                pdf_path = str(ensure_searchable(str(p), OCR_CACHE))

            raw = extract_highlighted_table(pdf_path)
            if raw is None or raw.empty:
                log.append((date, "no_table", 0)); print(f"  {date}: NO TABLE"); continue

            cleaned = clean_fn(raw.copy()) if clean_fn else raw
            cleaned.insert(0, "Report Date", date)
            frames.append(cleaned)
            log.append((date, "ok", len(cleaned)))
            print(f"  {date}: {len(cleaned)} rows")
        except Exception as e:
            log.append((date, f"ERROR: {e}", 0))
            print(f"  {date}: ERROR {e}")

    if not frames:
        print("\nNo rows extracted."); return

    combined = pd.concat(frames, ignore_index=True)
    out_path = Path(__file__).resolve().parent / "new_2026_rows.csv"
    combined.to_csv(out_path, index=False)

    print(f"\n=== SUMMARY ===")
    print(f"Files processed : {len(files)}")
    print(f"Files with table: {sum(1 for _,s,_ in log if s=='ok')}")
    print(f"Total rows      : {len(combined)}")
    print(f"Saved           : {out_path}")

    # Quick quality peek
    print(f"\nDiseases found: {sorted(combined['Agent/Syndrome'].dropna().unique())}")
    empty = combined[combined.filter(like='tot_').isna().all(axis=1)] if any('tot_' in c for c in combined.columns) else pd.DataFrame()
    print(f"All-NaN-count ghost rows: {len(empty)}")

if __name__ == "__main__":
    main()