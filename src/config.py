"""
config.py — All file paths in one place. Edit these to match your machine.
"""

from pathlib import Path

# Project root = the cdc-parser folder (this file's parent's parent)
ROOT = Path(__file__).resolve().parent.parent

# Where raw bulletin PDFs live (git-ignored, local only)
PDF_FOLDER = ROOT / "data" / "raw_pdfs"

# Where OCR'd (searchable) copies are cached, so each file is OCR'd only once
OCR_CACHE = ROOT / "data" / "ocr_cache"

# Where the generated dataset is written (git-ignored, local only)
OUTPUT_FILE = ROOT / "data" / "output" / "africa_cdc_master.xlsx"

# Where the validation report is written
VALIDATION_REPORT = ROOT / "data" / "output" / "validation_report.xlsx"