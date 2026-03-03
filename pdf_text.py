# """
# ===========================================================
# Combined PDF OCR to TXT using Azure Document Intelligence
# ===========================================================

# This script:
# 1. Reads all PDFs from input folder
# 2. Sends PDFs to Azure Document Intelligence
# 3. Extracts text page-wise
# 4. Adds metadata per page
# 5. Creates one combined TXT output

# Output format:

# Meta Data - [Document Name - XYZ, Page Number - 1]
# <text>
# page_number_ended - 1

# ===========================================================
# """

# # ===============================
# # Imports
# # ===============================
# import os
# from azure.ai.documentintelligence import DocumentIntelligenceClient
# from azure.core.credentials import AzureKeyCredential


# # ===============================
# # CONFIGURATION SECTION
# # ===============================
# # Update these values
# DOC_INTEL_ENDPOINT = "https://ire.com/"
# DOC_INTEL_KEY = "5V0dLACOGgGBo"

# INPUT_FOLDER = "input_pdfs"          # Folder containing PDFs
# OUTPUT_FILE = "/home/eytech/ai_mh/AI_Gujrat_Chatbot_POC/output_combined_txt/combined_output.txt"  # Output file


# # ===============================
# # Azure Client Initialization
# # ===============================
# client = DocumentIntelligenceClient(
#     endpoint=DOC_INTEL_ENDPOINT,
#     credential=AzureKeyCredential(DOC_INTEL_KEY)
# )


# # ===============================
# # OCR Extraction Function
# # ===============================
# def extract_text_per_page(pdf_path):
#     """
#     Extract page-wise text from PDF using Azure OCR.
    
#     Returns:
#         List of tuples -> [(page_no, text), ...]
#     """

#     with open(pdf_path, "rb") as f:
#         poller = client.begin_analyze_document(
#             "prebuilt-read",
#             body=f
#         )

#     result = poller.result()

#     pages_output = []

#     # Iterate pages
#     for page_index, page in enumerate(result.pages):
#         lines = []

#         if page.lines:
#             for line in page.lines:
#                 lines.append(line.content)

#         page_text = "\n".join(lines)

#         pages_output.append((page_index + 1, page_text))

#     return pages_output


# # ===============================
# # Main Processing Function
# # ===============================
# def process_all_pdfs():
#     """
#     Processes all PDFs and generates combined TXT.
#     """

#     os.makedirs(os.path.dirname(OUTPUT_FILE) or ".", exist_ok=True)

#     with open(OUTPUT_FILE, "w", encoding="utf-8") as output:

#         for file in os.listdir(INPUT_FOLDER):

#             if not file.lower().endswith(".pdf"):
#                 continue

#             pdf_path = os.path.join(INPUT_FOLDER, file)
#             document_name = os.path.splitext(file)[0]

#             print(f"Processing: {file}")

#             pages = extract_text_per_page(pdf_path)

#             for page_number, text in pages:

#                 # Metadata header
#                 output.write(
#                     f"Meta Data - "
#                     f"[Document Name - {document_name}, "
#                     f"Page Number - {page_number}]"
#                 )

#                 # Page content
#                 output.write(text)
#                 output.write("\n\n")

#                 # Page end marker
#                 output.write(
#                     f"page_number_ended - {page_number}\n\n"
#                 )

#     print("\nCombined TXT generated successfully!")


# # ===============================
# # Entry Point
# # ===============================
# if __name__ == "__main__":
#     process_all_pdfs()




##############################################################################################
# import os
# import sys
# from pathlib import Path
# from typing import List, Tuple

# from azure.core.credentials import AzureKeyCredential
# from azure.core.exceptions import HttpResponseError
# from azure.ai.documentintelligence import DocumentIntelligenceClient

# # ===============================
# # CONFIGURATION SECTION
# # ===============================
# # Keep these as-is (one-time task)
# DOC_INTEL_ENDPOINT = "htt.com/"
# DOC_INTEL_KEY      = "5V0dOGgGBo"

# INPUT_FOLDER = "input_pdfs"  # Folder containing PDFs
# OUTPUT_FILE = "/home/eytech/ai_mh/AI_Gujrat_Chatbot_POC/output_combined_txt/combined_output.txt"

# # Optional: limit pages per document during testing; None = all
# MAX_PAGES = None

# # ===============================
# # Azure Client Initialization (v4)
# # ===============================
# def make_client() -> DocumentIntelligenceClient:
#     if not DOC_INTEL_ENDPOINT or not DOC_INTEL_KEY:
#         print("ERROR: Missing endpoint/key.", file=sys.stderr)
#         sys.exit(1)
#     return DocumentIntelligenceClient(
#         endpoint=DOC_INTEL_ENDPOINT,
#         credential=AzureKeyCredential(DOC_INTEL_KEY),
#     )

# client = make_client()

# # ===============================
# # OCR Extraction Function
# # ===============================
# def extract_text_per_page(pdf_path: Path) -> List[Tuple[int, str]]:
#     """
#     Extract page-wise text from PDF using Azure DI Read model (v4).

#     Returns:
#         List of tuples -> [(page_no, text), ...]
#     """
#     pages_output: List[Tuple[int, str]] = []

#     try:
#         with pdf_path.open("rb") as f:
#             # v4 signature: model_id, body (IO[bytes]) as positional arg
#             poller = client.begin_analyze_document("prebuilt-read", f)
#             result = poller.result()

#     except HttpResponseError as e:
#         print(f"[ERROR] Azure DI failed for '{pdf_path.name}': {e}", file=sys.stderr)
#         return pages_output
#     except Exception as e:
#         print(f"[ERROR] Unexpected failure for '{pdf_path.name}': {e}", file=sys.stderr)
#         return pages_output

#     for idx, page in enumerate(result.pages or []):
#         if MAX_PAGES is not None and idx >= MAX_PAGES:
#             break

#         lines = []
#         if getattr(page, "lines", None):
#             for line in page.lines:
#                 lines.append((line.content or "").rstrip())

#         page_text = "\n".join(lines).strip()
#         pages_output.append((idx + 1, page_text))

#     return pages_output

# # ===============================
# # Main Processing Function
# # ===============================
# def process_all_pdfs():
#     """
#     Processes all PDFs and generates combined TXT (keeps your exact format).
#     """
#     input_dir = Path(INPUT_FOLDER)
#     if not input_dir.exists():
#         print(f"[ERROR] Input folder not found: {input_dir.resolve()}", file=sys.stderr)
#         sys.exit(1)

#     out_path = Path(OUTPUT_FILE)
#     out_path.parent.mkdir(parents=True, exist_ok=True)

#     # Deterministic file order
#     pdf_files = sorted(
#         (entry.path for entry in os.scandir(input_dir)
#          if entry.is_file() and entry.name.lower().endswith(".pdf")),
#         key=lambda p: os.path.basename(p).lower()
#     )

#     if not pdf_files:
#         print(f"[WARN] No PDF files found in {input_dir.resolve()}.")
#         return

#     with out_path.open("w", encoding="utf-8") as output:
#         for pdf in pdf_files:
#             pdf_path = Path(pdf)
#             document_name = pdf_path.stem

#             print(f"Processing: {pdf_path.name}")

#             pages = extract_text_per_page(pdf_path)
#             if not pages:
#                 print(f"[WARN] No pages extracted for {pdf_path.name} (skipped).", file=sys.stderr)
#                 continue

#             for page_number, text in pages:
#                 # Metadata header
#                 output.write(
#                     f"Meta Data - [Document Name - {document_name}, Page Number - {page_number}]\n"
#                 )

#                 # Page content
#                 if text:
#                     output.write(text)
#                     output.write("\n\n")
#                 else:
#                     output.write("\n")  # keep a blank line for empty pages

#                 # Page end marker
#                 output.write(f"page_number_ended - {page_number}\n\n")

#     print("\nCombined TXT generated successfully!")
#     print(f" -> {out_path.resolve()}")

# # ===============================
# # Entry Point
# # ===============================
# if __name__ == "__main__":
#     process_all_pdfs()

#############################################################################################





"""
===========================================================
Azure Document Intelligence (v4) - Read + Layout (tables inline)
===========================================================

What this script does:
1) Reads all PDFs from INPUT_FOLDER
2) Pass 1 (Read): Extracts page-wise text
3) Pass 2 (Layout): Finds all tables -> maps them to their originating pages
4) Writes ONE combined TXT:
   - For each page:
        Meta Data - [Document Name - <doc>, Page Number - <n>]
        <page text>

        -- TABLES (k) --
        Table 1:
        <aligned grid>
        END_TABLE

        page_number_ended - <n>

No extra libraries beyond azure-ai-documentintelligence.
"""

# -------------------------------
# Imports (stdlib + Azure v4)
# -------------------------------
import os
import sys
import re
import csv  # used only for optional debugging; not writing CSV here
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.documentintelligence import DocumentIntelligenceClient


# ===============================
# CONFIGURATION SECTION
# ===============================




DOC_INTEL_ENDPOINT = "htt.com/"
DOC_INTEL_KEY      = "5V0COGgGBo"

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
    Use Read (prebuilt-read) to get page-wise text.
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
        lines: List[str] = []
        if getattr(page, "lines", None):
            for ln in page.lines:
                # keep each OCR line; strip trailing whitespace only
                lines.append((ln.content or "").rstrip())
        lines = clean_lines(lines)
        text = "\n".join(lines).strip()
        text = normalize_digits(text)
        pages_output.append((idx + 1, text))
    return pages_output


# ===============================
# Layout model: get tables and map them to pages
# ===============================
def get_tables_by_page(pdf_path: Path) -> Dict[int, List[List[List[str]]]]:
    """
    Use Layout (prebuilt-layout) to get tables and assign them to page numbers.
    Returns: { page_no: [grid1, grid2, ...], ... }
            where grid is a 2D list of strings (rows->cols)
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

        # Build a 2D grid from cells
        rmax = max(c.row_index for c in table.cells) + 1
        cmax = max(c.column_index for c in table.cells) + 1
        grid: List[List[str]] = [["" for _ in range(cmax)] for _ in range(rmax)]
        for c in table.cells:
            grid[c.row_index][c.column_index] = normalize_digits(c.content or "")

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

            # 1) Read (text)
            pages = extract_text_per_page(pdf_path)

            # 2) Layout (tables by page)
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
