# Documentation

Documentation du projet **alternance** — collecte et consultation des offres d'emploi en
alternance via l'API [La Bonne Alternance](https://api.apprentissage.beta.gouv.fr), stockées
dans **DuckDB** (relationnel) et **MongoDB** (documentaire).

## Sommaire

- [Guide d'utilisation](usage.md) — installation, ingestion, application web, CLI
- [Tests](tests.md) — comment lancer et comprendre la suite de tests
- [Déploiement](deploy.md) — dépendances, services, configuration, bonnes pratiques

## Architecture

La documentation d'architecture est dans le dossier
[`architecture/`](architecture/architecture.md) :

| Document | Contenu |
|---|---|
| [architecture.md](architecture/architecture.md) | Vue d'ensemble, composants, flux de données, schémas |
| [architecture-duckdb.md](architecture/architecture-duckdb.md) | Schéma relationnel DuckDB (détaillé) |
| [architecture-mongodb.md](architecture/architecture-mongodb.md) | Modèle documentaire MongoDB (détaillé) |
| [comparaison.md](architecture/comparaison.md) | Comparaison des deux approches (relationnel vs documentaire) |
| [decisions.md](architecture/decisions.md) | Décisions d'architecture (ADR) |
