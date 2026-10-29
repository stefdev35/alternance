# alternance

Projet de collecte et de consultation des offres d'emploi en alternance à partir de
**plusieurs sources** — l'API [La Bonne Alternance](https://api.apprentissage.beta.gouv.fr)
et le scraping de [Indeed](https://fr.indeed.com) — normalisées vers un **schéma commun**
(`JobOffer`). Les données sont stockées dans **deux bases différentes** afin de tester les
deux approches :

- **DuckDB** (relationnel) : schéma normalisé avec clés primaires/étrangères
- **MongoDB** (NoSQL / documentaire) : chaque offre stockée telle quelle (JSON imbriqué)

La consultation se fait via une petite application web **FastAPI** qui permet de basculer
d'un backend à l'autre et d'afficher le détail de chaque annonce.

## API utilisée (source LBA)

- Recherche : `GET /job/v1/search` (filtres : romes, rncp, departements, opco, géolocalisation…)
- Détail d'une offre : `GET /job/v1/offer/{id}`
- Auth : header `Authorization: Bearer <API_KEY>`

> Sans clé API, le projet utilise un **mode mock** (`src/alternance/samples/sample_offers.json`)
> pour tester toute la chaîne (ingestion + consultation) sans réseau.

## Prérequis

- Python ≥ 3.12 et [uv](https://docs.astral.sh/uv/)
- Docker (pour MongoDB)

## Installation

```bash
# 1. Environnement
uv sync

# 2. Config (optionnel, sinon mode mock)
cp .env.example .env
# → renseigner LBA_API_KEY si vous avez une clé

# 3. Lancer MongoDB (Docker)
docker compose up -d

# 4. Ingérer les offres
uv run python -m src.alternance.ingest                      # LBA (mock si pas de clé)
uv run python -m src.alternance.ingest --use-api            # LBA avec clé
uv run python -m src.alternance.ingest --source indeed      # scraping Indeed
uv run python -m src.alternance.ingest --source both        # LBA + Indeed
```

## Application web

```bash
uv run uvicorn src.alternance.web.app:app --reload
```

Ouvrir http://127.0.0.1:8000

Routes utiles :

| Route | Description |
|---|---|
| `/` | Liste des offres (`?backend=duckdb\|mongo`, `?title=…`, `?city=…`, `?skill=…`, `?diploma_level=…`) |
| `/offers/{id}` | Page de détail d'une offre |
| `/offers` | Liste en JSON (mêmes filtres que `/`) |
| `/offers/{id}/json` | Détail d'une offre en JSON brut |
| `/filters` | Valeurs disponibles pour les filtres (villes, compétences, diplômes) |
| `/health` | État des connexions DuckDB / MongoDB |

## Tests

```bash
uv run pytest
```

71 tests : modèles, client API, scraper Indeed, normalisation, filtres, stockages
DuckDB/MongoDB, ingestion, application web.
Détails : [`docs/tests.md`](docs/tests.md).

## Documentation

- [Guide d'utilisation](docs/usage.md) — installation, ingestion, routes web, API LBA
- [Sources & normalisation](docs/sources-normalisation.md) — compatibilité LBA / Indeed
- [Déploiement](docs/deploy.md) — configuration, services, bonnes pratiques
- [Architecture](docs/architecture/architecture.md) — schémas, modèle de données, ADR

## Structure

```
src/alternance/
├── config.py            # réglages (variables d'environnement)
├── lba_api.py           # client API La Bonne Alternance + mode mock
├── models.py            # modèles Pydantic (structure JobOfferRead)
├── ingest.py            # pipeline d'ingestion multi-sources (CLI)
├── scrapers/
│   ├── indeed.py        # scraper Indeed (recherche + détail, parsing HTML)
│   └── normalize.py     # normalisation Indeed → JobOffer (compatibilité)
├── storage/
│   ├── duckdb_store.py  # approche relationnelle (schéma normalisé)
│   └── mongo_store.py   # approche documentaire (documents complets)
└── web/
    ├── app.py           # application FastAPI
    └── templates/       # pages HTML (liste + détail)
```

## Notes

- L'ingestion écrit les mêmes offres dans les **deux** bases (upsert sur l'identifiant).
- Limites de débit API respectées : 60 appels/min en recherche, 120/min en détail.
- Le fichier DuckDB est stocké dans `data/alternance.duckdb` (ignoré par git).
