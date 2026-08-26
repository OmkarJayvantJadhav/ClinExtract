import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    assert response.status_code == 200
    
    # 9. JWT never returned in JSON
    data = response.json()
    assert "access_token" not in data
    assert "token" not in data
    
    # 8. Password hash never returned
    assert "password_hash" not in data
    assert "password" not in data
    
    assert data["username"] == "admin"
    assert data["role"] == "ADMIN"
    
    # Check cookies
    cookies = response.cookies
    assert "access_token" in cookies
    assert "clinextract_csrf" in cookies

@pytest.mark.asyncio
async def test_login_invalid_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "password123"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_me_without_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_me_with_auth(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    assert login_response.status_code == 200
    
    response = client.get(
        "/api/v1/auth/me", 
        cookies={"access_token": login_response.cookies["access_token"]}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"

@pytest.mark.asyncio
async def test_logout(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    response = client.post(
        "/api/v1/auth/logout",
        cookies={"access_token": login_response.cookies["access_token"]},
        headers={"X-CSRF-Token": login_response.cookies["clinextract_csrf"]}
    )
    assert response.status_code == 200
    assert not response.cookies.get("access_token")
    assert not response.cookies.get("clinextract_csrf")

@pytest.mark.asyncio
async def test_cookie_flags(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    assert response.status_code == 200
    
    # Inspect Set-Cookie headers directly to verify flags
    set_cookie_headers = response.headers.get_list("set-cookie")
    access_token_cookie = next(c for c in set_cookie_headers if c.startswith("access_token="))
    csrf_cookie = next(c for c in set_cookie_headers if c.startswith("clinextract_csrf="))
    
    # 10. auth cookie is HttpOnly
    assert "HttpOnly" in access_token_cookie
    # 11. auth cookie SameSite=Strict
    assert "SameSite=strict" in access_token_cookie.lower() or "samesite=strict" in access_token_cookie.lower()
    
    # CSRF cookie is NOT HttpOnly
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=strict" in csrf_cookie.lower() or "samesite=strict" in csrf_cookie.lower()
