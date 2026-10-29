# Décisions d'architecture (ADR)

Historique des choix structurants du projet, au format ADR (Architecture Decision Record).

## ADR-001 — Stocker les offres dans DuckDB ET MongoDB

- **Statut** : acceptée
- **Contexte** : tester les deux paradigmes de base de données (relationnel vs
  documentaire) sur les mêmes données issues d'une API JSON.
- **Décision** : les deux bases reçoivent les mêmes offres lors de l'ingestion ; l'API
  web permet de basculer d'un backend à l'autre.
- **Conséquences** : double écriture (léger surcoût), code de stockage dupliqué, mais
  comparaison directe des approches à données équivalentes.

## ADR-002 — Langage Python, gestion de projet via uv

- **Statut** : acceptée
- **Contexte** : projet de formation ; l'environnement local utilise déjà Python et uv.
- **Décision** : Python ≥ 3.12, `uv` pour l'environnement et les dépendances,
  `pyproject.toml` comme source de vérité.
- **Conséquences** : installation reproductible (`uv sync` + `uv.lock`), pas d'outil
  supplémentaire requis.

## ADR-003 — Client API dédié avec mode mock

- **Statut** : acceptée
- **Contexte** : l'API LBA exige une clé ; tester la chaîne complète sans clé ni réseau.
- **Décision** : `LbaApiClient` (retries + backoff) + `load_sample_offers()` qui lit
  `src/alternance/samples/sample_offers.json` si `LBA_API_KEY` est vide.
- **Conséquences** : développement et tests possibles hors-ligne ; l'échantillon mock est
  embarqué dans le paquet.

## ADR-004 — URL de base avec préfixe `/api`

- **Statut** : acceptée
- **Contexte** : `https://api.apprentissage.beta.gouv.fr` sert le front-end ; les vraies
  routes API sont sous `/api` (constaté dans le code source serveur : `prefix: "/api"`).
- **Décision** : `LBA_API_BASE_URL` par défaut = `https://api.apprentissage.beta.gouv.fr/api`.
- **Conséquences** : valeur documentée dans `.env.example` ; évite un 404/HTML de la SPA.

## ADR-005 — Identifiant commun aux deux bases

- **Statut** : acceptée
- **Contexte** : une même offre doit être adressable de façon identique dans les deux bases.
- **Décision** : l'identifiant est `identifier.id`, sinon `partner_job_id` ; utilisé comme
  PK (`offers.id`) dans DuckDB et `_id` dans MongoDB.
- **Conséquences** : les routes `/offers/{id}` fonctionnent à l'identique sur les deux
  backends.

## ADR-006 — API web FastAPI

- **Statut** : acceptée
- **Contexte** : interface de consultation avec liste, détail et bascule de backend.
- **Décision** : FastAPI + templates Jinja2, endpoints JSON pour la consommation
  programmatique.
- **Conséquences** : documentation OpenAPI auto-générée (`/docs`) ; dépendances légères.

## ADR-007 — Tests isolés

- **Statut** : acceptée
- **Contexte** : rendre la suite fiable et exécutable partout.
- **Décision** : DuckDB en fichier temporaire (`tmp_path`), HTTP mocké pour le client API,
  tests Mongo auto-ignorés si le serveur est absent, TestClient FastAPI pour le web.
- **Conséquences** : suite rapide et déterministe ; MongoDB requis uniquement pour les
  tests dédiés.

## ADR-008 — Sources multiples normalisées vers un schéma commun

- **Statut** : acceptée
- **Contexte** : compléter les données de l'API LBA avec une seconde source (scraping
  Indeed) sans dupliquer le pipeline de stockage ni l'application web.
- **Décision** : toute source est convertie vers le modèle commun `JobOffer`
  (structure `JobOfferRead`) via un module de normalisation dédié
  (`scrapers/normalize.py`) avant écriture. L'ingestion accepte un paramètre `--source`
  (`lba`, `indeed`, `both`). Les champs non fournis par une source sont mis à une valeur
  neutre (`[]`, `None`, `1`) pour respecter le schéma.
- **Conséquences** : les offres de toutes les sources sont stockées et consultables de
  façon homogène (mêmes identifiants, mêmes champs, mêmes contraintes) ; le coût est une
  règle de correspondance par source à maintenir.

## ADR-009 — Filtres de consultation (ville, compétence, diplôme)

- **Statut** : acceptée
- **Contexte** : enrichir la consultation web avec des critères de recherche métier :
  localisation (ville), compétence et niveau de diplôme.
- **Décision** : les filtres sont implémentés dans **les deux** stores avec une API
  identique (`list_offers` / `count_offers` acceptent `title`, `city`, `skill`,
  `diploma_level`), exposés dans l'API web (`/offers`) et l'interface (`/`). Le niveau de
  diplôme est normalisé sur le code européen (`3`-`7`). Des facettes (`/filters`)
  alimentent l'auto-complétion de l'interface.
  - DuckDB : clauses `LIKE` + `EXISTS` sur la table `skills`, comparateur sur
    `target_diploma_european`.
  - MongoDB : `$regex` sur `workplace.location.address`, `$or` sur les tableaux de
    compétences, égalité sur `offer.target_diploma.european`.
- **Conséquences** : comportement identique entre les deux backends (mêmes résultats) ;
  le filtre ville opère sur l'adresse complète (code postal + ville).
