"""Page images for the review viewer, rendered once and stored instead of on every view."""
from typing import Iterator, Tuple

import pymupdf

# Resolution of the viewer's page images (bounding boxes are page fractions, so any DPI lines up)
PAGE_RENDER_DPI = 150


def render_pdf_page(pdf: pymupdf.Document, page_number: int) -> bytes:
    """PNG of one 1-based page."""
    zoom = PAGE_RENDER_DPI / 72.0
    return pdf[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")


def render_pdf_pages(file_bytes: bytes) -> Iterator[Tuple[int, bytes]]:
    """(page number, PNG) for every page of a PDF."""
    with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
        for number in range(1, pdf.page_count + 1):
            yield number, render_pdf_page(pdf, number)
