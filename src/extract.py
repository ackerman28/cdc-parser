"""
extract2.py — Coordinate-based extraction of the "Events Highlighted This Week" table.

WHY THIS REPLACES THE OLD APPROACH
----------------------------------
The old extract.py read the OCR'd page as FLAT TEXT. Tesseract, however, reads a
table in column-blocks: it emits the left-hand columns row by row, then dumps the
Probable/Confirmed/Deaths columns separately at the bottom of the page. Reading
flat text therefore DETACHES the case counts from their rows -- which is why the
numbers came out as garbage ("dBFF8O8FGFG") or vanished entirely.

This module instead uses Tesseract's `image_to_data`, which returns EVERY WORD
WITH ITS X/Y COORDINATES. We then:
  1. locate the "Events Highlighted this week" header and read the column
     x-positions directly off it (so we adapt to each bulletin's layout rather
     than hard-coding positions),
  2. group words into rows by y-position,
  3. assign each word to a column by x-position.

The table structure is recovered from the page geometry, not guessed from spacing.
That is what makes it robust across bulletins.

MULTI-ROW DISEASES
------------------
A disease (e.g. Mpox) spans many countries, and the bulletin prints the disease
name only on its FIRST row, leaving it blank for subsequent countries. We forward
-fill the disease name down those rows, which is why the old output had 8 rows
with a missing country/disease.
"""

import re
import pandas as pd
from pdf2image import convert_from_path
import pytesseract
from pytesseract import Output


DPI = 300
MIN_CONF = 15          # keep low-confidence words: small isolated digits (e.g. "2 (1)") often
                       # score ~25-30. Dropping them silently LOSES REAL DATA, which is
                       # worse than admitting a slightly uncertain read -- the validator
                       # downstream catches anything nonsensical.
ROW_TOLERANCE = 28     # px: words within this vertical distance are the same row

# The columns of the highlighted-events table, in order.
COLUMNS = [
    "Agent/Syndrome", "Country", "Risk:Human", "Risk:Animal",
    "Type", "Suspected", "Probable", "Confirmed", "Deaths",
]


def _page_words(img):
    """All OCR'd words on the page, with coordinates. One row per word."""
    d = pytesseract.image_to_data(img, output_type=Output.DATAFRAME)
    d = d[d.conf > MIN_CONF].dropna(subset=["text"])
    d["text"] = d["text"].astype(str).str.strip()
    d = d[d["text"] != ""]
    return d


def _find_table_header(words):
    """Locate the header of the *highlighted events* table.

    The page can contain two tables ("New events since last issue" first, then
    "Events Highlighted this week"). We anchor on the 'Highlighted' title and take
    the first header row BELOW it, so we never pick up the wrong table.
    """
    # We want the "Events Highlighted this week" table specifically.
    #
    # A page may also carry a "New events since last issue" table with the SAME
    # column headers. If we anchored on the wrong one we would silently harvest
    # 2-3 rows of new events instead of the ~25 highlighted events. So we anchor
    # on the word "Highlighted" and only accept header rows BELOW it.
    #
    # Note: some bulletins (seen in 2024) genuinely contain only the "New events"
    # table and no highlighted table at all. For those we correctly return None.
    hl = words[words["text"].str.contains("Highlighted", case=False, na=False)]
    if hl.empty:
        return None, None
    title_y = hl["top"].min()

    # Header words for the real table sit just under the title.
    # Header wording varies between bulletin years:
    #   2025 layout -> Tesseract reads "Risk:Human" / "Risk:Animal" as single words
    #   2026 layout -> it reads only a bare "Risk" (the ":Human" wraps to another line)
    # We therefore accept a bare "Risk" too, and disambiguate the two Risk columns
    # by their x-position below (leftmost = Human, next = Animal).
    hdr = words[
        (words["top"] > title_y)
        & (words["text"].str.fullmatch(
            r"Agent/Syndrome|Country|Risk:?Human|Risk:?Animal|Risk|Type|"
            r"Suspected|Probable|Confirmed|Deaths",
            case=False, na=False))
    ]
    if hdr.empty:
        return None, None

    # The header spans a couple of text lines ("Suspected" over "(New)"), so take
    # everything within ~60px of the topmost header word.
    hdr_top = hdr["top"].min()
    hdr = hdr[hdr["top"] < hdr_top + 60]

    # Column x-position = left edge of each header word, in reading order.
    bounds = {}

    # Handle the bare-"Risk" layout: the two Risk headers are distinguished only
    # by position. Leftmost -> Risk:Human, the one after it -> Risk:Animal.
    bare = sorted(
        hdr.loc[hdr["text"].str.fullmatch(r"Risk", case=False, na=False), "left"].tolist()
    )
    if bare:
        bounds["Risk:Human"] = bare[0]
        if len(bare) > 1:
            bounds["Risk:Animal"] = bare[1]

    for _, r in hdr.iterrows():
        name = r["text"].strip()
        if re.fullmatch(r"Risk", name, flags=re.I):
            continue                      # already handled above
        # normalize "RiskHuman"/"Risk:Human" -> "Risk:Human"
        m = re.fullmatch(r"Risk:?(Human|Animal)", name, flags=re.I)
        if m:
            name = "Risk:" + m.group(1).capitalize()
        # keep the leftmost occurrence of each header name
        if name not in bounds or r["left"] < bounds[name]:
            bounds[name] = r["left"]

    header_bottom = hdr["top"].max() + 40
    return bounds, header_bottom


def _column_edges(bounds):
    """Turn header x-positions into [start, end) ranges for each column."""
    # Normalize header names to our COLUMNS order
    order = []
    for c in COLUMNS:
        # header may say "Risk:Human" etc.
        for k in bounds:
            if k.lower().replace(" ", "") == c.lower().replace(" ", ""):
                order.append((c, bounds[k]))
                break
    order.sort(key=lambda t: t[1])

    edges = []
    for i, (name, x) in enumerate(order):
        # A column's LEFT boundary is the midpoint between its own header and the
        # previous header; its RIGHT boundary is the midpoint to the next header.
        # Using midpoints (rather than a fixed pixel margin) means the boundaries
        # adapt automatically when a bulletin's column layout shifts -- which it
        # does between report years. A fixed margin caused the risk level to be
        # absorbed into the Country cell ("Angola High") on the 2026 layout.
        if i == 0:
            start = 0
        else:
            start = (order[i - 1][1] + x) // 2

        if i + 1 < len(order):
            end = (x + order[i + 1][1]) // 2
        else:
            end = 10 ** 6

        edges.append((name, start, end))
    return edges


def _assign(words, edges, header_bottom):
    """Group words into rows (by y) and columns (by x). Returns a DataFrame."""
    body = words[words["top"] > header_bottom].copy()
    if body.empty:
        return pd.DataFrame(columns=[e[0] for e in edges])

    # --- group into rows by vertical position ---
    body = body.sort_values("top")
    rows, current, last_top = [], [], None
    for _, w in body.iterrows():
        if last_top is None or abs(w["top"] - last_top) <= ROW_TOLERANCE:
            current.append(w)
            last_top = w["top"] if last_top is None else last_top
        else:
            rows.append(current)
            current = [w]
            last_top = w["top"]
    if current:
        rows.append(current)

    # --- assign each word in a row to a column by x ---
    out = []
    for row in rows:
        cells = {name: [] for name, _, _ in edges}
        for w in row:
            x = w["left"]
            for name, start, end in edges:
                if start <= x < end:
                    cells[name].append((x, w["text"]))
                    break
        record = {}
        for name in cells:
            parts = [t for _, t in sorted(cells[name])]
            record[name] = " ".join(parts).strip()
        # skip rows that are entirely empty or are page furniture
        if any(record.values()):
            out.append(record)

    return pd.DataFrame(out)


def extract_highlighted_table(pdf_path):
    """Extract the highlighted-events table from a bulletin PDF.

    Works directly on the RAW scanned PDF -- no separate OCR'd file needed,
    because we OCR the page images here.
    """
    # The table is on the 'Event Summary' page; scan the first several pages.
    pages = convert_from_path(pdf_path, dpi=DPI, first_page=1, last_page=4)

    for img in pages:
        words = _page_words(img)
        if words.empty:
            continue
        bounds, header_bottom = _find_table_header(words)
        if not bounds:
            continue

        edges = _column_edges(bounds)
        if len(edges) < 5:      # not a real table
            continue

        df = _assign(words, edges, header_bottom)
        if len(df) >= 3:        # a real table has several rows
            return df

    return None


def extract_date_from_filename(filename):
    """Pull the report date (YYYY-MM-DD) out of the bulletin filename.

    Handles both naming styles seen in the archive:
        EBS_Weekly_Report_2025-07-15.pdf
        EBS Weekly Report 2026-02-04.pdf
    """
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else None