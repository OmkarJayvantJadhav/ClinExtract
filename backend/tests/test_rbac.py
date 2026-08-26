import pytest

# Roles: ADMIN, REVIEWER, OPERATOR, VIEWER

def get_auth_kwargs(client, username, password):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password}
    )
    assert login_response.status_code == 200
    return {
        "cookies": {
            "access_token": login_response.cookies["access_token"],
            "clinextract_csrf": login_response.cookies["clinextract_csrf"]
        },
        "headers": {
            "X-CSRF-Token": login_response.cookies["clinextract_csrf"]
        }
    }

@pytest.mark.asyncio
async def test_admin_rbac(client):
    kwargs = get_auth_kwargs(client, "admin", "devpass_admin")
    
    assert client.get("/api/v1/users/admin-only", **kwargs).status_code == 200
    assert client.get("/api/v1/users/reviewer-plus", **kwargs).status_code == 200
    assert client.get("/api/v1/users/operator-plus", **kwargs).status_code == 200
    assert client.get("/api/v1/users/viewer-plus", **kwargs).status_code == 200

@pytest.mark.asyncio
async def test_reviewer_rbac(client):
    kwargs = get_auth_kwargs(client, "reviewer", "devpass_reviewer")
    
    assert client.get("/api/v1/users/admin-only", **kwargs).status_code == 403
    assert client.get("/api/v1/users/reviewer-plus", **kwargs).status_code == 200
    assert client.get("/api/v1/users/operator-plus", **kwargs).status_code == 200
    assert client.get("/api/v1/users/viewer-plus", **kwargs).status_code == 200

@pytest.mark.asyncio
async def test_operator_rbac(client):
    kwargs = get_auth_kwargs(client, "operator", "devpass_operator")
    
    assert client.get("/api/v1/users/admin-only", **kwargs).status_code == 403
    assert client.get("/api/v1/users/reviewer-plus", **kwargs).status_code == 403
    assert client.get("/api/v1/users/operator-plus", **kwargs).status_code == 200
    assert client.get("/api/v1/users/viewer-plus", **kwargs).status_code == 200

@pytest.mark.asyncio
async def test_viewer_rbac(client):
    kwargs = get_auth_kwargs(client, "viewer", "devpass_viewer")
    
    assert client.get("/api/v1/users/admin-only", **kwargs).status_code == 403
    assert client.get("/api/v1/users/reviewer-plus", **kwargs).status_code == 403
    assert client.get("/api/v1/users/operator-plus", **kwargs).status_code == 403
    assert client.get("/api/v1/users/viewer-plus", **kwargs).status_code == 200
    
    # Viewer shouldn't be able to mutate
    assert client.post("/api/v1/users/dummy-mutation", **kwargs).status_code == 403
