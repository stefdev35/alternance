"""Client de l'API La Bonne Alternance (LBA).

Endpoints utilisés :
- GET /job/v1/search        → liste des offres (JobOfferRead complets)
- GET /job/v1/offer/{id}    → détail d'une offre
- GET /job/v1/export        → export total (limité à 2 appels/min)

Authentification : header "Authorization: Bearer <API_KEY>".
Sans clé API, un mode mock (échantillon local JSON) est utilisé pour
tester la chaîne complète ingestion / consultation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import settings
from .models import JobOffer

SEARCH_URL = "/job/v1/search"
DETAIL_URL = "/job/v1/offer/{id}"
EXPORT_URL = "/job/v1/export"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "alternance-project/0.1",
}

SAMPLE_OFFERS_FILE = Path(__file__).resolve().parent / "samples" / "sample_offers.json"


class LbaApiError(Exception):
    pass


class LbaApiClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 30, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        headers = dict(DEFAULT_HEADERS)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers.update(headers)

    @property
    def authenticated(self) -> bool:
        return bool(self.api_key)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt == self.retries:
                    break
                print(f"   ⚠ tentative {attempt} échouée ({error}), nouvel essai…")
                time.sleep(2 * attempt)
        raise LbaApiError(f"Requête {method} {url} échouée : {last_error}")

    def search(self, params: Optional[dict] = None) -> list[JobOffer]:
        """Recherche des offres. La réponse contient déjà les offres complètes."""
        data = self._request("GET", SEARCH_URL, params=params or {})
        jobs = data.get("jobs", [])
        return [JobOffer.model_validate(job) for job in jobs]

    def get_offer(self, offer_id: str) -> JobOffer:
        """Détail complet d'une offre par identifiant."""
        data = self._request("GET", DETAIL_URL.format(id=offer_id))
        return JobOffer.model_validate(data)

    def export(self) -> list[JobOffer]:
        """Export complet des opportunités (liste d'offres)."""
        data = self._request("GET", EXPORT_URL)
        jobs = data.get("jobs", []) if isinstance(data, dict) else data
        return [JobOffer.model_validate(job) for job in jobs]


def load_sample_offers() -> list[JobOffer]:
    """Charge l'échantillon mock (structure JobOfferRead) en l'absence de clé API."""
    path = Path(SAMPLE_OFFERS_FILE)
    if not path.exists():
        raise LbaApiError(
            "Aucune clé API configurée et aucun échantillon trouvé. "
            "Soit renseignez LBA_API_KEY dans .env, soit créez "
            f"{path.name} (voir README)."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    return [JobOffer.model_validate(job) for job in jobs]


def fetch_offers(use_mock_if_no_key: bool = True) -> list[JobOffer]:
    """Point d'entrée : renvoie les offres depuis l'API ou le mode mock."""
    if settings.has_api_key:
        client = LbaApiClient(settings.lba_api_base_url, settings.lba_api_key)
        return client.search()
    if use_mock_if_no_key:
        return load_sample_offers()
    raise LbaApiError("Aucune clé API configurée.")
