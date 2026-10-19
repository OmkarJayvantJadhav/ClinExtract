"""Sign-in protections that must hold under concurrent requests, and claim renewal."""
import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select, update

from src.core.config import settings
from src.main import app

STRONG = "Str0ng-Passw0rd!"


async def _client(username, password):
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    r = await c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = c.cookies["clinextract_csrf"]
    return c


async def _new_user(admin, role):
    username = f"{role.lower()}_{uuid.uuid4().hex[:8]}"
    r = await admin.post("/api/v1/users", json={"username": username, "role": role, "password": STRONG})
    assert r.status_code == 201, r.text
    return username, r.json()["id"]


async def test_concurrent_logins_cannot_exceed_the_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    from src.api.routes import auth
    monkeypatch.setattr(auth.login_limiter, "limit", 5)
    ip = f"10.9.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        responses = await asyncio.gather(*[
            c.post("/api/v1/auth/login", json={"username": "nobody", "password": "x" * 12}, headers={"X-Real-IP": ip})
            for _ in range(30)
        ])
    codes = [r.status_code for r in responses]
    assert codes.count(401) == 5 and codes.count(429) == 25


async def test_two_admins_cannot_demote_each_other_at_once():
    root = await _client("admin", "devpass_admin")
    a_name, a_id = await _new_user(root, "ADMIN")
    b_name, b_id = await _new_user(root, "ADMIN")
    a, b = await _client(a_name, STRONG), await _client(b_name, STRONG)
    r1, r2 = await asyncio.gather(
        a.patch(f"/api/v1/users/{b_id}", json={"role": "VIEWER"}),
        b.patch(f"/api/v1/users/{a_id}", json={"role": "VIEWER"}),
    )
    # The second is refused: 403 under the lock, or 401 if the first demotion (which ends the
    # demoted admin's sessions) was committed before it was authenticated
    codes = sorted([r1.status_code, r2.status_code])
    assert codes[0] == 200 and codes[1] in (401, 403), codes
    users = {u["id"]: u["role"] for u in (await root.get("/api/v1/users")).json()}
    assert sorted([users[a_id], users[b_id]]) == ["ADMIN", "VIEWER"]


async def test_wrong_current_password_counts_towards_the_lockout():
    from src.core.config import settings
    root = await _client("admin", "devpass_admin")
    name, _ = await _new_user(root, "VIEWER")
    user = await _client(name, STRONG)
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS - 1):
        r = await user.post("/api/v1/auth/change-password", json={"current_password": "Wr0ng-Guess-123", "new_password": "N3w-Passw0rd-xyz"})
        assert r.status_code == 400
    r = await user.post("/api/v1/auth/change-password", json={"current_password": "Wr0ng-Guess-123", "new_password": "N3w-Passw0rd-xyz"})
    assert r.status_code == 429
    # The session used for guessing is ended, and the right password no longer helps
    assert (await user.get("/api/v1/auth/me")).status_code == 401
    fresh = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await fresh.post("/api/v1/auth/login", json={"username": name, "password": STRONG})).status_code == 429
    actions = [e["action"] for e in (await root.get("/api/v1/audit", params={"size": 100})).json()["items"]]
    assert "USER_PASSWORD_CHANGE_FAILED" in actions and "USER_ACCOUNT_LOCKED" in actions


async def test_reopening_a_review_renews_the_claim(db_session):
    import pymupdf
    from src.db.models.review import Review
    root = await _client("admin", "devpass_admin")
    name, _ = await _new_user(root, "REVIEWER")
    other = await _client(name, STRONG)
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "Patient Name: Claim Test", fontsize=12)
    doc_id = (await root.post("/api/v1/documents", files={"file": (f"claim_{uuid.uuid4().hex[:6]}.pdf", io.BytesIO(doc.write()), "application/pdf")})).json()["id"]
    review_id = (await root.post(f"/api/v1/reviews/{doc_id}/claim")).json()["id"]
    # The admin's laptop slept past the claim timeout, then they reopen the document
    await db_session.execute(update(Review).where(Review.id == uuid.UUID(review_id))
                             .values(updated_at=datetime.now(timezone.utc) - timedelta(hours=2)))
    await db_session.commit()
    assert (await root.post(f"/api/v1/reviews/{doc_id}/claim")).status_code == 200
    assert (await other.post(f"/api/v1/reviews/{doc_id}/claim")).status_code == 409
    await root.post(f"/api/v1/reviews/{doc_id}/release")
