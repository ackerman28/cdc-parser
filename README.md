# cdc-parser

Extracts structured surveillance data from Africa CDC Event-Based Surveillance
(EBS) weekly bulletin PDFs, for the USAID funding-cuts / population-health study.

## What it does

Each EBS bulletin contains an "Events Highlighted This Week" table with
country-level case and death counts by disease. This tool pulls that table out of
every bulletin and combines them into one dataset.

## Project structure

```
cdc-parser/
  src/
    config.py     # all file paths (edit these for your machine)
    extract.py    # find + pull the table out of one PDF
    clean.py      # repair OCR/column-drift issues, standardize columns
    pipeline.py   # run extract -> clean over every PDF, write the dataset
  tests/          # (added later)
  notebooks/      # scratch / exploration
  data/           # raw PDFs + generated output -- NOT in git, lives locally
    raw_pdfs/
    output/
```

## How to run

From the project root, with the virtual environment active:

```
python -m src.pipeline
```

Output is written to `data/output/africa_cdc_master.xlsx`.

## IMPORTANT: OCR is required first

The raw bulletins downloaded from the Africa CDC website are scanned images with
**no embedded text layer**. Running the pipeline on a raw file produces no data
(it warns "No table detected"). The files must be OCR'd before extraction.
Automating that OCR step is a later stage of this project. Until then, extraction
expects OCR'd inputs.

## Credit

Original extraction + cleaning logic by Camellia Bùi. This repo reorganizes that
work into modules and replaces the Google Drive paths with local paths.
