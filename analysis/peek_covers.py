import pdfplumber
from pathlib import Path

# A few failed files + one that "succeeded" so we can compare
files = [
    "data/ocr_cache/Africa-CDC_Epidemic-_Intelligence_Weekly_Report_4_June_2026.pdf",
    "data/ocr_cache/Africa-CDC_EI_Weekly_Report_Week-27-July-05-2026.pdf",
    "data/ocr_cache/Weekly-Epidemic-Intelligence-Report_Epi-week-23.pdf",
    "data/ocr_cache/Africa-CDC-Epidemic-Intelligence-Report_Epi-week-9.pdf",
]

for f in files:
    p = Path(f)
    print("="*70)
    print("FILE:", p.name)
    if not p.exists():
        print("  (not in ocr_cache — check the path)")
        continue
    with pdfplumber.open(p) as pdf:
        txt = pdf.pages[0].extract_text() or ""
    # Print the first 600 characters of the cover so we see the date region
    print(txt[:600])
    print()