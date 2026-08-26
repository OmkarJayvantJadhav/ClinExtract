import pytest
import io

def get_auth_kwargs(client, username, password):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password}
    )
    if login_response.status_code != 200:
        return None
    return {
        "cookies": {
            "access_token": login_response.cookies.get("access_token"),
            "clinextract_csrf": login_response.cookies.get("clinextract_csrf")
        },
        "headers": {
            "X-CSRF-Token": login_response.cookies.get("clinextract_csrf")
        }
    }

pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
bad_content = b"This is just a text file, not a PDF."
large_content = b"0" * (11 * 1024 * 1024)

@pytest.mark.asyncio
async def test_upload_document_success(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    
    files = {"file": ("test_doc.pdf", pdf_content, "application/pdf")}

    response = client.post(
        "/api/v1/documents",
        files=files,
        **kwargs
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test_doc.pdf"
    assert data["status"] == "UPLOADED"
    assert "id" in data

@pytest.mark.asyncio
async def test_upload_path_security(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    files = {"file": ("../../malicious.pdf", pdf_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "malicious.pdf"

@pytest.mark.asyncio
async def test_upload_large_file(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    files = {"file": ("large.pdf", large_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 413

@pytest.mark.asyncio
async def test_upload_fake_pdf(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    files = {"file": ("fake.pdf", bad_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 415

@pytest.mark.asyncio
async def test_upload_unsupported_type(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    # Using real TIFF bytes to see if it's rejected as requested
    tiff_content = b"II*\x00\x08\x00\x00\x00"
    files = {"file": ("image.tiff", tiff_content, "image/tiff")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 415

@pytest.mark.asyncio
async def test_upload_unauthenticated(client):
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_upload_reviewer_rejected(client):
    kwargs = get_auth_kwargs(client, "reviewer", "devpass_reviewer")
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_upload_viewer_rejected(client):
    kwargs = get_auth_kwargs(client, "viewer", "devpass_viewer")
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_upload_operator_accepted(client):
    kwargs = get_auth_kwargs(client, "operator", "devpass_operator")
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 201

