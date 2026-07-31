"""
spotcheck_one.py — Run ONE bulletin through the existing pipeline functions
(OCR -> extract -> clean) and print the resulting rows, so we can judge how good
extraction is on the 2026 files before batch-processing all of them.

Reuses the real pipeline code (src.ocr / src.extract / src.clean) — nothing
reimplemented. Run from the project root:

    python analysis\\spotcheck_one.py "2026-06-07"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PDF_FOLDER, OCR_CACHE
from src.ocr import ensure_searchable, is_searchable
from src.extract import extract_highlighted_table, extract_date_from_filename
from src import clean as clean_mod

# The date to test (default 2026-06-07). Pass another as the first argument.
date = sys.argv[1] if len(sys.argv) > 1 else "2026-06-07"
filename = f"EBS Weekly Report {date}.pdf"
raw_path = Path(PDF_FOLDER) / filename

print(f"FILE: {filename}")
if not raw_path.exists():
    print(f"  not found at {raw_path}")
    sys.exit(1)

# STEP 1: OCR (cached) if needed
if is_searchable(str(raw_path)):
    pdf_path = str(raw_path)
    print("  text layer: already present")
else:
    pdf_path = str(ensure_searchable(str(raw_path), OCR_CACHE))
    print("  text layer: OCR'd (cache)")

# STEP 2: extract the highlighted table
raw = extract_highlighted_table(pdf_path)
print("\n=== RAW EXTRACTED TABLE ===")
if raw is None:
    print("  extract returned None (no table found)")
    sys.exit(0)
print("shape:", raw.shape)
print(raw.to_string())

# STEP 3: clean — support whichever function name your clean.py exposes
clean_fn = getattr(clean_mod, "clean_dataframe", None) or getattr(clean_mod, "clean_table", None)
print("\n=== CLEANED TABLE ===")
if clean_fn is None:
    print("  (no clean_dataframe/clean_table found in src.clean)")
    sys.exit(0)
try:
    cleaned = clean_fn(raw.copy())
    print("shape:", cleaned.shape)
    print("columns:", list(cleaned.columns))
    print(cleaned.to_string())
except Exception as e:
    import traceback
    print("  clean() raised:")
    traceback.print_exc()