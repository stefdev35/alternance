"""Scraper des offres d'emploi Indeed (https://fr.indeed.com).

Ce module parse les pages HTML de recherche et de détail d'Indeed afin de
récupérer les annonces en alternance.

⚠️ Restrictions et limites
--------------------------
- Le `robots.txt` d'Indeed **interdit** l'accès automatique aux pages de
  résultats (`/emploi/`, `/jobs`) et de détail (`/viewjob`).
- Indeed protège son site par un anti-bot (HTTP 403 « Security Check ») :
  les requêtes HTTP simples sont bloquées.
- Dans ce projet, le scraper est fourni à titre d'illustration : son
  parsing est couvert par des tests sur des fixtures représentatives de la
  structure HTML d'Indeed, mais **son exécution en direct peut être bloquée**
  et peut violer les CGU du site.

Le scraper est conçu pour être poli : délai entre requêtes, limite de pages,
et User-Agent réaliste.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://fr.indeed.com"
SEARCH_URL = f"{BASE_URL}/emplois"
VIEWJOB_URL = f"{BASE_URL}/viewjob"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# Délai (s) entre deux requêtes, pour rester raisonnable.
REQUEST_DELAY = 1.0


@dataclass
class IndeedJob:
    """Offre issue de la page de résultats de recherche."""

    job_key: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    date_text: Optional[str] = None
    snippet: Optional[str] = None

    @property
    def url(self) -> str:
        return f"{VIEWJOB_URL}?jk={self.job_key}"


@dataclass
class IndeedJobDetail:
    """Fiche complète issue de la page de détail (viewjob)."""

    job_key: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    contract_types: list[str] = field(default_factory=list)
    remote: Optional[str] = None
    salary: Optional[str] = None
    date_text: Optional[str] = None


class IndeedScraper:
    """Client de scraping minimal pour Indeed."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = 30,
        delay: float = REQUEST_DELAY,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _get(self, url: str, params: Optional[dict] = None) -> str:
        """GET et retourne le HTML. Ajoute un délai par politesse."""
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        time.sleep(self.delay)
        return response.text

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        location: str = "",
        max_pages: int = 1,
        results_per_page: int = 10,
    ) -> list[IndeedJob]:
        """Récupère les offres des pages de résultats.

        Pagination Indeed : paramètre `start` (0, 10, 20, …).
        """
        jobs: list[IndeedJob] = []
        for page in range(max_pages):
            start = page * results_per_page
            html = self._get(
                f"{self.base_url}/emplois",
                params={"q": query, "l": location, "start": start},
            )
            page_jobs = parse_search_results(html)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
        return jobs

    # ------------------------------------------------------------------
    # Détail
    # ------------------------------------------------------------------
    def get_job(self, job_key: str) -> Optional[IndeedJobDetail]:
        """Récupère le détail complet d'une offre via sa fiche."""
        html = self._get(f"{self.base_url}/viewjob", params={"jk": job_key})
        return parse_job_detail(html, job_key)


# ----------------------------------------------------------------------
# Parsing (fonctions pures, testables sur fixtures)
# ----------------------------------------------------------------------
def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def parse_search_results(html: str) -> list[IndeedJob]:
    """Parse la page de résultats et retourne la liste des offres.

    Structure ciblée (markup Indeed) :
    - conteneur d'offre : `.job_seen_beacon` ou `[data-jk]`
    - clé d'offre     : attribut `data-jk`
    - titre           : `h2.jobTitle span[title]` ou `a[data-jk] span`
    - entreprise      : `span.companyName` ou `[data-testid="company-name"]`
    - localisation    : `div[data-testid="text-location"]`
    - salaire         : `.salary-snippet-container span.attribute_snippet`
    - date            : `span.date`
    - extrait         : `div.job-snippet`
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[IndeedJob] = []

    containers = soup.select(".job_seen_beacon, [data-jk]")
    seen: set[str] = set()

    for container in containers:
        job_key = container.get("data-jk")
        if not job_key or job_key in seen:
            continue
        seen.add(job_key)

        title = _text(container.select_one("h2.jobTitle span[title]"))
        if not title:
            title = _text(container.select_one("h2.jobTitle"))
        if not title:
            title = _text(container.select_one("a[data-jk] span"))

        company = _text(container.select_one("span.companyName"))
        if not company:
            company = _text(container.select_one('[data-testid="company-name"]'))

        location = _text(container.select_one('[data-testid="text-location"]'))
        salary = _text(container.select_one(".salary-snippet-container span.attribute_snippet"))
        date_text = _text(container.select_one("span.date"))
        snippet = _text(container.select_one("div.job-snippet"))

        jobs.append(
            IndeedJob(
                job_key=job_key,
                title=title,
                company=company or None,
                location=location or None,
                salary=salary or None,
                date_text=date_text or None,
                snippet=snippet or None,
            )
        )
    return jobs


def parse_job_detail(html: str, job_key: str) -> IndeedJobDetail:
    """Parse la page de détail d'une offre (viewjob)."""
    soup = BeautifulSoup(html, "html.parser")

    title = _text(soup.select_one("h1[data-testid='jobsearch-JobInfoHeader-title']"))
    if not title:
        title = _text(soup.select_one("h1"))
    company = _text(soup.select_one('[data-testid="inlineHeader-companyName"]'))
    location = _text(soup.select_one('[data-testid="jobsearch-CompanyLocation"]'))

    description = _text(soup.select_one("#jobDescriptionText"))
    if not description:
        description = _text(soup.select_one('[data-testid="jobsearch-JobComponent-description"]'))

    # Type de contrat / modalité : libellés présents près de l'en-tête.
    contract_types: list[str] = []
    remote: Optional[str] = None
    salary: Optional[str] = None

    # Bloc d'informations compact (type de contrat, télétravail, salaire…).
    for node in soup.select('[data-testid="jobsearch-JobInfoHeader-compact"] [data-testid]'):
        label = node.get("data-testid", "")
        value = _text(node)
        if not value:
            continue
        if "jobsupportedtypemobile" in label or "jobtypes" in label:
            contract_types.extend(_split_contract_types(value))
        if "remotelocation" in label.lower():
            remote = normalize_remote(value)
        if "salary" in label.lower() or "salaryinfo" in label:
            salary = value

    # Descriptif : mention du type de contrat en préambule (ex. "Alternance").
    if not contract_types and description:
        contract_types = _contract_types_from_text(description[:500])

    date_text = _text(soup.select_one('[data-testid="jobsearch-JobInfoHeader-apply"] ~ div span'))
    if not date_text:
        date_text = _text(soup.select_one("span.date"))

    return IndeedJobDetail(
        job_key=job_key,
        title=title or None,
        company=company or None,
        location=location or None,
        description=description or None,
        contract_types=contract_types,
        remote=remote,
        salary=salary or None,
        date_text=date_text or None,
    )


# ----------------------------------------------------------------------
# Normalisation bas niveau (réutilisée par normalize.py)
# ----------------------------------------------------------------------
CONTRACT_KEYWORDS = {
    "apprentissage": "Apprentissage",
    "alternance": "Apprentissage",
    "professionnalisation": "Professionnalisation",
    "contrat pro": "Professionnalisation",
    "contrat de professionnalisation": "Professionnalisation",
}

REMOTE_MAP = {
    "hybride": "hybrid",
    "hybrid": "hybrid",
    "télétravail": "remote",
    "remote": "remote",
    "à distance": "remote",
    "sur site": "onsite",
    "présentiel": "onsite",
    "en présentiel": "onsite",
}

DATE_PATTERNS = [
    # "Aujourd'hui", "Hier"
    (re.compile(r"aujourd[’']hui", re.I), 0),
    (re.compile(r"hier", re.I), 1),
    # "Il y a 3 jours" / "il y a 30+ jours"
    (re.compile(r"il y a (\d+)\s*\+?\s*jours?", re.I), None),
    (re.compile(r"publi[ée]e? il y a (\d+)\s*jours?", re.I), None),
    # "Depuis 3 jours"
    (re.compile(r"depuis (\d+)\s*jours?", re.I), None),
    # "Il y a 2 semaines"
    (re.compile(r"il y a (\d+)\s*mois?", re.I), None),
    (re.compile(r"il y a (\d+)\s*semaines?", re.I), None),
]


def _split_contract_types(value: str) -> list[str]:
    """Découpe un libellé comme 'Apprentissage, CDI' et mappe vers l'enum LBA."""
    result: list[str] = []
    for token in value.lower().replace("/", ",").split(","):
        token = token.strip()
        for keyword, mapped in CONTRACT_KEYWORDS.items():
            if keyword in token:
                if mapped not in result:
                    result.append(mapped)
                break
    return result


def _contract_types_from_text(text: str) -> list[str]:
    """Détecte les types de contrat dans le début de la description."""
    return _split_contract_types(text[:500])


def normalize_remote(value: str) -> Optional[str]:
    """Mappe un libellé de localisation/télétravail vers l'enum LBA."""
    value = value.strip().lower()
    for keyword, mapped in REMOTE_MAP.items():
        if keyword in value:
            return mapped
    return None


def parse_date_text(date_text: str, now=None) -> Optional[str]:
    """Convertit une date relative Indeed en date ISO (YYYY-MM-DD).

    Renvoie None si le format n'est pas reconnu.
    """
    if not date_text:
        return None
    from datetime import datetime, timedelta

    now = now or datetime.now()
    for pattern, days in DATE_PATTERNS:
        match = pattern.search(date_text)
        if not match:
            continue
        if days is not None:
            days_offset = days
        else:
            days_offset = int(match.group(1))
        date = now - timedelta(days=days_offset)
        return date.date().isoformat()
    return None
