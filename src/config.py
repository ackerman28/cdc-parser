"""
config.py — All file paths in one place. Edit these to match your machine.

Camellia hard-coded Google Drive paths throughout the notebook. Centralizing them
here means there is exactly one place to change when the project moves machines or
when someone else runs it.
"""

from pathlib import Path

# Project root = the cdc-parser folder (this file's parent's parent)
ROOT = Path(__file__).resolve().parent.parent

# Where raw bulletin PDFs live (git-ignored, local only)
PDF_FOLDER = ROOT / "data" / "raw_pdfs"

# Where the generated dataset is written (git-ignored, local only)
OUTPUT_FILE = ROOT / "data" / "output" / "africa_cdc_master.xlsx"
