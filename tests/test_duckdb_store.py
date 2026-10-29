"""Tests du stockage relationnel DuckDB (schéma normalisé)."""

import pytest

from alternance.storage.duckdb_store import DuckDBStore


@pytest.fixture()
def store(tmp_path):
    db = DuckDBStore(db_path=str(tmp_path / "test.duckdb"))
    yield db
    db.close()


class TestDuckDBStore:
    def test_upsert_and_count(self, store, sample_offers):
        n = store.upsert_many(sample_offers)
        assert n == len(sample_offers)
        assert store.count_offers() == len(sample_offers)

    def test_upsert_is_idempotent(self, store, sample_offers):
        store.upsert_many(sample_offers)
        store.upsert_many(sample_offers)
        assert store.count_offers() == len(sample_offers)

    def test_get_offer_roundtrip(self, store, sample_offers):
        store.upsert_many(sample_offers)
        offer = sample_offers[0]
        nested = store.get_offer(offer.id)
        assert nested is not None
        assert nested["offer"]["title"] == offer.offer.title
        assert nested["identifier"]["partner_job_id"] == offer.identifier.partner_job_id
        assert nested["offer"]["rome_codes"] == offer.offer.rome_codes

    def test_get_offer_restores_relations(self, store, sample_offers):
        store.upsert_many(sample_offers)
        offer = sample_offers[0]
        nested = store.get_offer(offer.id)
        # Les listes sont stockées en lignes relationnelles : l'ordre
        # d'origine n'est pas préservé → comparaison sans tenir compte de l'ordre.
        assert sorted(nested["offer"]["desired_skills"]) == sorted(offer.offer.desired_skills)
        assert sorted(nested["offer"]["to_be_acquired_skills"]) == sorted(offer.offer.to_be_acquired_skills)
        assert sorted(nested["offer"]["access_conditions"]) == sorted(offer.offer.access_conditions)
        if offer.contract:
            assert sorted(nested["contract"]["type"]) == sorted(offer.contract.type)
        if offer.workplace:
            wp = nested["workplace"]
            assert wp["name"] == offer.workplace.name
            assert wp["domain"]["naf"]["code"] == offer.workplace.domain.naf.code

    def test_list_offers(self, store, sample_offers):
        store.upsert_many(sample_offers)
        rows = store.list_offers(limit=10)
        assert len(rows) == min(10, len(sample_offers))
        assert all("id" in r and "title" in r and "workplace" in r for r in rows)

    def test_list_offers_title_filter(self, store, sample_offers):
        store.upsert_many(sample_offers)
        rows = store.list_offers(title="python")
        assert rows
        assert all("Python" in r["title"] for r in rows)

    def test_get_offer_unknown_returns_none(self, store):
        assert store.get_offer("inexistant") is None
