"""Tests du scraper Indeed (parsing des fixtures HTML)."""

from pathlib import Path

import pytest

from alternance.scrapers.indeed import (
    IndeedScraper,
    parse_date_text,
    parse_job_detail,
    parse_search_results,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestParseSearchResults:
    def test_extracts_jobs(self):
        jobs = parse_search_results(_load("indeed_search.html"))
        assert len(jobs) == 2

    def test_first_job_fields(self):
        jobs = parse_search_results(_load("indeed_search.html"))
        job = jobs[0]
        assert job.job_key == "abc123def"
        assert job.title == "Développeur / Développeuse Python en alternance"
        assert job.company == "TechCorp Solutions"
        assert job.location == "Lyon (69)"
        assert job.salary == "25 000 € - 30 000 € par an"
        assert job.date_text == "Il y a 3 jours"
        assert "Python" in (job.snippet or "")
        assert job.url == "https://fr.indeed.com/viewjob?jk=abc123def"

    def test_second_job(self):
        jobs = parse_search_results(_load("indeed_search.html"))
        job = jobs[1]
        assert job.job_key == "xyz789ghi"
        assert job.company == "DataSquad"
        assert job.date_text == "Aujourd'hui"

    def test_empty_html(self):
        assert parse_search_results("<html></html>") == []


class TestParseJobDetail:
    def test_extracts_fields(self):
        detail = parse_job_detail(_load("indeed_viewjob.html"), "abc123def")
        assert detail.job_key == "abc123def"
        assert detail.title == "Développeur / Développeuse Python en alternance"
        assert detail.company == "TechCorp Solutions"
        assert detail.location == "Lyon (69)"
        assert "FastAPI" in (detail.description or "")
        assert detail.contract_types == ["Apprentissage"]
        assert detail.remote == "hybrid"
        assert detail.salary == "25 000 € - 30 000 € par an"


class TestParseDateText:
    def test_today(self):
        assert parse_date_text("Aujourd'hui") is not None

    def test_yesterday(self):
        assert parse_date_text("Hier") is not None

    def test_days_ago(self):
        assert parse_date_text("Il y a 3 jours") is not None

    def test_unknown(self):
        assert parse_date_text("Date inconnue") is None


class TestIndeedScraper:
    def test_parse_search_page_offline(self):
        """Le parsing de fixture ne nécessite aucun réseau."""
        html = _load("indeed_search.html")
        jobs = parse_search_results(html)
        assert jobs

    def test_parse_detail_offline(self):
        html = _load("indeed_viewjob.html")
        detail = parse_job_detail(html, "abc123def")
        assert detail.title

    def test_live_request_blocked(self):
        """En direct, Indeed renvoie 403 (anti-bot) — le scraper doit lever une erreur."""
        import requests

        scraper = IndeedScraper(timeout=10)
        with pytest.raises(requests.RequestException):
            scraper.search("developpeur", max_pages=1)
