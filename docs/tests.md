# Tests

La suite de tests couvre : les modèles, le client API (HTTP mocké), les deux stockages
(DuckDB et MongoDB), le pipeline d'ingestion et l'application web.

## Lancer les tests

```bash
uv run pytest
```

Avec plus de détails :

```bash
uv run pytest -v
```

## Configuration

- Déclaré dans `pyproject.toml` (`[tool.pytest.ini_options]`) :
  - `testpaths = ["tests"]`
  - `pythonpath = ["src"]`
- Dépendances de dev : `pytest`, `httpx` (requis par `fastapi.testclient`).
- Ajout : `uv add --dev pytest httpx`

## Prérequis

Les tests **DuckDB** et **web** sont isolés (base DuckDB temporaire dans `tmp_path`) et ne
nécessitent aucun service externe.

Les tests **MongoDB** nécessitent un serveur MongoDB joignable. Ils sont **ignorés
automatiquement** si MongoDB n'est pas disponible :

```bash
docker compose up -d   # démarre MongoDB
uv run pytest          # inclut désormais les tests Mongo
```

## Couverture par fichier

| Fichier | Ce qui est testé |
|---|---|
| `test_models.py` | Parsing Pydantic de la structure `JobOfferRead`, fallback de l'identifiant, aller-retour JSON |
| `test_lba_api.py` | Client HTTP : header d'auth, parsing des réponses, retries, erreurs, mode mock |
| `test_indeed.py` | Scraper Indeed : parsing recherche + détail (fixtures HTML), dates relatives, blocage anti-bot |
| `test_normalize.py` | Normalisation Indeed → `JobOffer` : compatibilité avec le schéma LBA, mapping contrat/remote, stockage |
| `test_duckdb_store.py` | Upsert (idempotent), lecture/reconstruction, filtrage par titre/ville/compétence/diplôme, facettes, inconnu |
| `test_mongo_store.py` | Idem pour le stockage documentaire (ignoré si Mongo absent) |
| `test_ingest.py` | Pipeline d'ingestion : sources LBA/Indeed, limite `max_offers` |
| `test_web.py` | Routes FastAPI : santé, liste, détail HTML/JSON, filtres, 404, backend Mongo |

## Notes

- Les listes (compétences, ROME…) sont comparées **sans tenir compte de l'ordre** dans
  DuckDB : le stockage relationnel ne préserve pas l'ordre des listes.
- Le test web backend Mongo est conditionné par `skipif` sur la disponibilité de MongoDB.
