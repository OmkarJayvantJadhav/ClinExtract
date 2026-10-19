"""Approving a review: unit corrections, warnings raised by corrections, and confirmed page-check warnings."""
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

HEADER = ["Patient Name: Ravi Kumar", "DOB: 1985-05-20", "Sex: Male", "Specimen Type: Blood",
          "Collection Date: 2026-03-02", "Received Date: 2026-03-03"]
RESULTS = ["Hemoglobin: 14.2 g/dL", "Hematocrit: 43 %", "WBC: 7.1 K/uL", "Platelets: 260 K/uL"]


@pytest.fixture
def admin():
    c = TestClient(app)
    assert c.post("/api/v1/auth/login", json={"username": "admin", "password": "devpass_admin"}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies["clinextract_csrf"]
    return c


def _claimed(client, lines):
    """Uploads a one-page report, claims its review and returns (document id, review id, fields by name)."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text(pymupdf.Point(50, 50 + 18 * i), line, fontsize=11)
    name = f"approval_{uuid.uuid4().hex[:8]}.pdf"
    doc_id = client.post("/api/v1/documents", files={"file": (name, io.BytesIO(doc.write()), "application/pdf")}).json()["id"]
    assert client.get(f"/api/v1/documents/{doc_id}").json()["status"] == "REVIEW_REQUIRED"
    review_id = client.post(f"/api/v1/reviews/{doc_id}/claim").json()["id"]
    return doc_id, review_id, _fields(client, doc_id)


def _fields(client, doc_id):
    fields = client.get(f"/api/v1/documents/{doc_id}").json()["extractions"][0]["extracted_fields"]
    return {f["field_name"]: f for f in fields}


def _approve(client, doc_id, review_id, corrections, **extra):
    return client.post(f"/api/v1/reviews/{doc_id}/complete", json={
        "review_id": review_id, "decision": "HUMAN_APPROVED", "corrections": corrections, **extra})


def test_reviewer_can_correct_a_missing_unit(admin):
    doc_id, review_id, fields = _claimed(admin, HEADER + [f"Patient ID: U-{uuid.uuid4().hex[:6]}1", "Glucose: 5.5"] + RESULTS)
    assert fields["glucose"]["validation_state"] == "UNRECOGNIZED_UNIT"

    r = _approve(admin, doc_id, review_id, [{"extracted_field_id": fields["glucose"]["id"], "new_value": "5.5",
                                             "new_unit": "mmol/L", "reason": "Unit printed in the header"}])
    assert r.status_code == 200, r.text
    glucose = _fields(admin, doc_id)["glucose"]
    assert glucose["current_unit"] == "mmol/L" and glucose["unit"] is None
    assert glucose["validation_state"] == "VALID" and float(glucose["normalized_value"]) == pytest.approx(99.09, abs=0.01)
    correction = r.json()["field_corrections"][0]
    assert correction["new_unit"] == "mmol/L"


def test_warnings_raised_by_a_correction_must_be_confirmed(admin):
    # Patient ID missing (must be corrected); the reviewer also mistypes the glucose
    doc_id, review_id, fields = _claimed(admin, HEADER + ["Glucose: 92 mg/dL"] + RESULTS)
    corrections = [
        {"extracted_field_id": fields["patient_id"]["id"], "new_value": "P-4471", "reason": "Read from the label"},
        {"extracted_field_id": fields["glucose"]["id"], "new_value": "9200", "reason": "Typo"},
        {"extracted_field_id": fields["collection_date"]["id"], "new_value": "1980-01-02", "reason": "Typo"},
    ]
    r = _approve(admin, doc_id, review_id, corrections)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "UNCONFIRMED_WARNINGS"
    assert {(f["field_name"], f["state"]) for f in detail["fields"]} == {
        ("glucose", "EXTREME_VALUE"), ("collection_date", "INCONSISTENT_DATES")}

    r = _approve(admin, doc_id, review_id, corrections, confirm_warnings=True)
    assert r.status_code == 200, r.text
    after = _fields(admin, doc_id)
    assert after["glucose"]["validation_state"] == "EXTREME_VALUE"
    assert after["collection_date"]["validation_state"] == "INCONSISTENT_DATES"


def test_confirmed_page_check_warning_stays_on_the_record(admin):
    # A low flag on a high value contradicts the value read
    doc_id, review_id, fields = _claimed(admin, HEADER + [f"Patient ID: F-{uuid.uuid4().hex[:6]}2", "Glucose: 150 L mg/dL"] + RESULTS)
    assert fields["glucose"]["validation_state"] == "FLAG_MISMATCH"

    r = _approve(admin, doc_id, review_id, [])
    assert r.status_code == 200, r.text
    assert _fields(admin, doc_id)["glucose"]["validation_state"] == "FLAG_MISMATCH"
    audit = admin.get("/api/v1/audit", params={"document_id": doc_id}).json()["items"]
    approved = next(e for e in audit if e["action"] == "DOCUMENT_HUMAN_APPROVED")
    assert {"field_name": "glucose", "state": "FLAG_MISMATCH"} in approved["changes"]["after"]["confirmed_warnings"]


def test_a_correction_does_not_re_read_the_dates_it_did_not_touch(admin):
    # 25/05/1985 shows the report prints dates day first, so 03/04/2026 is 3 April
    lines = ["Patient Name: Ravi Kumar", "DOB: 25/05/1985", "Sex: Male", "Specimen Type: Blood",
             "Collection Date: 03/04/2026", "Received Date: 04/04/2026", "Glucose: 92 mg/dL"] + RESULTS
    doc_id, review_id, fields = _claimed(admin, lines)
    assert fields["collection_date"]["normalized_value"] == "2026-04-03"
    r = _approve(admin, doc_id, review_id, [
        {"extracted_field_id": fields["patient_id"]["id"], "new_value": "P-" + uuid.uuid4().hex[:6], "reason": "Label"},
        {"extracted_field_id": fields["date_of_birth"]["id"], "new_value": "1985-05-25", "reason": "ISO format"},
    ])
    assert r.status_code == 200, r.text
    assert _fields(admin, doc_id)["collection_date"]["normalized_value"] == "2026-04-03"


@pytest.mark.parametrize("typed", ["14.2.5", "92abc7", "9" * 400], ids=["two-points", "letters", "overflow"])
def test_a_mistyped_result_must_be_fixed_before_approval(admin, typed):
    doc_id, review_id, fields = _claimed(admin, HEADER + ["Glucose: 92 mg/dL"] + RESULTS)
    r = _approve(admin, doc_id, review_id, [
        {"extracted_field_id": fields["patient_id"]["id"], "new_value": "P-" + uuid.uuid4().hex[:6], "reason": "Label"},
        {"extracted_field_id": fields["glucose"]["id"], "new_value": typed, "reason": "Typo"},
    ], confirm_warnings=True)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "UNRESOLVED_VALIDATION_ISSUES"
    assert [f["field_name"] for f in r.json()["detail"]["fields"]] == ["glucose"]
