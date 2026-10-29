"""Tests de la normalisation Indeed → JobOffer (compatibilité des sources)."""

from pathlib import Path

import pytest

from alternance.models import JobOffer
from alternance.scrapers.indeed import IndeedJob, parse_job_detail, parse_search_results
from alternance.scrapers.normalize import (
    detail_to_joboffer,
    enrich_with_detail,
    search_result_to_joboffer,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _search_jobs() -> list[IndeedJob]:
    html = (FIXTURES / "indeed_search.html").read_text(encoding="utf-8")
    return parse_search_results(html)


def _detail(job_key: str = "abc123def"):
    html = (FIXTURES / "indeed_viewjob.html").read_text(encoding="utf-8")
    return parse_job_detail(html, job_key)


class TestSearchResultToJobOffer:
    def test_is_joboffer_instance(self):
        offer = search_result_to_joboffer(_search_jobs()[0])
        assert isinstance(offer, JobOffer)

    def test_identifier_compat_lba(self):
        offer = search_result_to_joboffer(_search_jobs()[0])
        assert offer.identifier.partner_label == "Indeed"
        assert offer.identifier.partner_job_id == "abc123def"
        # Compatibilité : id retombe sur partner_job_id.
        assert offer.id == "abc123def"

    def test_minimal_fields(self):
        offer = search_result_to_joboffer(_search_jobs()[0])
        assert offer.offer.title == "Développeur / Développeuse Python en alternance"
        assert offer.workplace.name == "TechCorp Solutions"
        assert offer.workplace.location.address == "Lyon (69)"
        assert offer.offer.status == "Active"
        assert offer.is_delegated is False
        assert offer.apply.url == "https://fr.indeed.com/viewjob?jk=abc123def"

    def test_rome_codes_empty(self):
        """Indeed n'expose pas les codes ROME → liste vide (champ requis LBA)."""
        offer = search_result_to_joboffer(_search_jobs()[0])
        assert offer.offer.rome_codes == []


class TestDetailToJobOffer:
    def test_full_normalization(self):
        offer = detail_to_joboffer(_detail())
        assert offer.offer.title == "Développeur / Développeuse Python en alternance"
        assert "FastAPI" in offer.offer.description
        assert offer.contract.type == ["Apprentissage"]
        assert offer.contract.remote == "hybrid"
        assert offer.workplace.name == "TechCorp Solutions"

    def test_roundtrip_pydantic(self):
        """L'offre normalisée doit repasser dans le modèle sans erreur (compatibilité)."""
        offer = detail_to_joboffer(_detail())
        data = offer.model_dump(mode="json")
        assert JobOffer.model_validate(data) == offer

    def test_publishable_in_stores(self):
        """L'offre normalisée est utilisable par les stores (même schéma que LBA)."""
        from alternance.storage.duckdb_store import DuckDBStore

        store = DuckDBStore(db_path=":memory:")
        store.upsert_offer(detail_to_joboffer(_detail()))
        assert store.count_offers() == 1
        row = store.get_offer("abc123def")
        assert row["offer"]["title"] == "Développeur / Développeuse Python en alternance"
        store.close()


class TestEnrichWithDetail:
    def test_combines_both_sources(self):
        job = _search_jobs()[0]
        detail = _detail(job.job_key)
        offer = enrich_with_detail(job, detail)
        assert offer.offer.description  # détail rempli
        assert offer.offer.publication.creation  # date remplie
        assert offer.contract.type == ["Apprentissage"]
