# Guide d'utilisation

## Prérequis

- Python ≥ 3.12 et [uv](https://docs.astral.sh/uv/)
- Docker (pour MongoDB)

## Installation

```bash
uv sync
```

Créez le fichier `.env` à partir du modèle :

```bash
cp .env.example .env
```

### Sans clé API (mode mock)

Si `LBA_API_KEY` est vide, l'ingestion utilise l'échantillon local
`src/alternance/samples/sample_offers.json` : toute la chaîne (ingestion + consultation)
fonctionne sans réseau.

### Avec la clé API

1. Obtenez une clé sur https://api.apprentissage.beta.gouv.fr/fr/compte/profil
2. Renseignez `LBA_API_KEY` dans `.env`
3. L'URL de base par défaut est `https://api.apprentissage.beta.gouv.fr/api` (préfixe `/api` obligatoire).

> ⚠️ Le fichier `.env` contient un secret et est ignoré par git. Ne le committez jamais.

## Lancer MongoDB

```bash
docker compose up -d
```

L'image `mongo:7` est lancée sur `localhost:27017` avec un volume persistant.

## Ingestion

### CLI

```bash
# LBA — mode mock (par défaut si pas de clé)
uv run python -m src.alternance.ingest

# LBA — API réelle
uv run python -m src.alternance.ingest --use-api

# Scraping Indeed (peut être bloqué par l'anti-bot / robots.txt)
uv run python -m src.alternance.ingest --source indeed

# LBA + Indeed combinés
uv run python -m src.alternance.ingest --source both

# Limiter le nombre d'offres
uv run python -m src.alternance.ingest --max 100

# Requête Indeed personnalisée + fiches détaillées
uv run python -m src.alternance.ingest --source indeed --indeed-query "data" --indeed-details
```

Options CLI :

| Option | Description |
|---|---|
| `--source {lba,indeed,both}` | Source des offres (défaut `lba`) |
| `--use-api` | Force l'appel à l'API LBA (nécessite `LBA_API_KEY`) |
| `--max N` | Limite le nombre d'offres |
| `--indeed-query Q` | Requête de recherche Indeed (défaut `alternance`) |
| `--indeed-details` | Récupère aussi les fiches détaillées Indeed (`viewjob`) |

> ⚠️ **Indeed** : le scraping en direct est souvent bloqué (anti-bot HTTP 403) et interdit
> par `robots.txt` (`/emploi/`, `/viewjob`). Le parsing est couvert par des tests sur
> fixtures. Voir [Sources & normalisation](sources-normalisation.md).

### Depuis Python

```python
from alternance.ingest import ingest

# Source LBA
report = ingest(use_api=True, max_offers=200)
# {'source': 'lba', 'offers_ingested': 200, 'duckdb_total': 384, 'mongo_total': 384}

# Source Indeed
report = ingest(source="indeed", max_offers=50)

# Les deux sources
report = ingest(source="both", max_offers=300)
```

L'ingestion écrit **les mêmes offres** (normalisées vers `JobOffer`) dans DuckDB et MongoDB
(upsert sur l'identifiant).

## Application web

```bash
uv run uvicorn src.alternance.web.app:app --reload
```

Ouvrir http://127.0.0.1:8000

| Route | Méthode | Description |
|---|---|---|
| `/` | GET | Liste des offres. Query params : `backend` (`duckdb`\|`mongo`), `title`, `limit` |
| `/offers/{id}` | GET | Page HTML de détail d'une offre |
| `/offers` | GET | Liste JSON des offres (mêmes params que `/`) |
| `/offers/{id}/json` | GET | Détail d'une offre en JSON brut |
| `/health` | GET | État des connexions DuckDB / MongoDB |

La documentation interactive OpenAPI est disponible sur `/docs` (générée par FastAPI).

### Exemples curl

```bash
# Liste depuis DuckDB
curl "http://127.0.0.1:8000/?backend=duckdb"

# Recherche par titre sur MongoDB
curl "http://127.0.0.1:8000/offers?backend=mongo&title=python"

# Détail JSON d'une offre
curl "http://127.0.0.1:8000/offers/6ac96842015572e53e599d18/json"

# État de santé
curl "http://127.0.0.1:8000/health"
```

## API La Bonne Alternance — rappel des endpoints

| Endpoint | Rôle | Limite |
|---|---|---|
| `GET /api/job/v1/search` | Recherche d'offres (résultats complets) | 60 appels/min |
| `GET /api/job/v1/offer/{id}` | Détail d'une offre | 120 appels/min |
| `GET /api/job/v1/export` | Export total en JSON | 2 appels/min |

Authentification : header `Authorization: Bearer <API_KEY>`.

Filtres de recherche disponibles : `longitude`, `latitude`, `radius`, `target_diploma_level`,
`romes`, `rncp`, `opco`, `departements`, `partners_to_exclude`.
