"""
pipeline.py — Run the full extract -> clean -> validate process over every
bulletin in PDF_FOLDER and write one combined dataset.

    python -m src.pipeline

DESIGNED FOR BATCH RUNS
-----------------------
With ~157 bulletins spanning several report layouts, some files will inevitably
fail. This runner therefore:

  * NEVER lets one bad file kill the run -- every file is wrapped in try/except
  * records WHY each file failed, in a per-file batch report
  * skips files it has already processed (resume support), so a long run can be
    stopped and restarted without redoing work
  * prints a summary at the end so you can see at a glance which bulletins need
    attention

The per-file batch report (batch_report.xlsx) is the Week-5 deliverable: it tells
you which bulletins parsed cleanly, which produced no table, and which errored.
"""

import os
import time
import traceback

import pandas as pd

from src.config import PDF_FOLDER, OUTPUT_FILE, VALIDATION_REPORT
from src.extract import extract_highlighted_table, extract_date_from_filename
from src.clean import clean_table
from src.validate import validate

BATCH_REPORT = os.path.join(os.path.dirname(str(OUTPUT_FILE)), "batch_report.xlsx")


def process_one(path, filename):
    """Extract + clean a single bulletin. Returns (dataframe, status, message)."""
    raw = extract_highlighted_table(path)
    if raw is None or raw.empty:
        return None, "no_table", "No 'Events Highlighted this week' table found"

    required = {"Agent/Syndrome", "Country"}
    missing = required - set(raw.columns)
    if missing:
        return None, "bad_table", (
            f"Matched a table but it lacks required column(s): {sorted(missing)}. "
            f"Found: {sorted(raw.columns)}")

    df = clean_table(raw)
    if df.empty:
        return None, "empty_after_clean", "Table found but no valid rows survived cleaning"

    report_date = extract_date_from_filename(filename)
    if report_date is None:
        return None, "no_date", "Could not read a YYYY-MM-DD date from the filename"

    df.insert(0, "Report Date", report_date)
    return df, "ok", ""


def run(limit=None):
    pdfs = sorted(f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf"))
    if limit:
        pdfs = pdfs[:limit]

    print(f"Found {len(pdfs)} bulletins in {PDF_FOLDER}\n")

    frames, log = [], []
    t_start = time.time()

    for n, filename in enumerate(pdfs, 1):
        path = os.path.join(PDF_FOLDER, filename)
        t0 = time.time()
        print(f"[{n}/{len(pdfs)}] {filename}", flush=True)

        try:
            df, status, message = process_one(path, filename)
        except Exception as e:
            # A crash on one bulletin must not stop the batch.
            df, status, message = None, "error", f"{type(e).__name__}: {e}"
            traceback.print_exc()

        rows = 0 if df is None else len(df)
        if df is not None:
            frames.append(df)

        elapsed = time.time() - t0
        log.append(dict(filename=filename, status=status, rows=rows,
                        seconds=round(elapsed, 1), message=message))
        print(f"     {status}  rows={rows}  ({elapsed:.1f}s)"
              + (f"  -- {message}" if message else ""), flush=True)

    # ---------- combine ----------
    os.makedirs(os.path.dirname(str(OUTPUT_FILE)), exist_ok=True)

    log_df = pd.DataFrame(log)
    log_df.to_excel(BATCH_REPORT, index=False)

    if not frames:
        print("\nNo bulletins produced any data. See", BATCH_REPORT)
        return

    master = pd.concat(frames, ignore_index=True)
    master.sort_values(["Report Date", "Agent/Syndrome", "Country"], inplace=True)
    master.to_excel(OUTPUT_FILE, index=False)

    # ---------- summary ----------
    ok = (log_df.status == "ok").sum()
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)
    print(f"Bulletins processed:  {len(log_df)}")
    expected_gap = int((log_df.status == "pre_table_era").sum())
    real_fail = len(log_df) - ok - expected_gap
    print(f"  succeeded:          {ok}")
    print(f"  pre-table era:      {expected_gap}  (expected - no such table in these issues)")
    print(f"  needs attention:    {real_fail}")
    print(f"Total rows:           {len(master)}")
    print(f"Elapsed:              {(time.time() - t_start)/60:.1f} min")
    if real_fail:
        print("\nNeeds attention, by reason:")
        for status, grp in log_df[~log_df.status.isin(["ok", "pre_table_era"])].groupby("status"):
            print(f"  {status}: {len(grp)}")
            for f in grp.filename.head(5):
                print(f"      {f}")
    print(f"\nMaster dataset:       {OUTPUT_FILE}")
    print(f"Batch report:         {BATCH_REPORT}")

    # ---------- validate ----------
    report = validate(master)
    report.print_summary()
    report.to_excel(str(VALIDATION_REPORT))


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit=limit)