"""Pytest fixtures y configuration."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.database import Base, get_db_session, get_engine
from src.api.admin_routes import admin_router


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = get_engine(url=f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def test_client(temp_db):
    """Create a test client with temporary database."""
    from src.api.main import app

    def _override_get_db():
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=temp_db)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_downloader():
    """Mock downloader functions to avoid network calls."""

    def _create_mock_xml(name: str = "players_list_xml.xml", fideid: int = 123456) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<players>
  <player>
    <fideid>{fideid}</fideid>
    <name>Test Player</name>
    <country>PAR</country>
    <rating>2400</rating>
    <games>100</games>
    <rapid_rating>2350</rapid_rating>
    <rapid_games>50</rapid_games>
    <blitz_rating>2300</blitz_rating>
    <blitz_games>30</blitz_games>
  </player>
</players>"""

    def _create_mock_zip(xml_content: str) -> bytes:
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("standard_rating_list_xml.xml", xml_content)
        return buf.getvalue()

    with patch("src.importer_history.discover_period_archive_xml_zip_urls") as mock_discover, \
         patch("src.importer_history.get_current_xml_zip_urls") as mock_current, \
         patch("src.importer_history.extracted_xml_from_zip_url") as mock_extract, \
         patch("src.downloader.extracted_xml_from_zip_url") as mock_extract_dl:

        mock_discover.return_value = {
            "standard": "https://ratings.fide.com/download/standard_xml.zip",
            "rapid": "https://ratings.fide.com/download/rapid_xml.zip",
            "blitz": "https://ratings.fide.com/download/blitz_xml.zip",
        }

        mock_current.return_value = {
            "standard": "https://ratings.fide.com/download/standard_rating_list_xml.zip",
            "rapid": "https://ratings.fide.com/download/rapid_rating_list_xml.zip",
            "blitz": "https://ratings.fide.com/download/blitz_rating_list_xml.zip",
        }

        xml_std = _create_mock_xml("standard_rating_list_xml.xml")
        xml_rpd = _create_mock_xml("rapid_rating_list_xml.xml")
        xml_blz = _create_mock_xml("blitz_rating_list_xml.xml")

        def side_effect(url: str):
            if "standard" in url:
                content = xml_std
            elif "rapid" in url:
                content = xml_rpd
            else:
                content = xml_blz

            fd, tmp = tempfile.mkstemp(suffix=".xml")
            import os
            os.close(fd)
            Path(tmp).write_text(content, encoding="utf-8")

            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=Path(tmp))
            mock_ctx.__exit__ = MagicMock(return_value=None)
            return mock_ctx

        mock_extract.side_effect = side_effect
        mock_extract_dl.side_effect = side_effect

        yield {
            "mock_discover": mock_discover,
            "mock_current": mock_current,
            "mock_extract": mock_extract,
            "mock_extract_dl": mock_extract_dl,
        }
