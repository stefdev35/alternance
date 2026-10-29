"""Tests du stockage documentaire MongoDB.

Nécessite un MongoDB accessible (docker compose up -d). Les tests sont
ignorés automatiquement si MongoDB n'est pas joignable.
"""

import pytest

from alternance.storage.mongo_store import MongoStore


@pytest.fixture()
def mongo_store():
    store = MongoStore(db_name="alternance_test")
    if not store.is_available():
        pytest.skip("MongoDB indisponible — lancer 'docker compose up -d'")
    store.collection.delete_many({})
    yield store
    store.collection.delete_many({})
    store.close()


class TestMongoStore:
    def test_upsert_and_count(self, mongo_store, sample_offers):
        mongo_store.upsert_many(sample_offers)
        assert mongo_store.count_offers() == len(sample_offers)

    def test_upsert_is_idempotent(self, mongo_store, sample_offers):
        mongo_store.upsert_many(sample_offers)
        mongo_store.upsert_many(sample_offers)
        assert mongo_store.count_offers() == len(sample_offers)

    def test_document_stored_as_is(self, mongo_store, sample_offers):
        mongo_store.upsert_many(sample_offers)
        offer = sample_offers[0]
        doc = mongo_store.get_offer(offer.id)
        assert doc is not None
        # Approche NoSQL : le document garde sa structure imbriquée.
        assert doc["offer"]["title"] == offer.offer.title
        assert doc["workplace"]["location"]["address"] == offer.workplace.location.address
        assert doc["offer"]["desired_skills"] == offer.offer.desired_skills

    def test_list_offers_shape(self, mongo_store, sample_offers):
        mongo_store.upsert_many(sample_offers)
        rows = mongo_store.list_offers(limit=5)
        assert rows
        assert all(
            {"id", "title", "partner_label", "workplace", "offer"} <= set(r) for r in rows
        )

    def test_list_offers_title_filter(self, mongo_store, sample_offers):
        mongo_store.upsert_many(sample_offers)
        rows = mongo_store.list_offers(title="python")
        assert rows
        assert all("Python" in r["title"] for r in rows)

    def test_get_offer_unknown_returns_none(self, mongo_store):
        assert mongo_store.get_offer("inexistant") is None
