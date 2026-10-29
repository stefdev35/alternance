"""Tests des modèles Pydantic (structure JobOfferRead de l'API LBA)."""

import json

from alternance.models import JobOffer


class TestJobOfferModel:
    def test_parse_sample(self, sample_offer: JobOffer):
        assert isinstance(sample_offer, JobOffer)
        assert sample_offer.offer.title
        assert sample_offer.identifier.partner_job_id

    def test_id_property_falls_back_to_partner_job_id(self, sample_offers):
        # Une offre sans identifier.id doit retomber sur partner_job_id.
        data = sample_offers[0].model_dump()
        data["identifier"]["id"] = None
        offer = JobOffer.model_validate(data)
        assert offer.id == offer.identifier.partner_job_id

    def test_full_roundtrip(self, sample_offer: JobOffer):
        data = sample_offer.model_dump(mode="json")
        reparse = JobOffer.model_validate(data)
        assert reparse == sample_offer

    def test_serialize_roundtrip_matches_source_json(self, sample_offers):
        """Chaque offre de l'échantillon doit pouvoir être revalidée."""
        for offer in sample_offers:
            assert JobOffer.model_validate(offer.model_dump(mode="json")) == offer
