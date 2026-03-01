"""
services/ocr_service.py
========================
Dual-pass OCR using azure-ai-formrecognizer (DocumentAnalysisClient).

  Pass 1 — prebuilt-read   → clean page-wise text
  Pass 2 — prebuilt-layout → structured tables per page
"""
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from core.config import (
    DOC_INTEL_ENDPOINT,
    DOC_INTEL_KEY,
    INPUT_PDF_FOLDER,
    OUTPUT_TXT_FILE,
    ENABLE_FOOTER_FILTER,
    ENABLE_DIGIT_NORMALIZE,
)

FOOTER_PATTERNS = [
    r"[A-Za-z]:\\.*Desktop.*",
    r"C:\\.*\.doc",
    r"Page\s+\\\s*\d+",
]

GUJARATI_DIGITS   = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _make_client() -> DocumentAnalysisClient:
    if not DOC_INTEL_ENDPOINT or not DOC_INTEL_KEY:
        raise EnvironmentError("DOC_INTEL_ENDPOINT and DOC_INTEL_KEY must be set.")
    return DocumentAnalysisClient(
        endpoint=DOC_INTEL_ENDPOINT,
        credential=AzureKeyCredential(DOC_INTEL_KEY),
    )


def _clean_lines(lines: List[str]) -> List[str]:
    if not ENABLE_FOOTER_FILTER:
        return lines
    return [ln for ln in lines
            if not any(re.search(p, ln, re.IGNORECASE) for p in FOOTER_PATTERNS)]


def _normalize_digits(text: str) -> str:
    if not ENABLE_DIGIT_NORMALIZE:
        return text
    return text.translate(GUJARATI_DIGITS).translate(DEVANAGARI_DIGITS)


def extract_text_per_page(
    pdf_path: Path,
    client: DocumentAnalysisClient,
) -> List[Tuple[int, str]]:
    pages_output: List[Tuple[int, str]] = []
    try:
        with pdf_path.open("rb") as f:
            poller = client.begin_analyze_document("prebuilt-read", f)
            result = poller.result()
    except HttpResponseError as e:
        print(f"[ERROR] Read failed for '{pdf_path.name}': HTTP {e.status_code} — {e.message}")
        return pages_output
    except Exception as e:
        print(f"[ERROR] Read failed for '{pdf_path.name}': {type(e).__name__} — {e}")
        return pages_output

    for idx, page in enumerate(result.pages or []):
        lines = _clean_lines([(ln.content or "").rstrip()
                               for ln in (page.lines or [])])
        text  = _normalize_digits("\n".join(lines).strip())
        pages_output.append((idx + 1, text))
    return pages_output


def get_tables_by_page(
    pdf_path: Path,
    client: DocumentAnalysisClient,
) -> Dict[int, List[List[List[str]]]]:
    by_page: Dict[int, List[List[List[str]]]] = {}
    try:
        with pdf_path.open("rb") as f:
            poller = client.begin_analyze_document("prebuilt-layout", f)
            layout = poller.result()
    except HttpResponseError as e:
        print(f"[WARN] Layout failed for '{pdf_path.name}': HTTP {e.status_code} — {e.message}")
        return by_page
    except Exception as e:
        print(f"[WARN] Layout failed for '{pdf_path.name}': {type(e).__name__} — {e}")
        return by_page

    for table in (layout.tables or []):
        page_candidates = []
        for br in (getattr(table, "bounding_regions", None) or []):
            if getattr(br, "page_number", None):
                page_candidates.append(br.page_number)
        if not page_candidates:
            for c in (getattr(table, "cells", None) or []):
                for br in (getattr(c, "bounding_regions", None) or []):
                    if getattr(br, "page_number", None):
                        page_candidates.append(br.page_number)
        page_no = min(page_candidates) if page_candidates else -1

        cells = getattr(table, "cells", None)
        if not cells:
            continue

        rmax = max(c.row_index    for c in cells) + 1
        cmax = max(c.column_index for c in cells) + 1
        grid: List[List[str]] = [[""] * cmax for _ in range(rmax)]
        for c in cells:
            grid[c.row_index][c.column_index] = _normalize_digits(c.content or "")
        by_page.setdefault(page_no, []).append(grid)

    return by_page


def format_table_as_text(grid: List[List[str]]) -> str:
    if not grid:
        return ""
    cols   = max(len(row) for row in grid)
    widths = [0] * cols
    for row in grid:
        for j, cell in enumerate(row):
            widths[j] = max(widths[j], len(cell))
    lines = []
    for i, row in enumerate(grid):
        lines.append(" | ".join(cell.ljust(widths[j]) for j, cell in enumerate(row)))
        if i == 0:
            lines.append("-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def process_all_pdfs() -> None:
    client    = _make_client()
    input_dir = Path(INPUT_PDF_FOLDER)
    out_txt   = Path(OUTPUT_TXT_FILE)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        print(f"\nERROR: Folder not found: {input_dir.resolve()}")
        print("Run from project ROOT:  python scripts/ingest_pdfs.py\n")
        sys.exit(1)

    pdf_files = sorted(p for p in input_dir.iterdir()
                       if p.is_file() and p.suffix.lower() == ".pdf")

    if not pdf_files:
        print(f"\nERROR: No PDFs found in {input_dir.resolve()}\n")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF(s) to process.")

    with out_txt.open("w", encoding="utf-8") as out:
        for pdf_path in pdf_files:
            print(f"\nProcessing: {pdf_path.name}")
            pages        = extract_text_per_page(pdf_path, client)
            tables_by_pg = get_tables_by_page(pdf_path, client)

            if not pages:
                print(f"  [WARN] No pages extracted — skipping.")
                continue

            for page_no, page_text in pages:
                out.write(f"Meta Data - [Document Name - {pdf_path.stem}, Page Number - {page_no}]\n")
                out.write(page_text + "\n\n" if page_text else "\n")
                page_tables = tables_by_pg.get(page_no, [])
                if page_tables:
                    out.write(f"-- TABLES ({len(page_tables)}) --\n")
                    for idx, grid in enumerate(page_tables, 1):
                        out.write(f"Table {idx}:\n")
                        out.write(format_table_as_text(grid))
                        out.write("\nEND_TABLE\n\n")
                out.write(f"page_number_ended - {page_no}\n\n")

    print(f"\nOCR complete → {out_txt.resolve()}")
