"""Application web FastAPI : consultation des offres d'alternance
stockées dans DuckDB (relationnel) ou MongoDB (documentaire).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..storage.duckdb_store import DuckDBStore
from ..storage.mongo_store import MongoStore

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="Alternance — Consultation des offres")


def _get_store(backend: str):
    if backend == "duckdb":
        return DuckDBStore()
    if backend == "mongo":
        return MongoStore()
    raise HTTPException(status_code=400, detail=f"Backend inconnu : {backend}")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, backend: str = Query("duckdb"),
          title: Optional[str] = Query(None), limit: int = Query(50, le=500)):
    store = _get_store(backend)
    offers = store.list_offers(limit=limit, title=title)
    total = store.count_offers()
    store.close()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "backend": backend,
            "offers": offers,
            "total": total,
            "title": title,
        },
    )


@app.get("/offers", response_model=list)
def list_offers_json(backend: str = Query("duckdb"),
                     title: Optional[str] = Query(None),
                     limit: int = Query(50, le=500)):
    store = _get_store(backend)
    offers = store.list_offers(limit=limit, title=title)
    store.close()
    return offers


@app.get("/offers/{offer_id}", response_class=HTMLResponse)
def offer_detail(request: Request, offer_id: str, backend: str = Query("duckdb")):
    store = _get_store(backend)
    offer = store.get_offer(offer_id)
    store.close()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return templates.TemplateResponse(
        request,
        "detail.html",
        {"backend": backend, "offer": offer},
    )


@app.get("/offers/{offer_id}/json")
def offer_detail_json(offer_id: str, backend: str = Query("duckdb")):
    store = _get_store(backend)
    offer = store.get_offer(offer_id)
    store.close()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return offer


@app.get("/health")
def health():
    duck = DuckDBStore()
    duck_ok = True
    duck.close()

    mongo = MongoStore()
    mongo_ok = mongo.is_available()
    mongo.close()

    return {"duckdb": duck_ok, "mongo": mongo_ok}
