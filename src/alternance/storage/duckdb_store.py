"""Stockage relationnel des offres dans DuckDB.

Schéma normalisé (clés primaires / étrangères) pour illustrer l'approche
relationnelle : une offre est répartie dans plusieurs tables liées par
l'identifiant de l'offre.
"""

from __future__ import annotations

from typing import Optional

import duckdb

from ..config import settings
from ..models import JobOffer

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS offers (
    id                VARCHAR PRIMARY KEY,
    partner_job_id    VARCHAR NOT NULL,
    partner_label     VARCHAR NOT NULL,
    title             VARCHAR NOT NULL,
    description       VARCHAR,
    status            VARCHAR,
    opening_count     INTEGER,
    is_delegated      BOOLEAN,
    target_diploma_european VARCHAR,
    target_diploma_label    VARCHAR,
    publication_creation    TIMESTAMP,
    publication_expiration  TIMESTAMP,
    created_at        TIMESTAMP DEFAULT current_timestamp,
    updated_at        TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS contract_types (
    offer_id    VARCHAR NOT NULL REFERENCES offers(id),
    type        VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS contracts (
    offer_id         VARCHAR PRIMARY KEY REFERENCES offers(id),
    start            TIMESTAMP,
    start_type       VARCHAR,
    start_is_flexible BOOLEAN,
    duration         INTEGER,
    remote           VARCHAR
);

CREATE TABLE IF NOT EXISTS workplaces (
    offer_id    VARCHAR PRIMARY KEY REFERENCES offers(id),
    name        VARCHAR,
    description VARCHAR,
    website     VARCHAR,
    siret       VARCHAR,
    brand       VARCHAR,
    legal_name  VARCHAR,
    size        VARCHAR,
    address     VARCHAR,
    latitude    DOUBLE,
    longitude   DOUBLE,
    naf_code    VARCHAR,
    naf_label   VARCHAR,
    idcc        INTEGER,
    opco        VARCHAR
);

CREATE TABLE IF NOT EXISTS apply (
    offer_id     VARCHAR PRIMARY KEY REFERENCES offers(id),
    phone        VARCHAR,
    url          VARCHAR,
    recipient_id VARCHAR
);

CREATE TABLE IF NOT EXISTS skills (
    offer_id VARCHAR NOT NULL REFERENCES offers(id),
    kind     VARCHAR NOT NULL,
    skill    VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS rome_codes (
    offer_id VARCHAR NOT NULL REFERENCES offers(id),
    code     VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS to_applicant_questions (
    offer_id VARCHAR NOT NULL REFERENCES offers(id),
    question VARCHAR NOT NULL
);
"""


class DuckDBStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(settings.duckdb_file if db_path is None else db_path)
        self.conn = duckdb.connect(self.db_path)
        self.conn.execute(SCHEMA_SQL)

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def upsert_offer(self, offer: JobOffer) -> None:
        offer_id = offer.id
        assert offer_id, "L'offre doit avoir un identifiant."

        wp = offer.workplace
        loc = wp.location if wp else None
        geo = loc.geopoint.coordinates if loc and loc.geopoint else None
        dom = wp.domain if wp else None
        naf = dom.naf if dom else None
        pub = offer.offer.publication

        self.conn.execute(
            """
            INSERT INTO offers (
                id, partner_job_id, partner_label, title, description, status,
                opening_count, is_delegated, target_diploma_european,
                target_diploma_label, publication_creation, publication_expiration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                partner_job_id = excluded.partner_job_id,
                partner_label  = excluded.partner_label,
                title          = excluded.title,
                description    = excluded.description,
                status         = excluded.status,
                opening_count  = excluded.opening_count,
                is_delegated   = excluded.is_delegated,
                target_diploma_european = excluded.target_diploma_european,
                target_diploma_label    = excluded.target_diploma_label,
                publication_creation    = excluded.publication_creation,
                publication_expiration  = excluded.publication_expiration,
                updated_at     = (now())
            """,
            [
                offer_id,
                offer.identifier.partner_job_id,
                offer.identifier.partner_label,
                offer.offer.title,
                offer.offer.description,
                offer.offer.status,
                offer.offer.opening_count,
                offer.is_delegated,
                offer.offer.target_diploma.european if offer.offer.target_diploma else None,
                offer.offer.target_diploma.label if offer.offer.target_diploma else None,
                pub.creation if pub else None,
                pub.expiration if pub else None,
            ],
        )

        self.conn.execute("DELETE FROM contract_types WHERE offer_id = ?", [offer_id])
        contract = offer.contract
        if contract:
            self.conn.execute(
                """
                INSERT INTO contracts (offer_id, start, start_type,
                    start_is_flexible, duration, remote)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (offer_id) DO UPDATE SET
                    start = excluded.start, start_type = excluded.start_type,
                    start_is_flexible = excluded.start_is_flexible,
                    duration = excluded.duration, remote = excluded.remote
                """,
                [offer_id, contract.start, contract.start_type,
                 contract.start_is_flexible, contract.duration, contract.remote],
            )
            for ctype in contract.type:
                self.conn.execute(
                    "INSERT INTO contract_types (offer_id, type) VALUES (?, ?)",
                    [offer_id, ctype],
                )

        self.conn.execute(
            """
            INSERT INTO workplaces (offer_id, name, description, website, siret,
                brand, legal_name, size, address, latitude, longitude,
                naf_code, naf_label, idcc, opco)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (offer_id) DO UPDATE SET
                name = excluded.name, description = excluded.description,
                website = excluded.website, siret = excluded.siret,
                brand = excluded.brand, legal_name = excluded.legal_name,
                size = excluded.size, address = excluded.address,
                latitude = excluded.latitude, longitude = excluded.longitude,
                naf_code = excluded.naf_code, naf_label = excluded.naf_label,
                idcc = excluded.idcc, opco = excluded.opco
            """,
            [
                offer_id,
                wp.name if wp else None,
                wp.description if wp else None,
                wp.website if wp else None,
                wp.siret if wp else None,
                wp.brand if wp else None,
                wp.legal_name if wp else None,
                wp.size if wp else None,
                loc.address if loc else None,
                geo[1] if geo else None,
                geo[0] if geo else None,
                naf.code if naf else None,
                naf.label if naf else None,
                dom.idcc if dom else None,
                dom.opco if dom else None,
            ],
        )

        self.conn.execute("DELETE FROM apply WHERE offer_id = ?", [offer_id])
        ap = offer.apply
        if ap:
            self.conn.execute(
                "INSERT INTO apply (offer_id, phone, url, recipient_id) VALUES (?, ?, ?, ?)",
                [offer_id, ap.phone, ap.url, ap.recipient_id],
            )

        self.conn.execute("DELETE FROM skills WHERE offer_id = ?", [offer_id])
        self.conn.execute("DELETE FROM rome_codes WHERE offer_id = ?", [offer_id])
        self.conn.execute("DELETE FROM to_applicant_questions WHERE offer_id = ?", [offer_id])

        for kind, values in (
            ("desired", offer.offer.desired_skills),
            ("acquired", offer.offer.to_be_acquired_skills),
            ("access", offer.offer.access_conditions),
        ):
            for skill in values:
                self.conn.execute(
                    "INSERT INTO skills (offer_id, kind, skill) VALUES (?, ?, ?)",
                    [offer_id, kind, skill],
                )
        for code in offer.offer.rome_codes:
            self.conn.execute(
                "INSERT INTO rome_codes (offer_id, code) VALUES (?, ?)",
                [offer_id, code],
            )
        for q in offer.offer.to_applicant_questions or []:
            self.conn.execute(
                "INSERT INTO to_applicant_questions (offer_id, question) VALUES (?, ?)",
                [offer_id, q],
            )

    def upsert_many(self, offers: list[JobOffer]) -> int:
        count = 0
        for offer in offers:
            self.upsert_offer(offer)
            count += 1
        self.conn.commit()
        return count

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def _rows(self, sql: str, params: list = None) -> list[dict]:
        cur = self.conn.execute(sql, params or [])
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def _fetch_nested(self, offer_id: str) -> dict:
        """Reconstruit la structure imbriquée d'une offre depuis les tables."""
        row = self._rows("SELECT * FROM offers WHERE id = ?", [offer_id])
        if not row:
            return {}
        row = row[0]
        nested = {
            "identifier": {
                "partner_job_id": row["partner_job_id"],
                "id": row["id"],
                "partner_label": row["partner_label"],
            },
            "offer": {
                "title": row["title"],
                "description": row["description"],
                "desired_skills": self._skills(offer_id, "desired"),
                "to_be_acquired_skills": self._skills(offer_id, "acquired"),
                "access_conditions": self._skills(offer_id, "access"),
                "opening_count": row["opening_count"],
                "publication": {
                    "creation": row["publication_creation"],
                    "expiration": row["publication_expiration"],
                },
                "rome_codes": self._rome_codes(offer_id),
                "target_diploma": {
                    "european": row["target_diploma_european"],
                    "label": row["target_diploma_label"],
                },
                "status": row["status"],
                "to_applicant_questions": self._questions(offer_id),
            },
            "is_delegated": row["is_delegated"],
        }
        contracts = self._rows("SELECT * FROM contracts WHERE offer_id = ?", [offer_id])
        if contracts:
            c = contracts[0]
            ctypes = self._rows(
                "SELECT type FROM contract_types WHERE offer_id = ? ORDER BY type", [offer_id]
            )
            nested["contract"] = {
                "start": c["start"],
                "start_type": c["start_type"],
                "start_is_flexible": c["start_is_flexible"],
                "duration": c["duration"],
                "remote": c["remote"],
                "type": [x["type"] for x in ctypes],
            }
        workplaces = self._rows("SELECT * FROM workplaces WHERE offer_id = ?", [offer_id])
        if workplaces:
            w = workplaces[0]
            nested["workplace"] = {
                "name": w["name"],
                "description": w["description"],
                "website": w["website"],
                "siret": w["siret"],
                "brand": w["brand"],
                "legal_name": w["legal_name"],
                "size": w["size"],
                "location": {
                    "address": w["address"],
                    "geopoint": {"type": "Point", "coordinates": [w["longitude"], w["latitude"]]}
                    if w["longitude"] is not None
                    else None,
                },
                "domain": {
                    "idcc": w["idcc"],
                    "opco": w["opco"],
                    "naf": {"code": w["naf_code"], "label": w["naf_label"]}
                    if w["naf_code"]
                    else None,
                },
            }
        applies = self._rows("SELECT * FROM apply WHERE offer_id = ?", [offer_id])
        if applies:
            a = applies[0]
            nested["apply"] = {
                "phone": a["phone"],
                "url": a["url"],
                "recipient_id": a["recipient_id"],
            }
        return nested

    def _skills(self, offer_id: str, kind: str) -> list[str]:
        return [
            r["skill"]
            for r in self._rows(
                "SELECT skill FROM skills WHERE offer_id = ? AND kind = ? ORDER BY skill",
                [offer_id, kind],
            )
        ]

    def _rome_codes(self, offer_id: str) -> list[str]:
        return [
            r["code"]
            for r in self._rows(
                "SELECT code FROM rome_codes WHERE offer_id = ? ORDER BY code", [offer_id]
            )
        ]

    def _questions(self, offer_id: str) -> list[str]:
        return [
            r["question"]
            for r in self._rows(
                "SELECT question FROM to_applicant_questions WHERE offer_id = ? ORDER BY question",
                [offer_id],
            )
        ]

    def get_offer(self, offer_id: str) -> Optional[dict]:
        nested = self._fetch_nested(offer_id)
        return nested or None

    @staticmethod
    def _offer_filters(title: Optional[str] = None,
                       city: Optional[str] = None,
                       skill: Optional[str] = None,
                       diploma_level: Optional[str] = None) -> tuple[str, list]:
        """Construit la clause WHERE partagée (liste + comptage)."""
        conditions: list[str] = []
        params: list = []
        if title:
            conditions.append("lower(o.title) LIKE lower(?)")
            params.append(f"%{title}%")
        if city:
            conditions.append("lower(w.address) LIKE lower(?)")
            params.append(f"%{city}%")
        if skill:
            conditions.append(
                "EXISTS (SELECT 1 FROM skills s WHERE s.offer_id = o.id "
                "AND lower(s.skill) LIKE lower(?))"
            )
            params.append(f"%{skill}%")
        if diploma_level:
            conditions.append("o.target_diploma_european = ?")
            params.append(str(diploma_level))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where, params

    def list_offers(self, limit: int = 50, offset: int = 0,
                    title: Optional[str] = None,
                    city: Optional[str] = None,
                    skill: Optional[str] = None,
                    diploma_level: Optional[str] = None) -> list[dict]:
        """Liste les offres avec filtres optionnels.

        - `title`         : correspondance (insensible à la casse) sur le titre
        - `city`          : correspondance sur l'adresse du lieu de travail (ville)
        - `skill`         : correspondance sur les compétences (tous types confondus)
        - `diploma_level` : niveau européen du diplôme visé ("3" à "7")
        """
        where, params = self._offer_filters(
            title=title, city=city, skill=skill, diploma_level=diploma_level
        )
        sql = (
            "SELECT o.id, o.partner_label, o.title, o.status, o.opening_count, "
            "o.publication_creation, w.name AS workplace_name, "
            "w.address AS workplace_address, "
            "o.target_diploma_european, o.target_diploma_label "
            "FROM offers o "
            "LEFT JOIN workplaces w ON w.offer_id = o.id"
            + where
        )
        sql += " ORDER BY o.publication_creation DESC NULLS LAST LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = self._rows(sql, params)
        for row in rows:
            workplace = {
                "name": row.pop("workplace_name", None),
                "location": {"address": row.pop("workplace_address", None)},
            }
            row["workplace"] = workplace
        return rows

    def count_offers(self, title: Optional[str] = None,
                     city: Optional[str] = None,
                     skill: Optional[str] = None,
                     diploma_level: Optional[str] = None) -> int:
        where, params = self._offer_filters(
            title=title, city=city, skill=skill, diploma_level=diploma_level
        )
        sql = (
            "SELECT COUNT(*) AS n FROM offers o "
            "LEFT JOIN workplaces w ON w.offer_id = o.id"
            + where
        )
        return self._rows(sql, params)[0]["n"]

    def distinct_cities(self, limit: int = 200) -> list[str]:
        """Villes disponibles (dérivées des adresses, unique)."""
        rows = self._rows(
            "SELECT DISTINCT address FROM workplaces "
            "WHERE address IS NOT NULL AND address != '' "
            "ORDER BY address LIMIT ?",
            [limit],
        )
        return [r["address"] for r in rows]

    def distinct_skills(self, limit: int = 300) -> list[str]:
        rows = self._rows(
            "SELECT DISTINCT skill FROM skills ORDER BY skill LIMIT ?", [limit]
        )
        return [r["skill"] for r in rows]

    def search_skills(self, prefix: str, limit: int = 10) -> list[str]:
        """Compétences commençant par `prefix` (insensible à la casse).

        Utilisé par l'auto-complétion de l'interface.
        """
        rows = self._rows(
            "SELECT DISTINCT skill FROM skills "
            "WHERE lower(skill) LIKE lower(?) "
            "ORDER BY skill LIMIT ?",
            [f"{prefix}%", limit],
        )
        return [r["skill"] for r in rows]

    def distinct_diploma_levels(self) -> list[dict]:
        rows = self._rows(
            "SELECT DISTINCT target_diploma_european, target_diploma_label "
            "FROM offers WHERE target_diploma_european IS NOT NULL "
            "ORDER BY target_diploma_european"
        )
        return [
            {"level": r["target_diploma_european"], "label": r["target_diploma_label"]}
            for r in rows
        ]

    def close(self) -> None:
        self.conn.close()
