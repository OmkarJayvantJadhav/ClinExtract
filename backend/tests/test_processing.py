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
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 50), "Patient Name: John Doe", fontsize=12)
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
