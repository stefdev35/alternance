import pytest

from alternance.lba_api import load_sample_offers
from alternance.models import JobOffer


@pytest.fixture(scope="session")
def sample_offers() -> list[JobOffer]:
    """Échantillon mock des offres, utilisé par tous les tests."""
    return load_sample_offers()


@pytest.fixture()
def sample_offer(sample_offers) -> JobOffer:
    return sample_offers[0]
