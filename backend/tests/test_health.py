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


async def test_worker_is_not_pinged_when_the_broker_is_down(db_session, monkeypatch):
    import time
    from src.api.routes import health

    async def refuse(*args, **kwargs):
        raise ConnectionRefusedError("broker down")

    pinged = []

    def inspect(*args, **kwargs):
        pinged.append(True)
        raise ConnectionRefusedError("broker down")

    monkeypatch.setattr(health.aio_pika, "connect", refuse)
    monkeypatch.setattr(health.celery_app.control, "inspect", inspect)
    start = time.time()
    status = await health._check_dependencies(db_session)
    assert status["rabbitmq"] == "unavailable" and status["worker"] == "unavailable"
    assert status["database"] == "healthy"
    assert not pinged
    assert time.time() - start < 2
