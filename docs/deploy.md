# Déploiement & exploitation

## Dépendances

| Composant | Rôle | Installation |
|---|---|---|
| Python ≥ 3.12 | Runtime | système |
| uv | Gestion de l'environnement | https://docs.astral.sh/uv/ |
| DuckDB | Base relationnelle (fichier local) | via `uv sync` |
| MongoDB | Base documentaire (service) | `docker compose up -d` |
| Docker | Conteneurisation de MongoDB | https://docs.docker.com/ |

L'environnement Python est géré par `uv sync` (crée `.venv/` et résout `uv.lock`).

## Configuration

Toutes les valeurs sont lues depuis `.env` (voir `.env.example`) via `pydantic-settings` :

| Variable | Défaut | Description |
|---|---|---|
| `LBA_API_BASE_URL` | `https://api.apprentissage.beta.gouv.fr/api` | URL de base de l'API (préfixe `/api` requis) |
| `LBA_API_KEY` | *(vide)* | Clé API. Vide = mode mock |
| `DUCKDB_PATH` | `data/alternance.duckdb` | Chemin du fichier DuckDB |
| `MONGO_URI` | `mongodb://localhost:27017` | URI de connexion MongoDB |
| `MONGO_DB` | `alternance` | Nom de la base MongoDB |

### Bonnes pratiques

- Ne jamais committer `.env` (ignoré par `.gitignore`).
- La clé API est sensible : rotation régulière, accès limité.
- Les fichiers de données (`data/`, `*.duckdb`) sont ignorés par git.

## Services

### MongoDB (Docker Compose)

```bash
docker compose up -d      # démarre
docker compose ps         # état
docker compose down       # arrête (volume persistant conservé)
docker compose down -v    # arrête + supprime le volume (données perdues)
```

Le conteneur s'appelle `lba-mongo` (image `mongo:7`), exposé sur `localhost:27017`.

### Application web

```bash
uv run uvicorn src.alternance.web.app:app --reload      # dev
uv run uvicorn src.alternance.web.app:app --host 0.0.0.0 --port 8000   # exposée
```

## Commandes utiles

```bash
# Ingestion
uv run python -m src.alternance.ingest --use-api --max 500

# Tests
uv run pytest

# Lancer l'app
uv run uvicorn src.alternance.web.app:app
```

## Points d'attention

- **Rate limits API LBA** : 60 appels/min (search), 120/min (détail), 2/min (export).
  Le client intègre des réessais avec backoff. Une ingestion massive via `/job/v1/export`
  doit espacer les appels.
- **Cohérence des identifiants** : DuckDB utilise la PK `id` ; MongoDB utilise `_id`.
  L'identifiant retenu est `identifier.id` (sinon `partner_job_id`). Les deux bases
  contiennent les mêmes offres, adressables par le même identifiant.
- **Volume** : DuckDB est embarqué (fichier local) — parfait pour un usage mono-machine.
  MongoDB nécessite un serveur ; adaptez le plan mémoire du conteneur selon le volume.
