"""Pipeline d'ingestion : récupère les offres depuis plusieurs sources
(LBA / Indeed) et les écrit dans DuckDB et MongoDB.

Toutes les sources sont normalisées vers le modèle commun `JobOffer`
avant écriture, ce qui garantit la compatibilité entre elles.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import settings
from .lba_api import LbaApiClient, fetch_offers
from .models import JobOffer
from .scrapers.indeed import IndeedScraper
from .scrapers.normalize import enrich_with_detail, search_result_to_joboffer
from .storage.duckdb_store import DuckDBStore
from .storage.mongo_store import MongoStore

VALID_SOURCES = ("lba", "indeed", "both")


def fetch_lba_offers(use_api: bool | None = None) -> list[JobOffer]:
    """Offres issues de l'API La Bonne Alternance (ou mock)."""
    return fetch_offers(use_mock_if_no_key=(use_api is not True))


def fetch_indeed_offers(
    query: str = "alternance",
    location: str = "",
    max_pages: int = 1,
    fetch_details: bool = False,
) -> list[JobOffer]:
    """Offres scrapées sur Indeed, normalisées vers JobOffer.

    En direct, Indeed bloque souvent les requêtes (anti-bot / 403) et
    interdit le scraping dans robots.txt. Cette fonction est donc
    principalement utilisée via les fixtures de test, ou ponctuellement
    en direct si l'accès est disponible.
    """
    scraper = IndeedScraper()
    jobs = scraper.search(query=query, location=location, max_pages=max_pages)
    offers: list[JobOffer] = []
    for job in jobs:
        if fetch_details:
            detail = scraper.get_job(job.job_key)
            offers.append(
                enrich_with_detail(job, detail) if detail else search_result_to_joboffer(job)
            )
        else:
            offers.append(search_result_to_joboffer(job))
    return offers


def get_source_offers(
    source: str = "lba",
    use_api: bool | None = None,
    max_offers: Optional[int] = None,
    indeed_query: str = "alternance",
    indeed_fetch_details: bool = False,
) -> list[JobOffer]:
    """Récupère les offres normalisées de la source demandée."""
    if source in ("lba", "both"):
        offers = fetch_lba_offers(use_api)
    else:
        offers = []

    if source in ("indeed", "both"):
        indeed_offers = fetch_indeed_offers(
            query=indeed_query,
            fetch_details=indeed_fetch_details,
        )
        offers.extend(indeed_offers)

    if max_offers:
        offers = offers[:max_offers]
    return offers


def ingest(
    source: str = "lba",
    use_api: bool | None = None,
    max_offers: Optional[int] = None,
    indeed_query: str = "alternance",
    indeed_fetch_details: bool = False,
) -> dict:
    """Ingère les offres dans les deux bases. Retourne un rapport."""
    offers = get_source_offers(
        source=source,
        use_api=use_api,
        max_offers=max_offers,
        indeed_query=indeed_query,
        indeed_fetch_details=indeed_fetch_details,
    )

    print(f"→ {len(offers)} offres à ingérer (source : {source})")

    duck = DuckDBStore()
    duck_count = duck.upsert_many(offers)
    duck_total = duck.count_offers()
    duck.close()
    print(f"✅ DuckDB  : {duck_count} insérées/mises à jour (total : {duck_total})")

    mongo = MongoStore()
    if mongo.is_available():
        mongo_count = mongo.upsert_many(offers)
        mongo_total = mongo.count_offers()
        mongo.close()
        print(f"✅ MongoDB : {mongo_count} insérées/mises à jour (total : {mongo_total})")
    else:
        print(
            "⚠️ MongoDB indisponible. Lancez 'docker compose up -d' "
            "puis relancez l'ingestion."
        )
        mongo_total = 0

    return {
        "source": source,
        "offers_ingested": len(offers),
        "duckdb_total": duck_total,
        "mongo_total": mongo_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestion des offres d'alternance (sources : LBA, Indeed)"
    )
    parser.add_argument(
        "--source",
        choices=VALID_SOURCES,
        default="lba",
        help="Source des offres : lba (API La Bonne Alternance), indeed, ou both",
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="Forcer l'appel à l'API LBA (nécessite LBA_API_KEY)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Limiter le nombre d'offres ingérées",
    )
    parser.add_argument(
        "--indeed-query",
        default="alternance",
        help="Requête de recherche Indeed (défaut : alternance)",
    )
    parser.add_argument(
        "--indeed-details",
        action="store_true",
        help="Récupérer aussi les fiches détaillées Indeed (viewjob)",
    )
    args = parser.parse_args()

    report = ingest(
        source=args.source,
        use_api=args.use_api or None,
        max_offers=args.max,
        indeed_query=args.indeed_query,
        indeed_fetch_details=args.indeed_details,
    )
    print(f"\nTerminé : {report['offers_ingested']} offres ingérées.")
    sys.exit(0)


if __name__ == "__main__":
    main()
