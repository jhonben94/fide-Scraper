"""Tests para /admin/import-history endpoint."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestImportHistoryValidation:
    """Validaciones de ImportHistoryRequest."""

    def test_period_must_be_first_day_of_month(self):
        """Rechazar fechas que no sean el primer día del mes."""
        from src.api.admin_routes import ImportHistoryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ImportHistoryRequest(period="2026-07-15")

        errors = exc_info.value.errors()
        assert any("period" in str(e).lower() for e in errors)

    def test_period_july_1st_is_valid(self):
        """Período del primer día del mes es válido."""
        from src.api.admin_routes import ImportHistoryRequest

        req = ImportHistoryRequest(period="2026-07-01")
        assert req.period == "2026-07-01"

    def test_use_current_files_requires_period(self):
        """Rechazar use_current_files=true sin period."""
        from src.api.admin_routes import ImportHistoryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ImportHistoryRequest(use_current_files=True)

        errors = exc_info.value.errors()
        assert any("use_current_files" in str(e).lower() or "period" in str(e).lower() for e in errors)

    def test_use_current_files_with_period_is_valid(self):
        """use_current_files=true con period es válido."""
        from src.api.admin_routes import ImportHistoryRequest

        req = ImportHistoryRequest(period="2026-07-01", use_current_files=True)
        assert req.period == "2026-07-01"
        assert req.use_current_files is True


class TestImportHistoryExplicitPeriod:
    """Tests para importación de período explícito."""

    def test_explicit_period_ignores_months_and_period_scope(self):
        """Cuando existe period, months y period_scope no deben afectar la selección."""
        from src.api.admin_routes import ImportHistoryRequest

        req = ImportHistoryRequest(
            period="2026-07-01",
            months=60,
            period_scope="current_year",
        )
        assert req.period == "2026-07-01"
        assert req.months == 60
        assert req.period_scope == "current_year"


class TestImportHistorySkipCompleted:
    """Tests para skip_completed."""

    def test_skip_completed_true_omits_period(self, mock_downloader):
        """skip_completed=true omite el período si ya fue importado."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()

            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            mock_session.execute.return_value = [(date(2026, 7, 1),)]

            from src.importer_history import run_import_history

            result = run_import_history(
                explicit_period="2026-07-01",
                use_current_files=True,
                skip_completed=True,
                country_codes=frozenset({"PAR"}),
            )

            assert "2026-07-01" in result["periods_skipped"]
            assert result["total_periods"] == 0

    def test_skip_completed_false_reimports(self, mock_downloader):
        """skip_completed=false permite refrescar el snapshot."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()

            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            mock_session.execute.return_value = []

            from src.importer_history import run_import_history

            result = run_import_history(
                explicit_period="2026-07-01",
                use_current_files=True,
                skip_completed=False,
                country_codes=frozenset({"PAR"}),
            )

            assert result["periods_requested"] == 1
            assert "2026-07-01" in result["periods_imported"]


class TestImportHistorySource:
    """Tests para el campo source en el resultado."""

    def test_source_archive_when_using_historical_files(self, mock_downloader):
        """source='archive' cuando se usan archivos históricos."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()

            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            mock_session.execute.return_value = []

            from src.importer_history import run_import_history

            result = run_import_history(
                explicit_period="2026-06-01",
                use_current_files=False,
                skip_completed=False,
                country_codes=frozenset({"PAR"}),
            )

            assert result["source"] == "archive"

    def test_source_current_files_when_use_current_true(self, mock_downloader):
        """source='current_files' cuando use_current_files=True."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()

            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            mock_session.execute.return_value = []

            from src.importer_history import run_import_history

            result = run_import_history(
                explicit_period="2026-07-01",
                use_current_files=True,
                skip_completed=False,
                country_codes=frozenset({"PAR"}),
            )

            assert result["source"] == "current_files"


class TestGetCurrentXmlZipUrls:
    """Tests para get_current_xml_zip_urls()."""

    def test_returns_all_three_urls(self):
        """Retorna standard, rapid y blitz."""
        from src.downloader import get_current_xml_zip_urls

        urls = get_current_xml_zip_urls()

        assert "standard" in urls
        assert "rapid" in urls
        assert "blitz" in urls
        assert urls["standard"] == "https://ratings.fide.com/download/standard_rating_list_xml.zip"
        assert urls["rapid"] == "https://ratings.fide.com/download/rapid_rating_list_xml.zip"
        assert urls["blitz"] == "https://ratings.fide.com/download/blitz_rating_list_xml.zip"


class TestTraditionalImport:
    """Tests para importación tradicional sin regressiones."""

    def test_rolling_months_default(self, mock_downloader):
        """Modo rolling_months por defecto."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()

            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            mock_session.execute.return_value = []

            from src.importer_history import run_import_history

            result = run_import_history(
                months=2,
                period_scope="rolling_months",
                skip_completed=False,
                country_codes=frozenset({"PAR"}),
            )

            assert result["period_scope"] == "rolling_months"
            assert result["source"] == "archive"
            assert result["periods_requested"] == 2

    def test_current_year_scope(self, mock_downloader):
        """Modo current_year genera periodos de enero a mes actual."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()

            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            mock_session.execute.return_value = []

            from datetime import date
            from unittest.mock import patch as mock_patch

            with mock_patch("src.importer_history.date") as mock_date:
                mock_date.today.return_value = date(2026, 6, 15)
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

                from src.importer_history import run_import_history

                result = run_import_history(
                    months=12,
                    period_scope="current_year",
                    skip_completed=False,
                    country_codes=frozenset({"PAR"}),
                )

                assert result["period_scope"] == "current_year"
                assert result["source"] == "archive"


class TestDailyChangeSync:
    """Tests para run_daily_change_sync: solo debe persistir filas cuando algo cambió de verdad."""

    def test_new_player_is_written(self, mock_downloader):
        """Un fideid sin historial previo se escribe como cambio (alta nueva)."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"), \
             patch("src.importer_history._load_tracked_fideids", return_value=set()), \
             patch("src.importer_history._load_last_known_ratings", return_value={}), \
             patch("src.importer_history._batch_upsert_history_full") as mock_upsert, \
             patch("src.importer_history._upsert_checkpoint"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)
            mock_upsert.side_effect = lambda session, batch, period: len(batch)

            from src.importer_history import run_daily_change_sync

            result = run_daily_change_sync(country_codes=frozenset({"PAR"}), period=date(2026, 8, 1))

            assert result["rows_changed"] == 1
            written = mock_upsert.call_args[0][1]
            # El fixture mock_downloader reusa el mismo XML (rating=2400) para los tres ZIP de
            # modalidad, y cada pasada lee el tag genérico <rating>; por eso std/rpd/blz dan 2400.
            assert written == [
                {"fideid": 123456, "rating": 2400, "rapid_rating": 2400, "blitz_rating": 2400}
            ]

    def test_unchanged_player_is_skipped(self, mock_downloader):
        """Si el último valor conocido es idéntico al de hoy, no se escribe ninguna fila."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"), \
             patch("src.importer_history._load_tracked_fideids", return_value={123456}), \
             patch(
                 "src.importer_history._load_last_known_ratings",
                 return_value={123456: (2400, 2400, 2400)},
             ), \
             patch("src.importer_history._batch_upsert_history_full") as mock_upsert, \
             patch("src.importer_history._upsert_checkpoint"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            from src.importer_history import run_daily_change_sync

            result = run_daily_change_sync(country_codes=frozenset({"PAR"}), period=date(2026, 8, 1))

            assert result["rows_changed"] == 0
            mock_upsert.assert_not_called()

    def test_player_missing_from_all_lists_gets_explicit_null_row(self, mock_downloader):
        """Un jugador ya trackeado que desaparece de las tres listas se registra en NULL (baja real),
        no se ignora ni conserva silenciosamente el último valor."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"), \
              patch(
                  "src.importer_history._load_tracked_fideids",
                  return_value={123456, 999999},
              ), \
              patch(
                  "src.importer_history._load_country_fideids",
                  return_value={123456, 999999},
              ), \
             patch(
                 "src.importer_history._load_last_known_ratings",
                 return_value={123456: (2400, 2400, 2400), 999999: (1500, 1500, 1500)},
             ), \
             patch("src.importer_history._batch_upsert_history_full") as mock_upsert, \
             patch("src.importer_history._upsert_checkpoint"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)
            mock_upsert.side_effect = lambda session, batch, period: len(batch)

            from src.importer_history import run_daily_change_sync

            result = run_daily_change_sync(country_codes=frozenset({"PAR"}), period=date(2026, 8, 1))

            assert result["rows_changed"] == 1
            written = mock_upsert.call_args[0][1]
            assert written == [
                {"fideid": 999999, "rating": None, "rapid_rating": None, "blitz_rating": None}
            ]

    def test_filtered_sync_only_nulls_missing_tracked_players_inside_scope(self, mock_downloader):
        """PAR y afiliados son evaluables; un extranjero no afiliado no debe nulificarse."""
        par_fideid = 123456
        affiliated_foreign_fideid = 222222
        unrelated_foreign_fideid = 333333

        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"), \
             patch(
                 "src.importer_history.load_affiliated_fideids",
                 return_value=frozenset({affiliated_foreign_fideid}),
             ), \
             patch(
                 "src.importer_history._load_tracked_fideids",
                 return_value={par_fideid, affiliated_foreign_fideid, unrelated_foreign_fideid},
             ), \
             patch(
                 "src.importer_history._load_country_fideids",
                 return_value={par_fideid},
             ), \
             patch(
                 "src.importer_history._load_last_known_ratings",
                 return_value={
                     par_fideid: (2400, 2400, 2400),
                     affiliated_foreign_fideid: (2100, 2050, 2000),
                     unrelated_foreign_fideid: (1900, 1850, 1800),
                 },
             ) as mock_last_known, \
             patch("src.importer_history._batch_upsert_history_full") as mock_upsert, \
             patch("src.importer_history._upsert_checkpoint"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)
            mock_upsert.side_effect = lambda session, batch, period: len(batch)

            from src.importer_history import run_daily_change_sync

            result = run_daily_change_sync(
                country_codes=frozenset({"PAR"}),
                include_club_affiliates=True,
                period=date(2026, 8, 1),
            )

            assert result["players_evaluated"] == 2
            assert result["rows_changed"] == 1
            mock_last_known.assert_called_once_with(
                mock_session, {par_fideid, affiliated_foreign_fideid}
            )
            assert mock_upsert.call_args[0][1] == [
                {
                    "fideid": affiliated_foreign_fideid,
                    "rating": None,
                    "rapid_rating": None,
                    "blitz_rating": None,
                }
            ]

    def test_period_defaults_to_today(self, mock_downloader):
        """Sin --period explícito, usa la fecha de hoy."""
        with patch("src.importer_history.get_db_session") as mock_db, \
             patch("src.importer_history.get_engine") as mock_engine, \
             patch("src.importer_history.init_db"), \
             patch("src.importer_history._load_tracked_fideids", return_value=set()), \
             patch("src.importer_history._load_last_known_ratings", return_value={}), \
             patch("src.importer_history._batch_upsert_history_full", return_value=1), \
             patch("src.importer_history._upsert_checkpoint"):

            mock_session = MagicMock()
            mock_engine.return_value = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=None)

            from src.importer_history import run_daily_change_sync

            result = run_daily_change_sync(country_codes=frozenset({"PAR"}))

            assert result["period"] == date.today().strftime("%Y-%m-%d")
