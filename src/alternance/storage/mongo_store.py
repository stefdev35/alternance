"""Stockage documentaire des offres dans MongoDB.

Approche NoSQL : chaque offre est stockée telle quelle (JSON imbriqué
complet) dans une collection, avec _id = identifiant de l'offre.
"""

from __future__ import annotations

import re
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

    @staticmethod
    def _offer_filters(title: Optional[str] = None,
                       city: Optional[str] = None,
                       skill: Optional[str] = None,
                       diploma_level: Optional[str] = None) -> dict:
        """Construit le filtre Mongo partagé (liste + comptage)."""
        query: dict = {}
        if title:
            query["offer.title"] = {"$regex": title, "$options": "i"}
        if city:
            query["workplace.location.address"] = {"$regex": city, "$options": "i"}
        if skill:
            query["$or"] = [
                {"offer.desired_skills": {"$regex": skill, "$options": "i"}},
                {"offer.to_be_acquired_skills": {"$regex": skill, "$options": "i"}},
                {"offer.access_conditions": {"$regex": skill, "$options": "i"}},
            ]
        if diploma_level:
            query["offer.target_diploma.european"] = str(diploma_level)
        return query

    def list_offers(self, limit: int = 50, offset: int = 0,
                    title: Optional[str] = None,
                    city: Optional[str] = None,
                    skill: Optional[str] = None,
                    diploma_level: Optional[str] = None) -> list[dict]:
        query = self._offer_filters(
            title=title, city=city, skill=skill, diploma_level=diploma_level
        )
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
            "target_diploma_european": (offer.get("target_diploma") or {}).get("european"),
            "target_diploma_label": (offer.get("target_diploma") or {}).get("label"),
            "workplace": workplace,
            "offer": offer,
        }

    def count_offers(self, title: Optional[str] = None,
                     city: Optional[str] = None,
                     skill: Optional[str] = None,
                     diploma_level: Optional[str] = None) -> int:
        query = self._offer_filters(
            title=title, city=city, skill=skill, diploma_level=diploma_level
        )
        return self.collection.count_documents(query)

    def distinct_cities(self, limit: int = 200) -> list[str]:
        return self.collection.distinct("workplace.location.address")[:limit]

    def distinct_skills(self, limit: int = 300) -> list[str]:
        skills: list[str] = []
        seen: set[str] = set()
        for field in ("offer.desired_skills", "offer.to_be_acquired_skills",
                      "offer.access_conditions"):
            for value in self.collection.distinct(field):
                if value not in seen:
                    seen.add(value)
                    skills.append(value)
                if len(skills) >= limit:
                    break
        return skills

    def search_skills(self, prefix: str, limit: int = 10) -> list[str]:
        """Compétences commençant par `prefix` (insensible à la casse).

        Agrégation : concaténation des tableaux de compétences, dépliage
        ($unwind) puis correspondance sur le préfixe.
        """
        pipeline = [
            {
                "$project": {
                    "skills": {
                        "$concatArrays": [
                            {"$ifNull": ["$offer.desired_skills", []]},
                            {"$ifNull": ["$offer.to_be_acquired_skills", []]},
                            {"$ifNull": ["$offer.access_conditions", []]},
                        ]
                    }
                }
            },
            {"$unwind": "$skills"},
            {"$match": {"skills": {"$regex": f"^{re.escape(prefix)}", "$options": "i"}}},
            {"$group": {"_id": "$skills"}},
            {"$sort": {"_id": 1}},
            {"$limit": limit},
        ]
        return [doc["_id"] for doc in self.collection.aggregate(pipeline)]

    def distinct_diploma_levels(self) -> list[dict]:
        levels: dict[str, str] = {}
        for doc in self.collection.find(
            {"offer.target_diploma": {"$ne": None}},
            {"offer.target_diploma": 1},
        ):
            td = (doc.get("offer") or {}).get("target_diploma") or {}
            if td.get("european") and td["european"] not in levels:
                levels[td["european"]] = td.get("label")
        return [
            {"level": level, "label": label}
            for level, label in sorted(levels.items())
        ]

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
