"""
ocr.py — Add a text layer to a scanned CDC bulletin so it can be parsed.

WHY THIS EXISTS
---------------
The raw bulletins downloaded from the Africa CDC website are scanned images with
NO embedded text layer. pdfplumber (used by extract.py) returns nothing on them.
Until now, someone had to run Adobe Acrobat OCR by hand on every file before the
pipeline could touch it. This module does that step automatically with ocrmypdf
(which wraps the open-source Tesseract engine), removing the last manual step
from the pipeline.

HOW IT FITS IN
--------------
OCR is a PRE-step. It turns a scanned PDF into a searchable PDF; extract.py and
clean.py then run on the searchable PDF completely unchanged. Nothing downstream
had to be rewritten.

    raw scanned PDF  --ocr.py-->  searchable PDF  --extract.py-->  table  --clean.py-->  rows

CACHING (important)
-------------------
OCR is slow (~30-60s per bulletin). We OCR each file ONCE and save the result in
data/ocr_cache/. On later runs, if the cached searchable PDF already exists, we
skip OCR entirely. So the first full run over ~157 bulletins is slow, but every
run after that is fast. Delete the cache folder to force a re-OCR.

REQUIREMENTS
------------
System tools (installed once, outside pip):
  - Tesseract OCR      (the OCR engine)
  - Ghostscript        (ocrmypdf uses it internally)
Python package:
  - ocrmypdf           (pip install ocrmypdf)

On Windows, install Tesseract and Ghostscript from their official installers,
then `pip install ocrmypdf`. See README for the exact links.
"""

import subprocess
from pathlib import Path


def ensure_searchable(pdf_path, cache_dir):
    """Return a path to a searchable (text-layer) version of `pdf_path`.

    If a cached OCR'd copy already exists, return it without re-OCRing.
    Otherwise run OCR, cache the result, and return the new path.

    Parameters
    ----------
    pdf_path : str or Path
        The raw scanned bulletin.
    cache_dir : str or Path
        Folder where OCR'd copies are stored (created if missing).

    Returns
    -------
    Path to a searchable PDF that pdfplumber can read.
    """
    pdf_path = Path(pdf_path)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached = cache_dir / pdf_path.name

    # Already OCR'd -> reuse it, skip the slow step.
    if cached.exists():
        print(f"  [ocr] using cached: {cached.name}")
        return cached

    print(f"  [ocr] running OCR on {pdf_path.name} (this is slow, one time only)...")
    try:
        subprocess.run(
            [
                "ocrmypdf",
                "--force-ocr",          # these PDFs are pure images; force OCR on every page
                "--output-type", "pdf",
                str(pdf_path),
                str(cached),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ocrmypdf is not installed or not on PATH. Install Tesseract + "
            "Ghostscript, then `pip install ocrmypdf`. See README."
        )
    except subprocess.CalledProcessError as e:
        # If OCR fails on one file, don't kill the whole batch -- surface a clear error.
        raise RuntimeError(
            f"OCR failed for {pdf_path.name}.\n"
            f"ocrmypdf said:\n{e.stderr[-800:] if e.stderr else '(no message)'}"
        )

    print(f"  [ocr] done -> {cached.name}")
    return cached


def is_searchable(pdf_path):
    """Quick check: does this PDF already have a usable text layer?

    Lets the pipeline skip OCR for any bulletin that happens to be born-digital.
    """
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:4]:
            if (page.extract_text() or "").strip():
                return True
    return False