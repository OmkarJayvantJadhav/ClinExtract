"""Request bodies are limited before anything reads them, and uploads stay in memory."""
from fastapi.testclient import TestClient

from src.main import MAX_REQUEST_BYTES, app
from src.storage.service import StorageService


def test_oversized_upload_is_refused_before_authentication():
    body = b"x" * (MAX_REQUEST_BYTES + 1)
    r = TestClient(app).post("/api/v1/documents", content=body,
                             headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413  # not 401: the body was never parsed


def test_oversized_streamed_body_is_refused():
    def chunks():
        for _ in range(12):
            yield b"x" * (1024 * 1024)
    r = TestClient(app).post("/api/v1/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_uploads_are_not_spooled_to_disk(monkeypatch):
    seen = {}
    original = StorageService.read_upload

    async def spy(self, upload_file):
        seen["on_disk"] = getattr(upload_file.file, "_rolled", None)
        return await original(self, upload_file)

    monkeypatch.setattr(StorageService, "read_upload", spy)
    client = TestClient(app)
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "devpass_admin"}).status_code == 200
    client.headers["X-CSRF-Token"] = client.cookies["clinextract_csrf"]
    client.post("/api/v1/documents", files={"file": ("big.pdf", b"%PDF-1.7\n" + b"0" * (5 * 1024 * 1024), "application/pdf")})
    assert seen["on_disk"] is False
