"""
===========================================================
Azure Document Intelligence (v4) - Read + Layout + Translate (gu → en)
===========================================================

What this script does:
1) Reads all PDFs from INPUT_FOLDER
2) Pass 1 (Read): Extracts page-wise text
3) Pass 2 (Layout): Finds all tables -> maps them to their originating pages
4) Translates Gujarati text to English while preserving layout:
   - Page text -> translated line-by-line (Gujarati only)
   - Tables -> translated cell-by-cell (Gujarati only)
   - Bilingual mode optional
5) Writes ONE combined TXT:
   - For each page:
        Meta Data - [Document Name - <doc>, Page Number - <n>]
        <page text (translated)>

        -- TABLES (k) --
        Table 1:
        <aligned grid (translated)>
        END_TABLE

        page_number_ended - <n>

No extra libraries beyond azure-ai-documentintelligence and requests.
"""

# -------------------------------
# Imports (stdlib + Azure v4)
# -------------------------------
import os
import sys
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import requests  # used to call Azure Translator

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.documentintelligence import DocumentIntelligenceClient


# ===============================
# CONFIGURATION SECTION
# ===============================

# ---- Azure Document Intelligence (unchanged) ----
DOC_INTEL_ENDPOINT = "https://incdcxse.com/"
DOC_INTEL_KEY      = "5V0d1QK3AAALACOGgGBo"

INPUT_FOLDER = "input_pdfs"
OUTPUT_TXT   = "output_combined_txt/combined_output.txt"

# Optional: None = all pages; or a small int for smoke tests
MAX_PAGES = None

# Mild cleanups (no extra libs)
ENABLE_FOOTER_FILTER   = True
ENABLE_DIGIT_NORMALIZE = True

# Footer/path patterns you want to drop from text lines
FOOTER_PATTERNS = [
    r"[A-Za-z]:\\\\.*Desktop.*",          # Windows-like absolute paths
    r"C:\\\\.*Shruti\.doc",               # recurring noisy footer observed in sample
    r"Page\s+\\\s*\d+",                   # stray "Page \ 1" artifacts
]

# Digit normalization maps
GUJARATI_DIGITS   = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# ---- Azure Translator (use directly in code, one-time task) ----
TRANSLATOR_ENDPOINT = "https://aplator.com/"
TRANSLATOR_KEY      = "DSTJjuFNkUlslBXJ3w3AAAbACOGxwT1"
TRANSLATOR_REGION   = "centralindia"

# Force "from" language; set to "gu" to translate specifically Gujarati -> English.
# If set to "", the API will auto-detect.
FORCE_FROM_LANG = ""

# Bilingual mode: "1" -> keep original + add English; "0" -> English only (for Gujarati lines/cells)
BILINGUAL_MODE = "0"


# ===============================
# Small clean-up helpers
# ===============================
def clean_lines(lines: List[str]) -> List[str]:
    """Remove repeated footers/headers that are not real content."""
    if not ENABLE_FOOTER_FILTER:
        return lines
    cleaned = []
    for ln in lines:
        if any(re.search(pat, ln, flags=re.IGNORECASE) for pat in FOOTER_PATTERNS):
            continue
        cleaned.append(ln)
    return cleaned

def normalize_digits(text: str) -> str:
    """Convert Gujarati/Devanagari numerals to ASCII 0-9 for easier parsing."""
    if not ENABLE_DIGIT_NORMALIZE:
        return text
    return text.translate(GUJARATI_DIGITS).translate(DEVANAGARI_DIGITS)

def is_gujarati(text: str) -> bool:
    """Heuristic: Does the string contain Gujarati script characters? (U+0A80–U+0AFF)"""
    return any("\u0A80" <= ch <= "\u0AFF" for ch in text)


# ===============================
# Azure Translator helpers
# ===============================
def _translate_chunk(texts: List[str], force_from_lang: str = "gu") -> List[str]:
    """
    Translate a small batch of strings to English using Azure Translator.
    Returns translations in the same order. In case of error, returns originals.
    """
    if not texts:
        return []

    url = TRANSLATOR_ENDPOINT.rstrip("/") + "/translate"
    params = {
        "api-version": "3.0",
        "to": "en",
    }
    # Only set 'from' if caller wants to force Gujarati; otherwise let service auto-detect.
    if force_from_lang.strip():
        params["from"] = force_from_lang.strip()

    headers = {
        "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": TRANSLATOR_REGION,
        "Content-Type": "application/json; charset=UTF-8",
    }

    body = [{"text": t if t is not None else ""} for t in texts]

    try:
        resp = requests.post(url, params=params, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        out = []
        for i, item in enumerate(data):
            # per-item: translations is a list; take first
            if isinstance(item, dict) and "translations" in item and item["translations"]:
                out.append(item["translations"][0].get("text", texts[i]))
            else:
                out.append(texts[i])
        return out
    except Exception as e:
        print(f"[WARN] Translator error: {e}. Falling back to original text for this chunk.", file=sys.stderr)
        return texts

def translate_texts_preserve_layout(
    lines: List[str],
    bilingual: bool = False,
    force_from_lang: str = "gu",
    skip_if_not_gujarati: bool = True,
) -> List[str]:
    """
    Translate a list of lines to English while preserving line order and breaks.
    - Only translate lines with Gujarati characters if skip_if_not_gujarati=True.
    - Bilingual mode will append English below the original per line.
    """
    if not lines:
        return []

    # Collect which lines to translate
    idxs = []
    payload = []
    for i, ln in enumerate(lines):
        if ln and (not skip_if_not_gujarati or is_gujarati(ln)):
            idxs.append(i)
            payload.append(ln)

    # Translate in batches keeping API constraints in mind
    translated_map: Dict[int, str] = {}
    if payload:
        # Chunk by count (~100) and combined char size (~45k) to be safe
        start = 0
        while start < len(payload):
            size = 0
            count = 0
            chunk_texts: List[str] = []
            # Build chunk with conservative limits
            while start + count < len(payload) and count < 90 and size < 45000:
                t = payload[start + count]
                # Safety trim per element if extremely long
                t_trim = t[:4500]
                chunk_texts.append(t_trim)
                size += len(t_trim)
                count += 1
            # Translate chunk
            chunk_out = _translate_chunk(chunk_texts, force_from_lang=force_from_lang)
            # Assign back to the corresponding original indices
            for j, out_text in enumerate(chunk_out):
                orig_index = idxs[start + j]
                if bilingual:
                    translated_map[orig_index] = f"{lines[orig_index]}\n[EN] {out_text}"
                else:
                    translated_map[orig_index] = out_text
            start += count

    # Build final lines (translated where needed)
    final_lines = []
    for i, ln in enumerate(lines):
        final_lines.append(translated_map.get(i, ln))
    return final_lines

def translate_cells_preserve_grid(
    grid: List[List[str]],
    bilingual: bool = False,
    force_from_lang: str = "gu",
    skip_if_not_gujarati: bool = True,
) -> List[List[str]]:
    """
    Translate a 2D table grid cell-by-cell, preserving rows/columns.
    Only Gujarati cells are translated if skip_if_not_gujarati=True.
    """
    if not grid:
        return grid

    # Flatten with index mapping
    flat: List[str] = []
    idx_map: List[Tuple[int, int]] = []
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            flat.append(cell or "")
            idx_map.append((r, c))

    # Decide which to translate
    idxs = []
    payload = []
    for i, text in enumerate(flat):
        if text and (not skip_if_not_gujarati or is_gujarati(text)):
            idxs.append(i)
            payload.append(text)

    # Translate in batches
    translated_flat: Dict[int, str] = {}
    if payload:
        start = 0
        while start < len(payload):
            size = 0
            count = 0
            chunk_texts: List[str] = []
            while start + count < len(payload) and count < 90 and size < 45000:
                t = payload[start + count]
                t_trim = t[:4500]
                chunk_texts.append(t_trim)
                size += len(t_trim)
                count += 1
            chunk_out = _translate_chunk(chunk_texts, force_from_lang=force_from_lang)
            for j, out_text in enumerate(chunk_out):
                orig_flat_idx = idxs[start + j]
                if bilingual:
                    translated_flat[orig_flat_idx] = f"{flat[orig_flat_idx]}\n[EN] {out_text}"
                else:
                    translated_flat[orig_flat_idx] = out_text
            start += count

    # Rebuild grid
    out_grid = []
    k = 0
    for r, row in enumerate(grid):
        new_row = []
        for c, cell in enumerate(row):
            if k in translated_flat:
                new_row.append(translated_flat[k])
            else:
                new_row.append(cell or "")
            k += 1
        out_grid.append(new_row)
    return out_grid


# ===============================
# Azure client (v4)
# ===============================
def make_client() -> DocumentIntelligenceClient:
    if not DOC_INTEL_ENDPOINT or not DOC_INTEL_KEY:
        print("ERROR: Missing endpoint/key.", file=sys.stderr)
        sys.exit(1)
    return DocumentIntelligenceClient(
        endpoint=DOC_INTEL_ENDPOINT,
        credential=AzureKeyCredential(DOC_INTEL_KEY),
    )

client = make_client()


# ===============================
# Read model: page-wise text
# ===============================
def extract_text_per_page(pdf_path: Path) -> List[Tuple[int, str]]:
    """
    Use Read (prebuilt-read) to get page-wise text, then translate Gujarati -> English per line.
    Returns: [(page_no, page_text), ...]
    """
    pages_output: List[Tuple[int, str]] = []
    try:
        with pdf_path.open("rb") as f:
            poller = client.begin_analyze_document("prebuilt-read", f)
            result = poller.result()
    except HttpResponseError as e:
        print(f"[ERROR] Read failed for '{pdf_path.name}': {e}", file=sys.stderr)
        return pages_output
    except Exception as e:
        print(f"[ERROR] Unexpected Read failure for '{pdf_path.name}': {e}", file=sys.stderr)
        return pages_output

    for idx, page in enumerate(result.pages or []):
        if MAX_PAGES is not None and idx >= MAX_PAGES:
            break

        # Collect OCR lines
        lines: List[str] = []
        if getattr(page, "lines", None):
            for ln in page.lines:
                # keep each OCR line; strip trailing whitespace only
                lines.append((ln.content or "").rstrip())

        # Clean & normalize
        lines = clean_lines(lines)
        # Normalize digits first; translation targets language, digits are language-agnostic
        lines = [normalize_digits(x) for x in lines]

        # Translate Gujarati lines -> English (preserve layout)
        bilingual = (str(BILINGUAL_MODE).strip() == "1")
        
        translated_lines = translate_texts_preserve_layout(
            lines,
            bilingual=bilingual,
            force_from_lang=str(FORCE_FROM_LANG).strip(),  # now auto-detect
            skip_if_not_gujarati=False,                    # translate EVERY line
    )


        text = "\n".join(translated_lines).strip()
        pages_output.append((idx + 1, text))
    return pages_output


# ===============================
# Layout model: get tables and map them to pages
# ===============================
def get_tables_by_page(pdf_path: Path) -> Dict[int, List[List[List[str]]]]:
    """
    Use Layout (prebuilt-layout) to get tables and assign them to page numbers.
    Also translates Gujarati cell content -> English (preserving grid).
    Returns: { page_no: [grid1, grid2, ...], ... } where grid is a 2D list[str]
    """
    by_page: Dict[int, List[List[List[str]]]] = {}
    try:
        with pdf_path.open("rb") as f:
            poller = client.begin_analyze_document("prebuilt-layout", f)
            layout = poller.result()
    except HttpResponseError as e:
        print(f"[WARN] Layout failed for '{pdf_path.name}': {e}", file=sys.stderr)
        return by_page
    except Exception as e:
        print(f"[WARN] Unexpected Layout failure for '{pdf_path.name}': {e}", file=sys.stderr)
        return by_page

    tables = layout.tables or []
    bilingual = (str(BILINGUAL_MODE).strip() == "1")

    for table in tables:
        # Infer page number: prefer table.bounding_regions, else from its cells
        page_candidates = []
        if getattr(table, "bounding_regions", None):
            for br in table.bounding_regions:
                if getattr(br, "page_number", None):
                    page_candidates.append(br.page_number)
        if not page_candidates and getattr(table, "cells", None):
            for c in table.cells:
                if getattr(c, "bounding_regions", None):
                    for br in c.bounding_regions:
                        if getattr(br, "page_number", None):
                            page_candidates.append(br.page_number)
        page_no = min(page_candidates) if page_candidates else -1  # -1 = unknown page

        if not getattr(table, "cells", None):
            continue

        # Build a 2D grid from cells (normalize digits, preserve text)
        rmax = max(c.row_index for c in table.cells) + 1
        cmax = max(c.column_index for c in table.cells) + 1
        grid: List[List[str]] = [["" for _ in range(cmax)] for _ in range(rmax)]
        for c in table.cells:
            cell_text = c.content or ""
            cell_text = normalize_digits(cell_text)
            grid[c.row_index][c.column_index] = cell_text

        # Translate Gujarati cells -> English (preserve grid)
        grid = translate_cells_preserve_grid(
            grid,
            bilingual=bilingual,
            force_from_lang=str(FORCE_FROM_LANG).strip(),
            skip_if_not_gujarati=False,
        )

        by_page.setdefault(page_no, []).append(grid)

    return by_page


# ===============================
# Render a table grid as plain text (aligned columns)
# ===============================
def format_table_as_text(grid: List[List[str]]) -> str:
    """
    Render a 2D grid into an aligned plain-text table using monospaced columns.
    """
    if not grid:
        return ""
    # Compute column widths
    cols = max(len(row) for row in grid)
    widths = [0] * cols
    for row in grid:
        for j, cell in enumerate(row):
            widths[j] = max(widths[j], len(cell))

    # Build lines
    lines = []
    for i, row in enumerate(grid):
        padded = []
        for j, cell in enumerate(row):
            cell = cell or ""
            padded.append(cell.ljust(widths[j]))
        lines.append(" | ".join(padded))
        if i == 0:
            # header separator heuristic (optional). Comment out if tables have no header.
            sep = ["-" * w for w in widths]
            lines.append("-+-".join(sep))
    return "\n".join(lines)


# ===============================
# Main processing
# ===============================
def process_all_pdfs():
    input_dir = Path(INPUT_FOLDER)
    if not input_dir.exists():
        print(f"[ERROR] Input folder not found: {input_dir.resolve()}", file=sys.stderr)
        sys.exit(1)

    out_txt = Path(OUTPUT_TXT)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    # Ordered list of PDFs
    pdf_files = sorted(
        (entry.path for entry in os.scandir(input_dir)
         if entry.is_file() and entry.name.lower().endswith(".pdf")),
        key=lambda p: os.path.basename(p).lower()
    )

    if not pdf_files:
        print(f"[WARN] No PDF files found in {input_dir.resolve()}.")
        return

    with out_txt.open("w", encoding="utf-8") as out:
        for pdf in pdf_files:
            pdf_path = Path(pdf)
            doc_name = pdf_path.stem
            print(f"Processing: {pdf_path.name}")

            # 1) Read (text) -> with translation integrated
            pages = extract_text_per_page(pdf_path)

            # 2) Layout (tables by page) -> with translation integrated
            tables_by_page = get_tables_by_page(pdf_path)

            if not pages:
                print(f"[WARN] No pages extracted for {pdf_path.name} (skipped).", file=sys.stderr)
                continue

            # Write one block per page
            for page_no, page_text in pages:
                # --- header ---
                out.write(f"Meta Data - [Document Name - {doc_name}, Page Number - {page_no}]\n")

                # --- page text ---
                if page_text:
                    out.write(page_text)
                    out.write("\n\n")
                else:
                    out.write("\n")

                # --- tables for this page (if any) ---
                page_tables = tables_by_page.get(page_no, [])
                if page_tables:
                    out.write(f"-- TABLES ({len(page_tables)}) --\n")
                    for idx, grid in enumerate(page_tables, start=1):
                        out.write(f"Table {idx}:\n")
                        out.write(format_table_as_text(grid))
                        out.write("\nEND_TABLE\n\n")

                # --- page end marker ---
                out.write(f"page_number_ended - {page_no}\n\n")

    print("\nAll done.")
    print(f"Combined TXT -> {out_txt.resolve()}")


# ===============================
# Entry point
# ===============================
if __name__ == "__main__":
    process_all_pdfs()
