# Comparaison : relationnel (DuckDB) vs documentaire (MongoDB)

Ce projet stocke les **mêmes offres** dans les deux bases. Voici les enseignements issus
de l'implémentation réelle.

## Tableau de synthèse

| Critère | DuckDB (relationnel) | MongoDB (documentaire) |
|---|---|---|
| **Modèle** | Normalisé, tables liées par FK | Documents imbriqués (1 offre = 1 doc) |
| **Stockage** | Fichier local embarqué | Serveur dédié (Docker) |
| **Schéma** | Fixe, migrations requises | Flexible, auto-descriptif |
| **Fidélité à la source** | Perte de l'ordre des listes | Fidèle à 100 % |
| **Lecture du détail** | Reconstruction multi-requêtes | 1 lecture directe |
| **Écriture** | Multi-tables (DELETE+INSERT) | 1 `replaceOne` upsert |
| **Interrogation** | SQL (puissant, agrégations naturelles) | `find`/`aggregate` (moins naturel pour agréger) |
| **Recherche texte** | `LIKE` | `$regex` / index texte |
| **Dépendances** | Aucune (bibliothèque) | Serveur + Docker |
| **Cas d'usage** | Rapports, agrégations, volumes analytiques | Stockage de documents, schéma évolutif |

## Observations par opération

### Écriture (ingestion)

- **DuckDB** : pour insérer une offre il faut écrire dans 7 tables. En pratique
  `upsert_offer()` fait un `INSERT ... ON CONFLICT` sur `offers` puis purge/réinsère les
  lignes liées. Plus de code, plus de risques d'incohérence transitoire.
- **MongoDB** : `replace_one(..., upsert=True)` en une opération. L'upsert est
  **idempotent** : relancer l'ingestion ne crée pas de doublons, quelle que soit la
  duplication des réponses API.

### Lecture du détail

- **DuckDB** : `get_offer()` fait jusqu'à 6 requêtes (offers, contracts, contract_types,
  workplaces, apply, skills/rome/questions) pour reconstruire le JSON imbriqué.
- **MongoDB** : `find_one({"_id": …})` renvoie directement le document complet.

### Ordre des listes

- **DuckDB** : les listes sont des lignes → l'ordre d'origine n'est pas garanti (tri
  implicite). Détail non critique ici, mais à retenir.
- **MongoDB** : les tableaux sont stockés dans l'ordre exact de l'API.

### Recherche / filtrage

- **DuckDB** : SQL `WHERE lower(title) LIKE '%…%'` — simple et lisible. Les agrégations
  (compter par ROME, par statut) sont triviales en SQL.
- **MongoDB** : `$regex` fonctionne, mais les agrégations nécessitent une pipeline
  `aggregate` plus verbeuse.

## Recommandations

- **DuckDB** est idéal pour l'**analyse** : requêtes SQL, agrégations, jointures, export
  vers des outils BI. Le fichier embarqué simplifie l'exploitation (pas de serveur).
- **MongoDB** est idéal pour le **stockage de documents structurés** dont le schéma peut
  évoluer, avec un accès par identifiant très rapide et une ingestion sans friction.

Pour un projet comme celui-ci (collecter des offres depuis une API JSON et les
consulter), MongoDB réduit fortement la complexité d'ingestion ; DuckDB est préférable
dès que l'on veut **interroger et agréger** les données de façon analytique.
