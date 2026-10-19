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
    _, locked = login(new_user["username"], STRONG)
    _, unknown = login("no_such_user_xyz", STRONG)
    # Refused even with the right password, and indistinguishable from an unknown username
    assert locked.status_code == unknown.status_code == 401
    assert locked.json() == unknown.json()

    listed = {u["id"]: u for u in admin.get("/api/v1/users").json()}
    assert listed[new_user["id"]]["locked_until"] is not None

    assert admin.post(f"/api/v1/users/{new_user['id']}/unlock").status_code == 200
    _, r = login(new_user["username"], STRONG)
    assert r.status_code == 200

def test_unknown_user_gets_generic_error(admin):
    _, r = login("no_such_user_xyz", "whatever")
    assert r.status_code == 401
    assert r.json()["detail"].startswith("Incorrect username or password")
    events = admin.get("/api/v1/audit", params={"action": "USER_LOGIN_FAILED"}).json()["items"]
    assert any((e["changes"]["after"] or {}).get("username") == "no_such_user_xyz" for e in events)


def test_deactivated_account_does_not_reveal_a_right_password(admin, new_user):
    assert admin.patch(f"/api/v1/users/{new_user['id']}", json={"is_active": False}).status_code == 200
    _, right = login(new_user["username"], STRONG)
    _, wrong = login(new_user["username"], "Wr0ng-Passw0rd!")
    assert right.status_code == wrong.status_code == 401 and right.json() == wrong.json()


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
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text(pymupdf.Point(50, 50), text, fontsize=12)
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


# --- review policy, queue order, reprocessing ------------------------------------

def test_review_policy_settings(admin, new_user):
    original = admin.get("/api/v1/settings").json()["review_policy"]
    assert original == {"review_abnormal_results": False}
    try:
        r = admin.put("/api/v1/settings/review-policy", json={"review_abnormal_results": True})
        assert r.status_code == 200 and r.json()["review_policy"]["review_abnormal_results"] is True
        assert admin.get("/api/v1/settings").json()["review_policy"]["review_abnormal_results"] is True
        viewer, _ = login(new_user["username"], STRONG)
        assert viewer.put("/api/v1/settings/review-policy", json={"review_abnormal_results": False}).status_code == 403
    finally:
        admin.put("/api/v1/settings/review-policy", json=original)

def test_list_documents_oldest_first(admin):
    tag = uuid.uuid4().hex[:8]
    ids = []
    for i in range(3):
        r = admin.post("/api/v1/documents", files={"file": (f"order_{tag}_{i}.pdf", io.BytesIO(_pdf(f"Doc {i}")), "application/pdf")})
        assert r.status_code == 201
        ids.append(r.json()["id"])

    def listed(sort):
        items = admin.get("/api/v1/documents", params={"q": f"order_{tag}", "sort": sort}).json()["items"]
        return [d["id"] for d in items]

    assert listed("oldest") == ids
    assert listed("newest") == ids[::-1]
    assert admin.get("/api/v1/documents", params={"sort": "random"}).status_code == 422

def test_reprocess_failed_document(admin, new_user, monkeypatch):
    import pymupdf
    from src.core.config import settings
    monkeypatch.setattr(settings, "MAX_DOCUMENT_PAGES", 2)
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page().insert_text(pymupdf.Point(50, 50), "Patient Name: Retry Case Glucose: 90 mg/dL", fontsize=12)
    r = admin.post("/api/v1/documents", files={"file": ("too_long.pdf", io.BytesIO(doc.write()), "application/pdf")})
    doc_id = r.json()["id"]
    assert admin.get(f"/api/v1/documents/{doc_id}").json()["status"] == "FAILED"

    # Only admins/operators may retry
    viewer, _ = login(new_user["username"], STRONG)
    assert viewer.post(f"/api/v1/documents/{doc_id}/reprocess").status_code == 403

    # The cause is fixed, so the retry succeeds without a re-upload
    monkeypatch.setattr(settings, "MAX_DOCUMENT_PAGES", 50)
    r = admin.post(f"/api/v1/documents/{doc_id}/reprocess")
    assert r.status_code == 200, r.text
    detail = admin.get(f"/api/v1/documents/{doc_id}").json()
    assert detail["status"] in ("REVIEW_REQUIRED", "AUTO_ACCEPTED")
    assert detail["extractions"]

    # A document that did not fail cannot be reprocessed
    assert admin.post(f"/api/v1/documents/{doc_id}/reprocess").status_code == 409
    assert admin.post(f"/api/v1/documents/{uuid.uuid4()}/reprocess").status_code == 404

    actions = [i["action"] for i in admin.get("/api/v1/audit", params={"document_id": doc_id}).json()["items"]]
    assert "DOCUMENT_REPROCESS_REQUESTED" in actions


# --- public demo accounts -------------------------------------------------------

def test_demo_accounts(admin, monkeypatch):
    from src.core.config import settings
    username = f"demo_{uuid.uuid4().hex[:8]}"
    assert admin.post("/api/v1/users", json={"username": username, "role": "REVIEWER", "password": STRONG}).status_code == 201

    anon = TestClient(app)
    assert anon.get("/api/v1/auth/demo").json() == {"enabled": False, "accounts": []}

    # The admin account is never offered or treated as a demo account
    monkeypatch.setattr(settings, "DEMO_ACCOUNTS", f"{username}, admin")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", STRONG)
    info = anon.get("/api/v1/auth/demo").json()
    assert info == {"enabled": True, "accounts": [{"username": username, "role": "REVIEWER"}], "password": STRONG}

    # Failed logins never lock a shared account
    for _ in range(8):
        assert anon.post("/api/v1/auth/login", json={"username": username, "password": "wrong"}).status_code == 401
    demo, r = login(username, STRONG)
    assert r.status_code == 200

    # A visitor cannot take the account away from everyone else
    r = demo.post("/api/v1/auth/change-password", json={"current_password": STRONG, "new_password": "An0ther-Passw0rd!"})
    assert r.status_code == 403
    assert demo.post("/api/v1/auth/logout-all").status_code == 403
    assert demo.get("/api/v1/auth/me").status_code == 200


# --- review speed: stored page images, priority order, claim keep-alive -----------

def test_page_images_are_stored_served_and_deleted(admin):
    from src.storage import get_storage_service
    storage = get_storage_service()
    tag = uuid.uuid4().hex[:8]
    r = admin.post("/api/v1/documents", files={"file": (f"pages_{tag}.pdf", io.BytesIO(_pdf(f"Patient Name: P {tag}")), "application/pdf")})
    doc_id = r.json()["id"]
    admin.get(f"/api/v1/documents/{doc_id}")  # processed eagerly in tests
    from sqlalchemy import create_engine, text
    from src.core.config import settings
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        storage_key = conn.execute(text("select storage_key from documents where id = :i"), {"i": doc_id}).scalar_one()
    engine.dispose()

    # Rendered during processing, and served as-is
    stored = os.path.join(storage.backend.artifacts_dir, storage.page_image_key(storage_key, 1))
    assert os.path.exists(stored)
    page = admin.get(f"/api/v1/documents/{doc_id}/pages/1/image")
    assert page.status_code == 200 and page.content[:4] == b"\x89PNG"
    assert admin.get(f"/api/v1/documents/{doc_id}/pages").json() == {"page_count": 1}
    assert admin.get(f"/api/v1/documents/{doc_id}/pages/2/image").status_code == 404

    # Removed with the document
    assert admin.delete(f"/api/v1/documents/{doc_id}", params={"reason": "test cleanup"}).status_code == 204
    assert not os.path.exists(stored)


def _report_pdf(lines):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text(pymupdf.Point(50, 50 + 18 * i), line, fontsize=11)
    return doc.write()

def test_priority_sort_puts_possible_misreads_first(admin):
    tag = uuid.uuid4().hex[:8]
    fields = [f"Patient Name: Q{tag}", f"Patient ID: Z-{tag}", "DOB: 1990-01-01", "Specimen Type: Blood",
              "Collection Date: 2026-01-02", "Received Date: 2026-01-03", "Glucose: 92 mg/dL"]
    def upload(name, hemoglobin):
        pdf = _report_pdf(fields + [f"Hemoglobin: {hemoglobin} g/dL"])
        return admin.post("/api/v1/documents", files={"file": (name, io.BytesIO(pdf), "application/pdf")}).json()["id"]
    normal = upload(f"prio_{tag}_a.pdf", "14.5")
    misread = upload(f"prio_{tag}_b.pdf", "1.45")
    items = admin.get("/api/v1/documents", params={"q": f"prio_{tag}", "sort": "priority"}).json()["items"]
    assert [d["id"] for d in items] == [misread, normal]
    assert [d["needs_attention"] for d in items] == [True, False]


def test_review_heartbeat_keeps_the_claim(admin, new_user):
    tag = uuid.uuid4().hex[:8]
    doc_id = admin.post("/api/v1/documents", files={"file": (f"hb_{tag}.pdf", io.BytesIO(_pdf("Patient Name: Missing Fields")), "application/pdf")}).json()["id"]
    assert admin.get(f"/api/v1/documents/{doc_id}").json()["status"] == "REVIEW_REQUIRED"
    assert admin.post(f"/api/v1/reviews/{doc_id}/heartbeat").status_code == 404  # nothing claimed yet
    review = admin.post(f"/api/v1/reviews/{doc_id}/claim").json()
    r = admin.post(f"/api/v1/reviews/{doc_id}/heartbeat")
    assert r.status_code == 200 and r.json()["id"] == review["id"]
    # Another user cannot keep someone else's claim alive
    other, _ = login(new_user["username"], STRONG)
    assert other.post(f"/api/v1/reviews/{doc_id}/heartbeat").status_code in (403, 404)
    admin.post(f"/api/v1/reviews/{doc_id}/release")


# --- login rate limit shared across processes ---------------------------------------

def test_login_rate_limit_is_enforced(monkeypatch):
    from src.api.routes.auth import login_limiter
    monkeypatch.setattr(login_limiter, "limit", 3)
    anon = TestClient(app)
    codes = [anon.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"}).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 429, 429]


async def test_rate_limit_is_shared_between_processes(db_session):
    from src.core.rate_limit import DatabaseRateLimiter
    # Two limiters stand in for two API processes: they see each other's attempts
    first, second = DatabaseRateLimiter(2, 60), DatabaseRateLimiter(2, 60)
    key = f"ip-{uuid.uuid4().hex[:8]}"
    assert await first.allow(db_session, key)
    assert await second.allow(db_session, key)
    assert not await first.allow(db_session, key)
    assert await second.allow(db_session, f"{key}-other")  # per client
