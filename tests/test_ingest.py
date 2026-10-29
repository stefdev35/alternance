"""Tests du pipeline d'ingestion (mode mock)."""

from pathlib import Path
from unittest.mock import patch

from alternance.config import settings
from alternance.ingest import ingest
from alternance.scrapers.indeed import parse_search_results
from alternance.scrapers.normalize import search_result_to_joboffer

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _indeed_offers():
    html = (FIXTURES / "indeed_search.html").read_text(encoding="utf-8")
    return [search_result_to_joboffer(job) for job in parse_search_results(html)]


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

    def test_ingest_indeed_source(self, tmp_path, monkeypatch):
        """La source Indeed produit des offres normalisées, stockables."""
        monkeypatch.setattr(settings, "lba_api_key", "")
        monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "ingest3.duckdb"))

        with patch(
            "alternance.ingest.fetch_indeed_offers", return_value=_indeed_offers()
        ):
            report = ingest(source="indeed")

        assert report["source"] == "indeed"
        assert report["offers_ingested"] == 2
        assert report["duckdb_total"] == 2
