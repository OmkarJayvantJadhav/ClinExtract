from src.db.models import Base

def test_health_returns_200(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200

def test_health_response_structure(client):
    response = client.get("/api/v1/health")
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert data["status"] == "healthy"

def test_correlation_id_is_returned(client):
    response = client.get("/api/v1/health")
    assert "x-correlation-id" in response.headers

def test_correlation_id_is_preserved(client):
    test_id = "test-1234-uuid"
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": test_id})
    assert response.headers["x-correlation-id"] == test_id

def test_database_models_import():
    from src.db.models import User, Document, Extraction
    assert User.__tablename__ == "users"

def test_alembic_metadata_connected():
    assert len(Base.metadata.tables) > 0
    assert "users" in Base.metadata.tables
