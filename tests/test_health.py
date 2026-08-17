"""Tests de health checks de producción."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app


def _ready_client(*, schema_exists=True, tables_exist=True):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    inspector = MagicMock()
    inspector.has_schema.return_value = schema_exists
    inspector.has_table.return_value = tables_exist
    return engine, inspector


def test_liveness_and_legacy_health_do_not_access_database():
    client = TestClient(app)
    with patch("src.api.main.get_engine") as get_engine:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health").json() == {"status": "ok"}
    get_engine.assert_not_called()
    client.close()


def test_readiness_checks_database_schema_and_required_tables():
    engine, inspector = _ready_client()
    client = TestClient(app)
    with patch("src.api.main.get_engine", return_value=engine), patch(
        "src.api.main.inspect", return_value=inspector
    ):
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert str(engine.connect.return_value.__enter__.return_value.execute.call_args.args[0]) == "SELECT 1"
    inspector.has_schema.assert_called_once_with("fide")
    assert inspector.has_table.call_count == 2
    engine.dispose.assert_called_once_with()
    client.close()


def test_readiness_returns_sanitized_503_when_database_fails():
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("postgresql://user:secret@database")
    client = TestClient(app)
    with patch("src.api.main.get_engine", return_value=engine):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "secret" not in response.text
    engine.dispose.assert_called_once_with()
    client.close()


def test_readiness_returns_503_when_required_table_is_missing():
    engine, inspector = _ready_client(tables_exist=False)
    client = TestClient(app)
    with patch("src.api.main.get_engine", return_value=engine), patch(
        "src.api.main.inspect", return_value=inspector
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    client.close()
