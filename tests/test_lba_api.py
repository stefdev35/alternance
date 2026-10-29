"""Tests du client API LBA (couche HTTP mockée)."""

from unittest.mock import MagicMock

import pytest
import requests

from alternance.lba_api import LbaApiClient, LbaApiError, load_sample_offers


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def make_client(payload):
    session = MagicMock()
    session.request.return_value = FakeResponse(payload)
    client = LbaApiClient("https://api.example.org/api", "secret-key")
    client.session = session
    return client, session


class TestLbaApiClient:
    def test_authentication_header(self):
        client = LbaApiClient("https://api.example.org/api", "secret-key")
        assert client.session.headers["Authorization"] == "Bearer secret-key"

    def test_search_parses_jobs(self):
        payload = {"jobs": [load_sample_offers()[0].model_dump(mode="json")], "recruiters": [], "warnings": []}
        client, session = make_client(payload)
        offers = client.search({"romes": "M1805"})
        assert len(offers) == 1
        assert offers[0].offer.title
        session.request.assert_called_once()
        args, kwargs = session.request.call_args
        assert kwargs["params"] == {"romes": "M1805"}

    def test_get_offer(self):
        offer = load_sample_offers()[0]
        client, session = make_client(offer.model_dump(mode="json"))
        detail = client.get_offer(offer.id)
        assert detail.id == offer.id

    def test_search_empty_jobs(self):
        client, _ = make_client({"jobs": [], "recruiters": [], "warnings": []})
        assert client.search({}) == []

    def test_export_parses_list(self):
        offers = load_sample_offers()
        client, _ = make_client({"jobs": [o.model_dump(mode="json") for o in offers]})
        exported = client.export()
        assert len(exported) == len(offers)

    def test_raises_after_retries(self):
        session = MagicMock()
        session.request.side_effect = requests.ConnectionError("boom")
        client = LbaApiClient("https://api.example.org/api", "key", retries=2)
        client.session = session
        with pytest.raises(LbaApiError):
            client.search({})
        assert session.request.call_count == 2

    def test_load_sample_offers(self):
        offers = load_sample_offers()
        assert len(offers) > 0
        assert all(o.offer.title for o in offers)
