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

_PDF = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"

def unique_pdf() -> bytes:
    """A minimal PDF with unique bytes, so duplicate-upload detection doesn't refuse it."""
    import uuid
    return _PDF + f"% {uuid.uuid4()}\n".encode()
bad_content = b"This is just a text file, not a PDF."
large_content = b"0" * (11 * 1024 * 1024)

@pytest.mark.asyncio
async def test_upload_document_success(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    
    files = {"file": ("test_doc.pdf", unique_pdf(), "application/pdf")}

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
    files = {"file": ("../../malicious.pdf", unique_pdf(), "application/pdf")}
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
    files = {"file": ("test.pdf", unique_pdf(), "application/pdf")}
    response = client.post("/api/v1/documents", files=files)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_upload_reviewer_rejected(client):
    kwargs = get_auth_kwargs(client, "reviewer", "devpass_reviewer")
    files = {"file": ("test.pdf", unique_pdf(), "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_upload_viewer_rejected(client):
    kwargs = get_auth_kwargs(client, "viewer", "devpass_viewer")
    files = {"file": ("test.pdf", unique_pdf(), "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_upload_operator_accepted(client):
    kwargs = get_auth_kwargs(client, "operator", "devpass_operator")
    files = {"file": ("test.pdf", unique_pdf(), "application/pdf")}
    response = client.post("/api/v1/documents", files=files, **kwargs)
    assert response.status_code == 201



# --- duplicate detection and export ------------------------------------------------

def test_duplicate_upload_is_refused_unless_allowed(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    pdf = unique_pdf()
    first = client.post("/api/v1/documents", files={"file": ("a.pdf", pdf, "application/pdf")}, **kwargs)
    assert first.status_code == 201
    again = client.post("/api/v1/documents", files={"file": ("b.pdf", pdf, "application/pdf")}, **kwargs)
    assert again.status_code == 409
    detail = again.json()["detail"]
    assert detail["code"] == "DUPLICATE_DOCUMENT" and detail["existing_document_id"] == first.json()["id"]
    forced = client.post("/api/v1/documents", params={"allow_duplicate": "true"},
                         files={"file": ("c.pdf", pdf, "application/pdf")}, **kwargs)
    assert forced.status_code == 201


def _lab_pdf(lines):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text(pymupdf.Point(50, 50 + 18 * i), line, fontsize=11)
    return doc.write()


def test_export_csv_and_json(client):
    import csv, io, json, uuid
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    tag = uuid.uuid4().hex[:8]
    pdf = _lab_pdf(["Patient Name: Export Test", f"Patient ID: X-{tag}", "DOB: 1985-03-14", "Specimen Type: Blood",
                    "Collection Date: 2026-01-02", "Received Date: 2026-01-03", "Glucose: 5.5 mmol/L 3.9 - 5.6",
                    "Hemoglobin: 14.5 g/dL", "Hematocrit: 42 %", "WBC: 7.5 K/uL", "Platelets: 250 K/uL"])
    doc_id = client.post("/api/v1/documents", files={"file": (f"exp_{tag}.pdf", pdf, "application/pdf")}, **kwargs).json()["id"]
    assert client.get(f"/api/v1/documents/{doc_id}", **kwargs).json()["status"] == "AUTO_ACCEPTED"

    r = client.get("/api/v1/documents/export", params={"q": f"exp_{tag}"}, **kwargs)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1
    row = rows[0]
    assert row["document_id"] == doc_id and row["patient_id"] == f"X-{tag}"
    # Results are normalized to canonical units, with the printed range kept
    assert (row["glucose"], row["glucose_unit"], row["glucose_reference_range"]) == ("99.088", "mg/dL", "3.9 - 5.6")

    data = client.get("/api/v1/documents/export", params={"q": f"exp_{tag}", "format": "json"}, **kwargs).json()
    assert data[0]["fields"]["glucose"]["printed_value"] == "5.5"
    assert data[0]["fields"]["glucose"]["printed_unit"] == "mmol/L"
    assert data[0]["fields"]["glucose"]["flag"] is None  # 5.5 is within 3.9 - 5.6

    # Exports are audited; viewers and reviewers cannot export
    actions = [i["action"] for i in client.get("/api/v1/audit", params={"size": 20}, **kwargs).json()["items"]]
    assert "DOCUMENTS_EXPORTED" in actions
    viewer = get_auth_kwargs(client, "viewer", "devpass_viewer")
    assert client.get("/api/v1/documents/export", **viewer).status_code == 403


def test_export_cells_cannot_inject_formulas():
    from src.api.routes.documents import _csv_cell
    assert _csv_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert _csv_cell("-12.5") == "-12.5"
    assert _csv_cell("Jane") == "Jane"


def test_export_flag_follows_the_final_value():
    from types import SimpleNamespace
    from src.api.routes.documents import _final_flag
    # The report printed L next to a misread 1.48; the reviewer corrected it to 14.8
    corrected = SimpleNamespace(validation_metadata={"printed_direction": None, "printed_range": "13.5 - 17.5"}, abnormal_flag="L")
    assert _final_flag(corrected) is None
    high = SimpleNamespace(validation_metadata={"value": 182.0, "lower": 70.0, "upper": 100.0})
    assert _final_flag(high) == "H"
    assert _final_flag(SimpleNamespace(validation_metadata=None)) is None
