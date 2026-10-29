"""Tests du pipeline d'ingestion (mode mock)."""

from unittest.mock import patch

from alternance.config import settings
from alternance.ingest import ingest


class TestIngest:
    def test_ingest_mock_populates_duckdb(self, tmp_path, sample_offers, monkeypatch):
        monkeypatch.setattr(settings, "lba_api_key", "")
        monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "ingest.duckdb"))

        with patch(
            "alternance.lba_api.load_sample_offers", return_value=sample_offers
        ) as mock_load:
            report = ingest()

        mock_load.assert_called_once()
        assert report["offers_ingested"] == len(sample_offers)
        assert report["duckdb_total"] == len(sample_offers)

    def test_ingest_max_offers(self, tmp_path, sample_offers, monkeypatch):
        monkeypatch.setattr(settings, "lba_api_key", "")
        monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "ingest2.duckdb"))

        with patch(
            "alternance.lba_api.load_sample_offers", return_value=sample_offers
        ):
            report = ingest(max_offers=2)

        assert report["offers_ingested"] == 2
        assert report["duckdb_total"] == 2
