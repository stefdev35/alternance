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

    def test_offers_json_city_filter(self, client):
        resp = client.get("/offers?city=lyon")
        rows = resp.json()
        assert rows
        assert all("lyon" in (r["workplace"]["location"].get("address") or "").lower()
                   for r in rows)

    def test_offers_json_skill_filter(self, client):
        resp = client.get("/offers?skill=autonomie")
        rows = resp.json()
        assert rows
        assert len(rows) <= len(client.get("/offers").json())

    def test_offers_json_diploma_filter(self, client):
        resp = client.get("/offers?diploma_level=6")
        rows = resp.json()
        assert rows
        assert all(r["target_diploma_european"] == "6" for r in rows)

    def test_index_renders_filters_form(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "city" in resp.text
        assert "skill" in resp.text
        assert "diploma_level" in resp.text

    def test_filters_endpoint(self, client):
        resp = client.get("/filters")
        assert resp.status_code == 200
        data = resp.json()
        assert "cities" in data and "skills" in data and "diploma_levels" in data

    def test_skills_autocomplete_endpoint(self, client):
        resp = client.get("/skills?q=faire")
        assert resp.status_code == 200
        skills = resp.json()
        assert skills
        assert all(s.lower().startswith("faire") for s in skills)

    def test_skills_autocomplete_requires_q(self, client):
        assert client.get("/skills").status_code == 422

    def test_skills_autocomplete_prefix_dynamic(self, client):
        """Chaque préfixe renvoie un sous-ensemble adapté (progression)."""
        broad = client.get("/skills?q=faire").json()
        narrow = client.get("/skills?q=faire preuve d'auto").json()
        assert narrow
        assert set(narrow) <= set(broad)

    def test_index_has_autocomplete_script(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "skill-input" in resp.text
        assert "autocomplete-list" in resp.text
        assert "/skills?q=" in resp.text

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
