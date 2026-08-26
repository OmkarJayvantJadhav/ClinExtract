import pytest

@pytest.mark.asyncio
async def test_csrf_missing_token(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    assert login_response.status_code == 200
    
    # Authenticated mutation without CSRF token
    response = client.post(
        "/api/v1/users/dummy-mutation",
        cookies={"access_token": login_response.cookies["access_token"], "clinextract_csrf": login_response.cookies["clinextract_csrf"]}
        # No X-CSRF-Token header
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_csrf_invalid_token(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    assert login_response.status_code == 200
    
    # Authenticated mutation with invalid CSRF token
    response = client.post(
        "/api/v1/users/dummy-mutation",
        cookies={"access_token": login_response.cookies["access_token"], "clinextract_csrf": login_response.cookies["clinextract_csrf"]},
        headers={"X-CSRF-Token": "invalid_token_value"}
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_csrf_valid_token(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "devpass_admin"}
    )
    assert login_response.status_code == 200
    
    # Authenticated mutation with valid CSRF token
    response = client.post(
        "/api/v1/users/dummy-mutation",
        cookies={"access_token": login_response.cookies["access_token"], "clinextract_csrf": login_response.cookies["clinextract_csrf"]},
        headers={"X-CSRF-Token": login_response.cookies["clinextract_csrf"]}
    )
    assert response.status_code == 200
