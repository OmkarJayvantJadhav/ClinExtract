"""Retention, export completeness and flags, duplicate uploads and deletion reasons."""
import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from src.api.routes import documents as documents_routes
from src.db.models.document import Document, DocumentStatus
from src.db.models.extracted_field import ExtractedField
from src.main import app
from src.services import retention


@pytest.fixture
def admin():
    c = TestClient(app)
    assert c.post("/api/v1/auth/login", json={"username": "admin", "password": "devpass_admin"}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies["clinextract_csrf"]
    return c


class _NoFiles:
    async def delete_document_files(self, key):
        pass


async def test_retention_purges_every_expired_document(db_session, user, monkeypatch):
    monkeypatch.setattr(retention, "PURGE_BATCH", 2)
    old = datetime.now(timezone.utc) - timedelta(days=400)
    tag = uuid.uuid4().hex[:8]
    for i in range(5):
        doc = Document(uploader_id=user.id, filename=f"ret_{tag}_{i}.pdf", storage_key=str(uuid.uuid4()),
                       status=DocumentStatus.AUTO_ACCEPTED)
        db_session.add(doc)
        await db_session.flush()
        doc.created_at = old
    await db_session.commit()

    await retention.purge_expired_documents(db_session, _NoFiles(), retention_days=365)
    left = await db_session.scalar(select(func.count()).select_from(Document).where(Document.filename.like(f"ret_{tag}_%")))
    assert left == 0  # all five, though a batch is two


async def test_retention_skips_a_document_another_request_holds(db_session, user):
    from src.core.database import async_session_maker
    doc = Document(uploader_id=user.id, filename="held.pdf", storage_key=str(uuid.uuid4()), status=DocumentStatus.FAILED)
    db_session.add(doc)
    await db_session.flush()
    doc.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    await db_session.commit()
    doc_id = doc.id

    async with async_session_maker() as other:  # e.g. "Retry processing" holding the row
        await other.execute(select(Document).where(Document.id == doc_id).with_for_update())
        async with async_session_maker() as purger:
            # Waiting for the held row would be the bug (and would hang this test): fail instead
            await purger.execute(text("SET lock_timeout = '3s'"))
            await retention.purge_expired_documents(purger, _NoFiles(), retention_days=365)
        await other.rollback()
    assert await db_session.scalar(select(func.count()).select_from(Document).where(Document.id == doc_id)) == 1


def test_export_refuses_instead_of_cutting_documents_off(admin, monkeypatch):
    monkeypatch.setattr(documents_routes, "EXPORT_LIMIT", 0)
    r = admin.get("/api/v1/documents/export", params={"status": ["UPLOADED", "AUTO_ACCEPTED", "REVIEW_REQUIRED", "FAILED"]})
    assert r.status_code == 422 and "limited to 0" in r.json()["detail"]


def test_confirmed_implausible_value_keeps_its_flag():
    field = ExtractedField(field_name="glucose", validation_state="EXTREME_VALUE",
                           validation_metadata={"value": 2500.0, "plausible_lower": 10.0, "plausible_upper": 2000.0})
    assert documents_routes._final_flag(field) == "H"


async def test_identical_files_uploaded_at_once_are_stored_once():
    pdf = pymupdf.open()
    pdf.new_page().insert_text((50, 50), f"Patient Name: Twin {uuid.uuid4().hex}", fontsize=12)
    data = pdf.write()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/api/v1/auth/login", json={"username": "admin", "password": "devpass_admin"})).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies["clinextract_csrf"]
        responses = await asyncio.gather(*[
            c.post("/api/v1/documents", files={"file": (f"twin_{i}.pdf", io.BytesIO(data), "application/pdf")})
            for i in range(4)
        ])
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]


def test_blank_deletion_reason_is_refused(admin):
    r = admin.delete(f"/api/v1/documents/{uuid.uuid4()}", params={"reason": "    "})
    assert r.status_code == 422
