"""Tests de l'application web FastAPI (TestClient)."""

import pytest
from fastapi.testclient import TestClient

from alternance.config import settings
from alternance.storage.duckdb_store import DuckDBStore
from alternance.storage.mongo_store import MongoStore
from alternance.web.app import app


@pytest.fixture()
def client(tmp_path, sample_offers, monkeypatch):
    db_path = tmp_path / "web.duckdb"
    monkeypatch.setattr(settings, "duckdb_path", str(db_path))

    # Prépare les données DuckDB avant les requêtes.
    store = DuckDBStore(db_path=str(db_path))
    store.upsert_many(sample_offers)
    store.close()

    with TestClient(app) as test_client:
        yield test_client


class TestWebApp:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["duckdb"] is True
        assert body["mongo"] in (True, False)

    def test_index_renders_offers(self, client, sample_offers):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "offre(s)" in resp.text
        assert sample_offers[0].offer.title.split()[0] in resp.text

    def test_index_backend_switch(self, client):
        resp = client.get("/?backend=duckdb")
        assert resp.status_code == 200
        assert "DuckDB" in resp.text

    def test_offers_json(self, client):
        resp = client.get("/offers")
        assert resp.status_code == 200
        rows = resp.json()
        assert rows
        assert all("id" in r and "title" in r for r in rows)

    def test_offers_json_title_filter(self, client):
        resp = client.get("/offers?title=python")
        rows = resp.json()
        assert rows
        assert all("Python" in r["title"] for r in rows)

    def test_offer_detail_html(self, client, sample_offers):
        offer = sample_offers[0]
        resp = client.get(f"/offers/{offer.id}")
        assert resp.status_code == 200
        assert offer.offer.title in resp.text

    def test_offer_detail_json(self, client, sample_offers):
        offer = sample_offers[0]
        resp = client.get(f"/offers/{offer.id}/json")
        assert resp.status_code == 200
        assert resp.json()["offer"]["title"] == offer.offer.title

    def test_offer_detail_not_found(self, client):
        assert client.get("/offers/inexistant").status_code == 404


@pytest.mark.skipif(
    not MongoStore().is_available(), reason="MongoDB indisponible — lancer 'docker compose up -d'"
)
class TestWebAppMongo:
    def test_mongo_backend_list_and_detail(self, tmp_path, sample_offers):
        mongo = MongoStore(db_name="alternance_test_web")
        mongo.collection.delete_many({})
        mongo.upsert_many(sample_offers)
        mongo.close()

        try:
            with TestClient(app) as client:
                resp = client.get("/?backend=mongo")
                assert resp.status_code == 200
                assert "offre(s)" in resp.text

                offer = sample_offers[0]
                resp = client.get(f"/offers/{offer.id}?backend=mongo")
                assert resp.status_code == 200
                assert offer.offer.title in resp.text

                resp = client.get(f"/offers/{offer.id}/json?backend=mongo")
                assert resp.status_code == 200
                assert resp.json()["offer"]["title"] == offer.offer.title
        finally:
            mongo = MongoStore(db_name="alternance_test_web")
            mongo.collection.delete_many({})
            mongo.close()
