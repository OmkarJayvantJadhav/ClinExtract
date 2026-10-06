import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

STRONG = "Str0ng-Passw0rd!"

def login(username, password):
    """Returns a TestClient holding the session cookies plus the CSRF header."""
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    if r.status_code == 200:
        c.headers["X-CSRF-Token"] = c.cookies["clinextract_csrf"]
    return c, r

@pytest.fixture
def admin():
    c, r = login("admin", "devpass_admin")
    assert r.status_code == 200
    return c

@pytest.fixture
def new_user(admin):
    username = f"user_{uuid.uuid4().hex[:8]}"
    r = admin.post("/api/v1/users", json={"username": username, "role": "VIEWER", "password": STRONG})
    assert r.status_code == 201, r.text
    return r.json()


# --- account lockout ------------------------------------------------------------

def test_account_locks_after_repeated_failures(admin, new_user):
    for _ in range(5):
        _, r = login(new_user["username"], "wrong-password")
        assert r.status_code == 401
    _, r = login(new_user["username"], STRONG)
    assert r.status_code == 429  # locked even with the right password

    listed = {u["id"]: u for u in admin.get("/api/v1/users").json()}
    assert listed[new_user["id"]]["locked_until"] is not None

    assert admin.post(f"/api/v1/users/{new_user['id']}/unlock").status_code == 200
    _, r = login(new_user["username"], STRONG)
    assert r.status_code == 200

def test_unknown_user_gets_generic_error():
    _, r = login("no_such_user_xyz", "whatever")
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect username or password"


# --- password change / session revocation --------------------------------------

def test_change_password_revokes_other_sessions(new_user):
    c1, _ = login(new_user["username"], STRONG)
    c2, _ = login(new_user["username"], STRONG)

    assert c1.post("/api/v1/auth/change-password", json={"current_password": "nope", "new_password": "An0ther-Passw0rd"}).status_code == 400
    assert c1.post("/api/v1/auth/change-password", json={"current_password": STRONG, "new_password": "weak"}).status_code == 422

    r = c1.post("/api/v1/auth/change-password", json={"current_password": STRONG, "new_password": "An0ther-Passw0rd"})
    assert r.status_code == 200
    assert c1.get("/api/v1/auth/me").status_code == 200       # this session got a fresh cookie
    assert c2.get("/api/v1/auth/me").status_code == 401       # other session revoked
    assert login(new_user["username"], "An0ther-Passw0rd")[1].status_code == 200

def test_logout_everywhere(new_user):
    c1, _ = login(new_user["username"], STRONG)
    c2, _ = login(new_user["username"], STRONG)
    assert c1.post("/api/v1/auth/logout-all").status_code == 200
    assert c2.get("/api/v1/auth/me").status_code == 401


# --- user administration --------------------------------------------------------

def test_user_admin_lifecycle(admin, new_user):
    uid = new_user["id"]
    assert admin.post("/api/v1/users", json={"username": new_user["username"], "role": "VIEWER", "password": STRONG}).status_code == 409
    assert admin.post("/api/v1/users", json={"username": "weakling_x", "role": "VIEWER", "password": "short"}).status_code == 422

    session, _ = login(new_user["username"], STRONG)
    r = admin.patch(f"/api/v1/users/{uid}", json={"role": "REVIEWER"})
    assert r.status_code == 200 and r.json()["role"] == "REVIEWER"
    assert session.get("/api/v1/auth/me").status_code == 401  # role change revokes old tokens

    assert admin.patch(f"/api/v1/users/{uid}", json={"is_active": False}).json()["is_active"] is False
    assert login(new_user["username"], STRONG)[1].status_code == 401

    admin.patch(f"/api/v1/users/{uid}", json={"is_active": True})
    assert admin.post(f"/api/v1/users/{uid}/reset-password", json={"new_password": "Res3t-Passw0rd!"}).status_code == 200
    assert login(new_user["username"], "Res3t-Passw0rd!")[1].status_code == 200

def test_admin_cannot_demote_self(admin):
    me = admin.get("/api/v1/auth/me").json()
    assert admin.patch(f"/api/v1/users/{me['id']}", json={"role": "VIEWER"}).status_code == 400
    assert admin.patch(f"/api/v1/users/{me['id']}", json={"is_active": False}).status_code == 400

def test_non_admin_cannot_manage_users(new_user):
    viewer, _ = login(new_user["username"], STRONG)
    assert viewer.post("/api/v1/users", json={"username": "x_y_z", "role": "ADMIN", "password": STRONG}).status_code == 403


# --- settings -------------------------------------------------------------------

def test_threshold_settings(admin, new_user):
    original = admin.get("/api/v1/settings").json()["confidence_thresholds"]
    try:
        r = admin.put("/api/v1/settings/confidence-thresholds", json={"auto_accept": 0.95})
        assert r.status_code == 200 and r.json()["confidence_thresholds"]["auto_accept"] == 0.95
        assert admin.put("/api/v1/settings/confidence-thresholds", json={"low_confidence": 0.99}).status_code == 422
        viewer, _ = login(new_user["username"], STRONG)
        assert viewer.get("/api/v1/settings").status_code == 200
        assert viewer.put("/api/v1/settings/confidence-thresholds", json={"auto_accept": 0.6}).status_code == 403
    finally:
        admin.put("/api/v1/settings/confidence-thresholds", json=original)


# --- documents: search, view audit, deletion ------------------------------------

def _pdf(text):
    import fitz
    doc = fitz.open()
    doc.new_page().insert_text(fitz.Point(50, 50), text, fontsize=12)
    return doc.write()

def test_search_view_logging_and_delete(admin):
    from src.storage import get_storage_service
    base_dir = get_storage_service().backend.base_dir
    files_before = set(os.listdir(base_dir))

    tag = uuid.uuid4().hex[:8]
    pdf = _pdf(f"Patient Name: Zed Quill{tag} DOB: 1990-01-01 Patient ID: Z-{tag} Glucose: 90 mg/dL")
    r = admin.post("/api/v1/documents", files={"file": (f"report_{tag}.pdf", io.BytesIO(pdf), "application/pdf")})
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert len(set(os.listdir(base_dir)) - files_before) == 1

    # Server-side search by filename and by patient ID (from the extraction)
    assert [d["id"] for d in admin.get("/api/v1/documents", params={"q": f"report_{tag}"}).json()["items"]] == [doc_id]
    assert [d["id"] for d in admin.get("/api/v1/documents", params={"q": f"Z-{tag}"}).json()["items"]] == [doc_id]
    assert admin.get("/api/v1/documents", params={"q": "%"}).status_code == 200  # wildcards are escaped
    multi = admin.get("/api/v1/documents", params=[("status", "REVIEW_REQUIRED"), ("status", "AUTO_ACCEPTED")])
    assert multi.status_code == 200

    # Views are audited, repeated views within the throttle window only once
    for _ in range(3):
        assert admin.get(f"/api/v1/documents/{doc_id}").status_code == 200
    actions = [i["action"] for i in admin.get("/api/v1/audit", params={"document_id": doc_id}).json()["items"]]
    assert actions.count("DOCUMENT_VIEWED") == 1

    # Deletion: admin only, reason required, removes data and files, keeps a redacted trail
    detail = admin.get(f"/api/v1/documents/{doc_id}").json()
    assert detail["extractions"]
    assert admin.delete(f"/api/v1/documents/{doc_id}").status_code == 422
    r = admin.delete(f"/api/v1/documents/{doc_id}", params={"reason": "patient request"})
    assert r.status_code == 204
    assert admin.get(f"/api/v1/documents/{doc_id}").status_code == 404

    items = admin.get("/api/v1/audit", params={"document_id": doc_id}).json()["items"]
    by_action = {i["action"]: i for i in items}
    assert by_action["DOCUMENT_DELETED"]["changes"]["after"] == {"reason": "patient request"}
    assert by_action["DOCUMENT_UPLOADED"]["changes"]["after"] == {"redacted": True}
    assert set(os.listdir(base_dir)) - files_before == set()  # stored file removed

def test_non_admin_cannot_delete(new_user, admin):
    viewer, _ = login(new_user["username"], STRONG)
    r = viewer.delete(f"/api/v1/documents/{uuid.uuid4()}", params={"reason": "x-x-x"})
    assert r.status_code == 403
