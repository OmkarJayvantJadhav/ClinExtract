"""Page images for the review viewer, rendered once and stored instead of on every view."""
from typing import Iterator, Tuple

import pymupdf

from src.processing import scanned_image

# Resolution of the viewer's page images (bounding boxes are page fractions, so any DPI lines up)
PAGE_RENDER_DPI = 150


def capped_zoom(rect: pymupdf.Rect, dpi: float) -> float:
    """
    Zoom to render `rect` (PDF points) at `dpi`, lowered when needed so the image stays within
    the pixel limit for images: a tiny PDF can declare a page several meters wide.
    """
    zoom = dpi / 72.0
    area = rect.width * rect.height
    limit = scanned_image.MAX_IMAGE_PIXELS
    if area > 0 and area * zoom * zoom > limit:
        zoom = 0.99 * (limit / area) ** 0.5  # rendering rounds the size up a pixel
    return zoom


def render_pdf_page(pdf: pymupdf.Document, page_number: int) -> bytes:
    """PNG of one 1-based page."""
    page = pdf[page_number - 1]
    zoom = capped_zoom(page.rect, PAGE_RENDER_DPI)
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")


def render_pdf_pages(file_bytes: bytes) -> Iterator[Tuple[int, bytes]]:
    """(page number, PNG) for every page of a PDF."""
    with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
        for number in range(1, pdf.page_count + 1):
            yield number, render_pdf_page(pdf, number)
