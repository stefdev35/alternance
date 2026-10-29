"""Pipeline d'ingestion : récupère les offres (API ou mock) et les
écrit dans DuckDB et MongoDB.
"""

from __future__ import annotations

import argparse
import sys

from .config import settings
from .lba_api import LbaApiClient, fetch_offers
from .models import JobOffer
from .storage.duckdb_store import DuckDBStore
from .storage.mongo_store import MongoStore


def ingest(use_api: bool | None = None, max_offers: int | None = None) -> dict:
    """Ingère les offres dans les deux bases. Retourne un rapport."""
    offers = fetch_offers(use_mock_if_no_key=(use_api is not True))
    if max_offers:
        offers = offers[:max_offers]

    print(f"→ {len(offers)} offres à ingérer")

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
        "offers_ingested": len(offers),
        "duckdb_total": duck_total,
        "mongo_total": mongo_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion des offres d'alternance")
    parser.add_argument("--use-api", action="store_true",
                        help="Forcer l'appel à l'API (nécessite LBA_API_KEY)")
    parser.add_argument("--max", type=int, default=None,
                        help="Limiter le nombre d'offres ingérées")
    args = parser.parse_args()

    report = ingest(use_api=args.use_api or None, max_offers=args.max)
    print(f"\nTerminé : {report['offers_ingested']} offres ingérées.")
    sys.exit(0)


if __name__ == "__main__":
    main()
