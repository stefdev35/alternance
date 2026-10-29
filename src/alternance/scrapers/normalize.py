"""Normalisation des données Indeed vers le schéma commun `JobOffer`.

Le but est de rendre les offres scrapées sur Indeed **compatibles** avec
celles issues de l'API La Bonne Alternance : les deux sources sont
converties vers le même modèle Pydantic `JobOffer` (structure JobOfferRead),
ce qui permet de les stocker et de les interroger de façon homogène dans
DuckDB et MongoDB.
"""

from __future__ import annotations

from typing import Optional

from ..models import (
    Apply,
    Contract,
    Identifier,
    JobOffer,
    Location,
    Offer,
    Publication,
    TargetDiploma,
    Workplace,
)
from .indeed import IndeedJob, IndeedJobDetail, normalize_remote, parse_date_text

PARTNER_LABEL = "Indeed"


# ----------------------------------------------------------------------
# Règles de correspondance Indeed → JobOfferRead
# ----------------------------------------------------------------------
def _make_identifier(job_key: str) -> Identifier:
    return Identifier(
        partner_job_id=job_key,  # clé unique Indeed (data-jk)
        id=None,  # None → `JobOffer.id` retombe sur partner_job_id
        partner_label=PARTNER_LABEL,
    )


def _make_contract(detail: IndeedJobDetail) -> Contract:
    return Contract(
        start=None,
        start_type=None,
        start_is_flexible=None,
        duration=None,
        type=detail.contract_types or [],
        remote=detail.remote,
    )


def _make_workplace(company: Optional[str], location: Optional[str]) -> Optional[Workplace]:
    if not company and not location:
        return None
    return Workplace(
        name=company,
        description=None,
        website=None,
        siret=None,  # Indeed n'expose pas le SIRET dans le HTML public
        location=Location(address=location or "", geopoint=None),
        brand=None,
        legal_name=None,
        size=None,
        domain=None,
    )


def _make_apply(job_key: str, detail: IndeedJobDetail) -> Apply:
    return Apply(
        phone=None,
        url=f"https://fr.indeed.com/viewjob?jk={job_key}",
        recipient_id=None,
    )


def _make_offer(detail: IndeedJobDetail) -> Offer:
    return Offer(
        title=detail.title or "Intitulé inconnu",
        description=detail.description or "",
        desired_skills=[],  # non fourni par Indeed dans le HTML public
        to_be_acquired_skills=[],
        access_conditions=[],
        opening_count=1,
        publication=Publication(
            creation=parse_date_text(detail.date_text or ""),
            expiration=None,
        ),
        rome_codes=[],  # Indeed n'expose pas les codes ROME
        target_diploma=TargetDiploma(european=None, label=None),
        status="Active",
        to_applicant_questions=[],
    )


# ----------------------------------------------------------------------
# API publique
# ----------------------------------------------------------------------
def search_result_to_joboffer(job: IndeedJob) -> JobOffer:
    """Normalise une offre issue de la page de résultats.

    La page de recherche ne contient que peu de champs : on remplit ce qui
    est disponible et le détail (description, contrat…) est complété par
    `detail_to_joboffer`.
    """
    return JobOffer(
        identifier=_make_identifier(job.job_key),
        workplace=_make_workplace(job.company, job.location),
        apply=_make_apply(job.job_key, IndeedJobDetail(job_key=job.job_key)),
        contract=Contract(
            start=None, start_type=None, start_is_flexible=None,
            duration=None, type=[], remote=None,
        ),
        offer=Offer(
            title=job.title,
            description=job.snippet or "",
            desired_skills=[],
            to_be_acquired_skills=[],
            access_conditions=[],
            opening_count=1,
            publication=Publication(
                creation=parse_date_text(job.date_text or ""),
                expiration=None,
            ),
            rome_codes=[],
            target_diploma=TargetDiploma(european=None, label=None),
            status="Active",
            to_applicant_questions=[],
        ),
        is_delegated=False,
    )


def detail_to_joboffer(detail: IndeedJobDetail) -> JobOffer:
    """Normalise une offre issue de la page de détail (source la plus riche)."""
    return JobOffer(
        identifier=_make_identifier(detail.job_key),
        workplace=_make_workplace(detail.company, detail.location),
        apply=_make_apply(detail.job_key, detail),
        contract=_make_contract(detail),
        offer=_make_offer(detail),
        is_delegated=False,
    )


def enrich_with_detail(job: IndeedJob, detail: IndeedJobDetail) -> JobOffer:
    """Combine une offre de recherche avec sa fiche détaillée."""
    normalized = detail_to_joboffer(detail)
    # Complète avec les infos disponibles uniquement dans la liste.
    if not normalized.offer.publication.creation:
        normalized.offer.publication.creation = parse_date_text(job.date_text or "")
    return normalized
