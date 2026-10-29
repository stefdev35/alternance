"""Stockage documentaire des offres dans MongoDB.

Approche NoSQL : chaque offre est stockée telle quelle (JSON imbriqué
complet) dans une collection, avec _id = identifiant de l'offre.
"""

from __future__ import annotations

from typing import Optional

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from ..config import settings
from ..models import JobOffer

COLLECTION = "job_offers"


class MongoStore:
    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        self.uri = uri or settings.mongo_uri
        self.db_name = db_name or settings.mongo_db
        self.client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[self.db_name]
        self.collection = self.db[COLLECTION]
        if self.is_available():
            self.collection.create_index("identifier.partner_job_id")

    def is_available(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except ConnectionFailure:
            return False

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def upsert_offer(self, offer: JobOffer) -> None:
        offer_id = offer.id
        assert offer_id, "L'offre doit avoir un identifiant."
        doc = offer.model_dump(mode="json")
        doc["_id"] = offer_id
        self.collection.replace_one({"_id": offer_id}, doc, upsert=True)

    def upsert_many(self, offers: list[JobOffer]) -> int:
        if not offers:
            return 0
        docs = []
        for offer in offers:
            assert offer.id, "L'offre doit avoir un identifiant."
            doc = offer.model_dump(mode="json")
            doc["_id"] = offer.id
            docs.append(doc)
        result = self.collection.bulk_write(
            [
                pymongo_replace_one(doc)
                for doc in docs
            ],
            ordered=False,
        )
        return result.upserted_count + result.modified_count

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def get_offer(self, offer_id: str) -> Optional[dict]:
        doc = self.collection.find_one({"_id": offer_id})
        if doc is not None and "_id" in doc:
            doc["identifier"] = doc.get("identifier", {})
            if "id" not in doc["identifier"] or doc["identifier"]["id"] is None:
                doc["identifier"]["id"] = doc["_id"]
        return doc

    def list_offers(self, limit: int = 50, offset: int = 0,
                    title: Optional[str] = None) -> list[dict]:
        query = {}
        if title:
            query["offer.title"] = {"$regex": title, "$options": "i"}
        cursor = (
            self.collection.find(query)
            .sort("offer.publication.creation", -1)
            .skip(offset)
            .limit(limit)
        )
        # Aplatit la forme pour correspondre au schéma "liste" de DuckDB.
        return [self._to_list_shape(doc) for doc in cursor]

    def _to_list_shape(self, doc: dict) -> dict:
        offer = doc.get("offer") or {}
        identifier = doc.get("identifier") or {}
        workplace = doc.get("workplace")
        return {
            "id": doc.get("_id"),
            "partner_label": identifier.get("partner_label"),
            "title": offer.get("title"),
            "status": offer.get("status"),
            "opening_count": offer.get("opening_count"),
            "publication_creation": (offer.get("publication") or {}).get("creation"),
            "workplace": workplace,
            "offer": offer,
        }

    def count_offers(self) -> int:
        return self.collection.count_documents({})

    def _clean(self, doc: dict) -> dict:
        doc = dict(doc)
        if "_id" in doc:
            identifier = doc.get("identifier") or {}
            doc["identifier"] = {**identifier, "id": doc["_id"]}
        return doc

    def close(self) -> None:
        self.client.close()


def pymongo_replace_one(doc: dict):
    from pymongo import ReplaceOne

    return ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
