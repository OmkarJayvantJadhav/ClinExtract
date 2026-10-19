import pytest
import os
import json
import uuid
from sqlalchemy import select
from src.db.models.document import Document, DocumentStatus
from src.db.models.processing_job import ProcessingJob, JobStatus
from src.worker.tasks import process_document_job
from src.storage import get_storage_service

@pytest.fixture
def fake_pdf_bytes():
    # A simple valid PDF
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(pymupdf.Point(50, 50), "Patient Name: John Doe", fontsize=12)
    return doc.write()

@pytest.fixture
def fake_scanned_png_bytes():
    import cv2
    import numpy as np
    img = np.ones((1000, 1000, 3), dtype=np.uint8) * 255
    cv2.putText(img, "Scanned Document", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    return cv2.imencode('.png', img)[1].tobytes()

@pytest.mark.asyncio
async def test_process_native_pdf(db_session, user, fake_pdf_bytes):
    # Setup Storage
    storage = get_storage_service()
    
    import io
    from fastapi import UploadFile
    from tempfile import SpooledTemporaryFile
    
    # Need to simulate file upload for storage key
    f = SpooledTemporaryFile(max_size=1000000)
    f.write(fake_pdf_bytes)
    f.seek(0)
    upload_file = UploadFile(filename="test.pdf", file=f)
    storage_key, mime, size = await storage.store_document(upload_file)
    
    doc = Document(
        uploader_id=user.id,
        filename="test.pdf",
        storage_key=storage_key,
        doc_type="application/pdf",
        status=DocumentStatus.UPLOADED
    )
    db_session.add(doc)
    await db_session.flush()
    
    job = ProcessingJob(
        document_id=doc.id,
        status=JobStatus.QUEUED
    )
    db_session.add(job)
    await db_session.commit()
    
    # Process
    # Calling the async task directly
    from src.worker.tasks import process_document_async
    await process_document_async(str(job.id))
    
    # Assertions
    await db_session.refresh(job)
    await db_session.refresh(doc)
    
    assert job.status == JobStatus.SUCCEEDED
    assert doc.status in (DocumentStatus.PROCESSING, DocumentStatus.REVIEW_REQUIRED)
    
    # Check artifact
    artifacts_dir = os.path.join(os.path.dirname(storage.backend.base_dir), 'artifacts')
    artifact_path = os.path.join(artifacts_dir, f"{storage_key}_ocr.json")
    
    assert os.path.exists(artifact_path)
    with open(artifact_path, 'r') as f_art:
        data = json.load(f_art)
        
    print("NATIVE PDF DATA:", data)
    assert data.get("schema_version") == "1.0"
    assert data.get("document_id") == str(doc.id)
    assert data.get("processing_job_id") == str(job.id)
    assert len(data.get("pages", [])) == 1
    assert data["pages"][0].get("source_type") == "PDF_NATIVE"
    assert "John Doe" in data["pages"][0].get("text", "")
    
@pytest.mark.asyncio
async def test_process_corrupt_document(db_session, user):
    storage = get_storage_service()
    
    from fastapi import UploadFile
    from tempfile import SpooledTemporaryFile
    from fastapi.exceptions import HTTPException
    f = SpooledTemporaryFile(max_size=100)
    f.write(b"NOT A VALID PDF OR IMAGE")
    f.seek(0)
    upload_file = UploadFile(filename="corrupt.pdf", file=f)
    
    with pytest.raises(HTTPException) as excinfo:
        await storage.store_document(upload_file)
    assert excinfo.value.status_code == 415

@pytest.mark.asyncio
async def test_process_scanned_image(db_session, user, fake_scanned_png_bytes):
    storage = get_storage_service()
    
    from fastapi import UploadFile
    from tempfile import SpooledTemporaryFile
    f = SpooledTemporaryFile(max_size=1000000)
    f.write(fake_scanned_png_bytes)
    f.seek(0)
    upload_file = UploadFile(filename="scanned.png", file=f)
    storage_key, mime, size = await storage.store_document(upload_file)
    
    doc = Document(
        uploader_id=user.id,
        filename="scanned.png",
        storage_key=storage_key,
        doc_type="image/png",
        status=DocumentStatus.UPLOADED
    )
    db_session.add(doc)
    await db_session.flush()
    
    job = ProcessingJob(
        document_id=doc.id,
        status=JobStatus.QUEUED
    )
    db_session.add(job)
    await db_session.commit()
    
    from src.worker.tasks import process_document_async
    await process_document_async(str(job.id))
    
    await db_session.refresh(job)
    await db_session.refresh(doc)
    
    assert job.status == JobStatus.SUCCEEDED
    
    artifacts_dir = os.path.join(os.path.dirname(storage.backend.base_dir), 'artifacts')
    artifact_path = os.path.join(artifacts_dir, f"{storage_key}_ocr.json")
    with open(artifact_path, 'r') as f_art:
        data = json.load(f_art)
        
    assert data["pages"][0]["source_type"] == "OCR"
    assert "Scanned" in data["pages"][0]["text"]


def _mixed_page_pdf() -> bytes:
    """A typed header with the results pasted underneath as a picture (no text layer)."""
    import pymupdf
    results = pymupdf.open()
    results.new_page(width=400, height=150).insert_text((20, 60), "Glucose: 92 mg/dL", fontsize=24)
    picture = results[0].get_pixmap(dpi=200).tobytes("png")

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "City Lab Report - Patient Name: Jane Doe", fontsize=12)
    page.insert_image(pymupdf.Rect(50, 100, 450, 250), stream=picture)
    return doc.write()


def test_mixed_page_reads_text_inside_images():
    from src.processing.analyzer import DocumentAnalyzer
    artifact = DocumentAnalyzer.process(_mixed_page_pdf(), "application/pdf", "doc", "job")
    page = artifact["pages"][0]

    assert page["source_type"] == "MIXED" and page["ocr_used"]
    texts = [w["text"] for w in page["words"]]
    assert "Jane" in texts  # native header kept
    assert "Glucose:" in texts and "92" in texts  # read from the image

    # The OCR'd word sits inside the image area, in page coordinates
    x, y, w, h = next(w["bbox"] for w in page["words"] if w["text"] == "92")
    page_w, page_h = 612, 792
    assert 50 / page_w <= x and x + w <= 450 / page_w
    assert 100 / page_h <= y and y + h <= 250 / page_h


def test_small_images_on_text_pages_are_not_ocrd():
    import pymupdf
    from src.processing.analyzer import DocumentAnalyzer
    logo = pymupdf.open()
    logo.new_page(width=40, height=40).insert_text((5, 25), "LOGO", fontsize=10)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Patient Name: Jane Doe  Glucose: 92 mg/dL", fontsize=12)
    page.insert_image(pymupdf.Rect(500, 20, 540, 60), stream=logo[0].get_pixmap().tobytes("png"))

    page_data = DocumentAnalyzer.process(doc.write(), "application/pdf", "doc", "job")["pages"][0]
    assert page_data["source_type"] == "PDF_NATIVE" and not page_data["ocr_used"]


def test_ocr_timeout_fails_the_document_instead_of_hanging(monkeypatch, fake_scanned_png_bytes):
    import time
    from src.core.config import settings
    from src.processing.analyzer import DocumentAnalyzer, DocumentProcessingError
    monkeypatch.setattr(settings, "OCR_PAGE_TIMEOUT_SECONDS", 0.001)
    start = time.time()
    with pytest.raises(DocumentProcessingError, match="OCR of page 1 took longer than"):
        DocumentAnalyzer.process(fake_scanned_png_bytes, "image/png", "doc", "job")
    assert time.time() - start < 10


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_pdf_page_boxes_and_pasted_results(rotation):
    import pymupdf
    from src.processing.analyzer import DocumentAnalyzer
    pasted = pymupdf.open()
    p = pasted.new_page(width=400, height=200)
    p.insert_text((20, 100), "Hemoglobin 14.5 g/dL", fontsize=24)
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 100), "Patient Name: Jane Doe Glucose 92 mg/dL", fontsize=14)
    page.insert_image(pymupdf.Rect(50, 300, 450, 500), stream=p.get_pixmap(matrix=pymupdf.Matrix(3, 3)).tobytes("png"))
    page.set_rotation(rotation)

    page_data = DocumentAnalyzer.process(doc.write(), "application/pdf", "doc", "job")["pages"][0]
    # The text in the pasted image is read on rotated pages too
    assert page_data["source_type"] == "MIXED"
    assert "Hemoglobin" in [w["text"] for w in page_data["words"]]
    # Boxes are where the word is shown: (50, 85) on the page, turned 90 degrees clockwise
    x, y, w, h = next(w["bbox"] for w in page_data["words"] if w["text"] == "Glucose")
    if rotation == 0:
        assert x < 0.5 and y < 0.2
    elif rotation == 90:
        assert x > 0.8 and y < 0.5 and h > w  # the word now runs down the page
    elif rotation == 180:
        assert x > 0.5 and y > 0.8
    # Values are still read from their label's line, including the pasted results
    from src.extraction.rule_based import RuleBasedExtractor
    fields = {f.field_name: f.value for f in RuleBasedExtractor().extract({"pages": [page_data]}).fields}
    assert fields["glucose"] == "92" and fields["hemoglobin"] == "14.5" and fields["patient_name"] == "Jane Doe"


def _png_header(width, height):
    """A PNG that only declares its size (no pixel data): enough for a size check."""
    import struct
    import zlib
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


@pytest.mark.parametrize("size", [9000, 14000])  # 14000x14000 is past Pillow's own limit
def test_oversized_image_is_refused_before_decoding(size):
    from src.processing.analyzer import DocumentAnalyzer, DocumentProcessingError
    with pytest.raises(DocumentProcessingError, match="too large"):
        DocumentAnalyzer.process(_png_header(size, size), "image/png", "doc", "job")


def test_huge_scanned_pdf_page_is_refused_without_rendering_it():
    import time
    import pymupdf
    from src.processing.analyzer import DocumentAnalyzer, DocumentProcessingError
    doc = pymupdf.open()
    doc.new_page(width=5000, height=5000)  # 69 x 69 inches, no text: would be rendered for OCR
    start = time.time()
    with pytest.raises(DocumentProcessingError, match="too large to read"):
        DocumentAnalyzer.process(doc.write(), "application/pdf", "doc", "job")
    assert time.time() - start < 5


def test_viewer_page_image_stays_within_the_pixel_limit(monkeypatch):
    import io
    import pymupdf
    from PIL import Image
    from src.processing import scanned_image
    from src.processing.page_images import render_pdf_page
    monkeypatch.setattr(scanned_image, "MAX_IMAGE_PIXELS", 1_000_000)
    doc = pymupdf.open()
    doc.new_page(width=2000, height=1000)  # 150 DPI would be 4167 x 2083 pixels
    width, height = Image.open(io.BytesIO(render_pdf_page(doc, 1))).size
    assert width * height <= 1_000_000 and width > height
