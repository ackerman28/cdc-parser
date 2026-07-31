"""
Automatically read the reporting date printed INSIDE each new Africa CDC bulletin
and rename the file to the clean `EBS Weekly Report YYYY-MM-DD.pdf` convention.

Why read inside the PDF instead of the filename?
The 20 new files use ~6 inconsistent naming schemes and some contain only an
epi-week number (which we found to be internally contradictory). The date printed
on the bulletin cover is the ground truth.

Run from the project root (D:\\cdc-parser), with the venv active:
    python analysis\\rename_new_bulletins.py            # dry run: shows plan, renames nothing
    python analysis\\rename_new_bulletins.py --apply     # actually renames

Safe by design: dry-run first, never overwrites an existing file, flags
duplicates/failures for you to eyeball before anything is touched.
"""
import re
import sys
import shutil
from pathlib import Path
from datetime import date, timedelta

import pdfplumber
from dateutil import parser as dateparser

# Use the project's existing OCR module (Week 3) so we don't duplicate OCR logic.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from src.ocr import ensure_searchable
    HAVE_OCR = True
except Exception:
    HAVE_OCR = False

RAW_DIR = Path("data/raw_pdfs")
OCR_CACHE = Path("data/ocr_cache")
MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
          "November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec")

# Files that already follow the clean convention -> leave alone.
ALREADY_CLEAN = re.compile(r"^EBS Weekly Report \d{4}-\d{2}-\d{2}\.pdf$", re.IGNORECASE)


def _read_first_page(pdf_path, max_pages=1):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return " ".join((p.extract_text() or "") for p in pdf.pages[:max_pages])
    except Exception:
        return ""


def cover_text(pdf_path, max_pages=1, do_ocr=True):
    """Return first-page text. If the file has no text layer, OCR it first using
    the project's cached ocr.ensure_searchable (Week 3 module)."""
    txt = _read_first_page(pdf_path, max_pages)
    if txt.strip():
        return txt
    if do_ocr and HAVE_OCR:
        try:
            searchable = ensure_searchable(pdf_path, OCR_CACHE)
            return _read_first_page(searchable, max_pages)
        except Exception as e:
            print(f"    [ocr failed] {Path(pdf_path).name}: {e}")
            return ""
    return ""


def extract_report_date(text):
    """(iso_str, method). Prefer the labelled 'Date of Issue' on the cover,
    which is the authoritative report date. Then fall back to range end, single
    date, or epi-week."""
    t = " ".join(text.split())

    # 0. "Date of Issue: 2026-07-05"  OR  "Date of Issue: 13 Mar 2026"
    doi = re.search(r"Date\s+of\s+Issue\s*:?\s*"
                    r"(\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\.?\s+\d{4})",
                    t, re.IGNORECASE)
    if doi:
        raw = doi.group(1)
        try:
            if re.match(r"\d{4}-\d{2}-\d{2}", raw):
                return raw, "date-of-issue"
            return dateparser.parse(raw, dayfirst=True, fuzzy=True).date().isoformat(), "date-of-issue"
        except Exception:
            pass

    rng = re.search(
        rf"(\d{{1,2}}\s+(?:{MONTHS})\.?\s*\d{{0,4}})\s*[-\u2013\u2014]|to\s*(\d{{1,2}}\s+(?:{MONTHS})\.?\s+\d{{4}})",
        t, re.IGNORECASE)
    rng = re.search(
        rf"(\d{{1,2}}\s+(?:{MONTHS})\.?\s*\d{{0,4}})\s*(?:[-\u2013\u2014]|to)\s*(\d{{1,2}}\s+(?:{MONTHS})\.?\s+\d{{4}})",
        t, re.IGNORECASE)
    if rng:
        try:
            return dateparser.parse(rng.group(2), dayfirst=True, fuzzy=True).date().isoformat(), "range-end"
        except Exception:
            pass

    single = re.search(rf"(\d{{1,2}}\s+(?:{MONTHS})\.?\s+\d{{4}})", t, re.IGNORECASE)
    if single:
        try:
            return dateparser.parse(single.group(1), dayfirst=True, fuzzy=True).date().isoformat(), "single-date"
        except Exception:
            pass

    single2 = re.search(rf"((?:{MONTHS})\.?\s+\d{{1,2}},?\s+\d{{4}})", t, re.IGNORECASE)
    if single2:
        try:
            return dateparser.parse(single2.group(1), fuzzy=True).date().isoformat(), "single-date"
        except Exception:
            pass

    ew = re.search(r"(?:epi[\s-]*week|week)\D{0,4}(\d{1,2})\D{0,10}(20\d{2})", t, re.IGNORECASE)
    if ew:
        wk, yr = int(ew.group(1)), int(ew.group(2))
        jan4 = date(yr, 1, 4)
        wk1_mon = jan4 - timedelta(days=jan4.isoweekday() - 1)
        sunday = wk1_mon + timedelta(weeks=wk - 1, days=6)
        return sunday.isoformat(), f"epiweek-{wk}"

    return None, "FAILED"


def main(apply=False, do_ocr=True):
    if not RAW_DIR.exists():
        print(f"ERROR: {RAW_DIR} not found. Run from the project root (D:\\cdc-parser).")
        sys.exit(1)

    if do_ocr and not HAVE_OCR:
        print("WARNING: could not import src.ocr — running without OCR. "
              "Files with no text layer will be flagged, not read.\n")

    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    todo = [p for p in pdfs if not ALREADY_CLEAN.match(p.name)]
    print(f"{len(pdfs)} PDFs total | {len(todo)} need renaming | "
          f"{len(pdfs)-len(todo)} already clean")
    if do_ocr and HAVE_OCR:
        print("(OCR runs on any file with no text layer; first pass is slow, then cached)")
    print()

    plan = []          # (src_path, target_name, iso, method)
    failures = []
    for p in todo:
        txt = cover_text(p, do_ocr=do_ocr)
        if not txt.strip():
            failures.append((p.name, "NO TEXT LAYER (OCR unavailable or failed)"))
            continue
        iso, method = extract_report_date(txt)
        if iso is None:
            failures.append((p.name, "could not find a date on the cover"))
            continue
        plan.append((p, f"EBS Weekly Report {iso}.pdf", iso, method))

    # Detect collisions: two source files resolving to the same date, or a target
    # that already exists on disk.
    from collections import Counter
    target_counts = Counter(t for _, t, _, _ in plan)
    existing = {p.name for p in pdfs}

    print("=== RENAME PLAN ===")
    print(f"{'RESOLVED':<12} {'METHOD':<12} {'->':<3} SOURCE")
    for src, target, iso, method in sorted(plan, key=lambda x: x[2]):
        dup = "  <DUP DATE>" if target_counts[target] > 1 else ""
        clash = "  <TARGET EXISTS>" if (target in existing and target != src.name) else ""
        print(f"{iso:<12} {method:<12} ->  {src.name}{dup}{clash}")

    if failures:
        print("\n=== NEEDS ATTENTION (not renamed) ===")
        for name, why in failures:
            print(f"  ! {name}  --  {why}")

    dups = [t for t, c in target_counts.items() if c > 1]
    if dups:
        print("\n=== DUPLICATE DATES (review before applying) ===")
        for t in dups:
            print(f"  {t}: from {[s.name for s,tt,_,_ in plan if tt==t]}")

    if not apply:
        print("\nDRY RUN — nothing renamed. Re-run with --apply once the plan looks right.")
        return

    # Apply: skip anything involved in a duplicate/clash for safety.
    print("\n=== APPLYING ===")
    renamed = 0
    for src, target, iso, method in plan:
        if target_counts[target] > 1:
            print(f"  SKIP (dup): {src.name}")
            continue
        dest = src.with_name(target)
        if dest.exists() and dest != src:
            print(f"  SKIP (exists): {target}")
            continue
        src.rename(dest)
        print(f"  {src.name}  ->  {target}")
        renamed += 1
    print(f"\nDone. Renamed {renamed} file(s). "
          f"{len(failures)+len(dups)} left for manual review.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv, do_ocr="--no-ocr" not in sys.argv)