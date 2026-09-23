# DAT — Churn SaaS v1 (document d'architecture technique du build réel)

> Décrit le système tel qu'il tourne réellement dans ce dépôt (mécanismes portés
> depuis `py-init/ml`, cf. `guide_experimentation_churn_saas.md` et
> `cahier_de_tests_churn_saas.md`) — pas une architecture cible. Chaque affirmation
> renvoie à un fichier réel du dépôt. Pas de section de gouvernance de release, de
> multi-environnement ou d'orchestration : ces briques n'existent pas ici, et ne sont
> pas simulées comme si elles existaient (voir §9).

## 1. Périmètre

Outil d'aide à la décision pour les équipes Customer Success : scoring de risque de
résiliation (`churn`) et de valeur vie client (`CLV`), priorisation d'actions —
jamais d'exécution automatique (contrainte de l'énoncé, cf.
`Livrables/sections_02_03_cadrage_argumente.md` §2). Un seul environnement local +
Docker Compose, pas de staging/production.

## 2. Vue d'ensemble par brique

| Brique | Rôle | Statut réel | Preuve |
|---|---|---|---|
| Gate RGPD | Scan de motifs nominatifs avant toute ingestion, décision GO/NO-GO | ✅ Exécuté, 0 motif détecté sur 5035×29 valeurs | `data/rgpd/rgpd_gate_manifest.json` |
| Versioning Bronze→Silver→Gold | Ingestion brute → nettoyage → dataset modélisable, hash sha256 chaînés | ✅ Reproduit à l'identique (35 doublons supprimés, 5000 lignes) | `src/bronze.py`, `src/silver.py`, `src/gold.py`, `data/gold/gold_manifest.json` |
| Modélisation churn | Régression logistique retenue, comparée à forêt aléatoire + Optuna | ✅ PR-AUC test 0,759 (LR) > 0,716 (RF optimisée Optuna) | `data/model/model_manifest.json` |
| Modélisation CLV | Régression sur `valeur_vie_client_eur`, mêmes exclusions anti-fuite | ✅ | `data/model/model_clv_manifest.json` (référencé par `data/README.md`) |
| Règle de décision D9/D10/D14 | Seuil calibré (rappel ≥ 80%), capacité CSM, formule de priorité | ✅ seuil 0,282, capacité 150/mois | `data/model/scoring_manifest.json`, `src/scoring.py` |
| API de scoring | FastAPI : `/health`, `/ready`, `/metrics`, `/score-batch` | ✅ 11 tests, bout en bout mesuré | `src/api.py`, `tests/test_api.py` |
| Conteneur | Image multi-stage, non-root (UID 10001), healthcheck stdlib | ✅ | `Dockerfile` |
| Stack locale | Compose : api, drift-exporter, prometheus, grafana | ✅ `docker compose up -d --build --wait` | `compose.yaml` |
| Dérive (PSI/KS) | Exporteur Prometheus, alerte `ChurnSaasDriftPSIEleve` | ✅ 21 features évaluées, règle chargée | `src/drift.py`, `drift_alert_rules.yml` |
| Observabilité | Compteurs/histogrammes HTTP + taille de batch, 1 alerte, dashboard Grafana | ⚠️ Partiel — pas d'Alertmanager, pas de SLO versionné | `src/api.py` (métriques), `prometheus.yml` |
| CI/CD | — | 🔴 Absent — aucun `.github/workflows/` dans ce dépôt | recherche `**/.github/workflows/*.yml` : aucun résultat |
| Orchestration | — | 🔴 Absent — pas de flow planifié, scoring appelé à la demande via l'API | aucun fichier `flows/` dans `src/` |
| Gouvernance de release | — | 🔴 Absent — pas de `release_id`, un seul `model.joblib` chargé directement | `src/api.py::load_artifacts` |

## 3. Pipeline de données

```
CSV fournis (Examen_cas d'usage candidat/)
   -> Gate RGPD (00_conformite_rgpd_anonymisation.ipynb) -> data/rgpd/
   -> Bronze (01_ingestion_bronze.ipynb, src/bronze.py)   -> data/bronze/*.parquet
   -> Silver (02_nettoyage_silver.ipynb, src/silver.py)   -> data/silver/clients_churn_silver.parquet
   -> Gold   (03_preparation_gold.ipynb, src/gold.py)     -> data/gold/clients_churn_gold.parquet
   -> Modèles (04_modelisation_churn, 05_modelisation_clv) -> data/model/model.joblib, model_clv.joblib
   -> Scoring (06_implementation_scoring.ipynb, src/scoring.py) -> API /score-batch
```

Chaque étape écrit un `*_manifest.json` (jamais rempli à la main) avec un champ
`sha256_*` du fichier source et du fichier produit — chaîne de hash vérifiable de
bout en bout (`sha256_gold` de `gold_manifest.json` == `gold_sha256` de
`model_manifest.json`, cf. `data/README.md`).

**Stockage** : Parquet en couches, pas de base relationnelle. Une cible PostgreSQL
avait été envisagée (annoncée dans un TP antérieur) puis explicitement écartée et
documentée comme non active (`silver_manifest.json` → `cible_production` :
"PostgreSQL churn_saas_db.clients_churn (non disponible dans cet environnement)") —
choix argumenté en détail dans
`Livrables/sections_02_03_cadrage_argumente.md` §3 et
`Livrables/architecture_donnees_churn_saas.pptx`.

**Anti-fuite** : `sante_compte_fin_periode` (corrélation -0,881 avec `churn`, AUC
univarié 0,999) conservée dans le Gold pour traçabilité mais exclue du `X` des deux
modèles (churn et CLV) par principe de disponibilité au moment du scoring, pas
seulement pour sa force de corrélation (`gold_manifest.json` → `piege_de_fuite`).

## 4. Modélisation

| | Régression logistique (retenue) | Forêt aléatoire | Forêt aléatoire + Optuna (25 trials) |
|---|---|---|---|
| PR-AUC test | 0,759 | 0,713 | 0,716 |
| ROC-AUC test | 0,88 | 0,859 | — |

30 features (`model_manifest.json` → `features`), seed 42, split stratifié 80/20
(28,0% churn train et test). La recherche Optuna confirme la décision déjà prise :
même optimisée, la forêt aléatoire reste sous la régression logistique
(`cahier_de_tests_churn_saas.md`, TC-SEARCH-03).

Le seuil de coût pur (0,02, sur minimisation de coût seule) est **supersédé** par la
décision métier D9 (rappel cible ≥ 80% sur le jeu de test réel) : seuil 0,282,
précision 0,627 — c'est ce seuil, et lui seul, qui est chargé par l'API en
production (`src/api.py::load_artifacts` lit `scoring_manifest.json`, jamais
`metrics.json`).

## 5. Contrat API

| Endpoint | Auth | Entrée | Sortie |
|---|---|---|---|
| `GET /health` | non | — | `{"status": "ok"}` — liveness pure, ne dépend d'aucun modèle chargé |
| `GET /ready` | non | — | `{"status": "ready"}` ou 503 si `model.joblib`/`model_clv.joblib`/`model_manifest.json` absents |
| `GET /metrics` | non | — | format Prometheus (`churn_saas_http_requests_total`, `churn_saas_scoring_batch_size`, ...) |
| `POST /score-batch` | `X-API-Key` (401 si absente/invalide), rate-limit 60 req/min/IP (429) | `{"clients": [{"client_id", "features": {...}}]}` | `{"resultats": [{"client_id", "score_churn", "valeur_vie_estimee_eur", "perte_attendue_eur", "priorite", "action_recommandee"}]}` |

Limites de sécurité assumées et documentées dans le code même
(`src/api.py`, commentaires sur `_rate_limit_state`) :
- limite de débit en mémoire du process → correcte pour un seul worker Uvicorn,
  non partagée entre plusieurs workers ou instances ;
- pas de proxy/TLS devant l'API — Compose l'expose directement sur l'hôte ;
- pas de séparation `predictions`/`api_predictions` ni de journal d'appels : l'API
  ne persiste rien, elle ne fait que scorer et répondre.

## 6. Conteneur et stack locale

- Image `python:3.13-slim`, non-root (UID 10001), healthcheck via stdlib Python
  (pas de curl/wget pour ne pas grossir l'image) — `Dockerfile`.
- `compose.yaml` : `api` (8011→8000), `drift-exporter` (9111→9110),
  `prometheus` (9092→9090), `grafana` (3011→3000). Ports décalés volontairement
  par rapport à toute stack `py-init/ml` déjà active sur la même machine.
- Dépendances de démarrage : `prometheus` attend `api` `service_healthy` et
  `drift-exporter` `service_started` ; `grafana` attend `prometheus` `service_healthy`.
- Les artefacts modèle (`data/model/`, `data/gold/`) sont **copiés à la
  construction de l'image**, pas montés en volume — un modèle manquant au moment
  du `build` cause un `/ready` à 503 au démarrage (piège documenté dans
  `guide_experimentation_churn_saas.md` §9).

## 7. Observabilité et dérive

- Exporteur dédié (`scripts/export_drift_metrics.py`) : PSI/KS sur 21 features
  numériques du Gold, référence = split train figé, rafraîchi toutes les 60s.
- Règle Prometheus unique : `ChurnSaasDriftPSIEleve` (`churn_saas_drift_psi > 0.25`,
  sévérité "majeure") — chargée et vérifiée `firing`-capable (`drift_alert_rules.yml`).
- Un seul palier d'alerte (binaire stable/dérive), pas de palier intermédiaire
  "à surveiller".
- Dashboard Grafana "Churn SaaS" (PSI par feature, taux d'alerte, requêtes API par
  statut, p95 de latence, taille des batches, p-value KS) — `grafana/provisioning/`.
- Pas d'Alertmanager : la règle passe à `firing` dans Prometheus mais ne route vers
  aucun destinataire.

## 8. Gouvernance des données et conformité

- Portique RGPD (`00_conformite_rgpd_anonymisation.ipynb`) exécuté **avant** toute
  ingestion Bronze — recherche systématique de motifs nominatifs dans
  `commentaire_csm`, 0 résultat sur l'échantillon disponible.
- Décision D7 : `commentaire_csm` n'est **jamais** utilisée comme variable
  explicative, indépendamment du résultat du scan (risque résiduel d'un champ texte
  libre alimenté manuellement).
- Table de correspondance de pseudonymisation disponible (`data/rgpd/keymap_client_id.parquet`)
  mais **non appliquée par défaut** — `client_id` circule en clair tant que personne
  ne décide explicitement de l'utiliser (`rgpd_gate_manifest.json`).
- Conformité art. 22 RGPD (pas de décision entièrement automatisée) vérifiée
  unitairement : `tests/test_scoring.py::TestConformiteD3` — 3 actions réelles du
  catalogue D11 conformes, 3 formulations à risque rejetées.

## 9. Ce qui n'existe délibérément pas dans ce build

Pas des oublis — des choix documentés ailleurs (cadrage, PDC3) plutôt que simulés
ici pour faire nombre :

- **Orchestration planifiée** : aucun scheduler, aucun flow séparé
  entraînement/scoring horaire. Le scoring est appelé à la demande via `/score-batch` ;
  le réentraînement est un notebook rejoué manuellement (04/05), pas un flow.
- **Gouvernance de release** : pas de `release_id`, pas de statut
  CANDIDATE/APPROVED/ACTIVE, pas de rollback automatisé — `model.joblib` chargé
  directement est *de facto* le modèle actif.
- **Multi-environnement** : un seul environnement local + Compose, pas de
  staging/production, donc pas de promotion ni de comparaison de digests.
- **Base de données relationnelle** : écartée au profit du Parquet en couches
  (raisonnement en 3 points dans `Livrables/sections_02_03_cadrage_argumente.md` §3).
- **CI/CD** : aucun pipeline automatisé (`.github/workflows/` absent) — les tests
  (`pytest tests/ -q`, 87 passed) et la stack Docker sont vérifiés manuellement,
  pas en gate automatique.

## 10. Traçabilité — cahier de tests

Chaque brique de ce DAT est couverte par un identifiant `TC-*` exécutable dans
`cahier_de_tests_churn_saas.md` : `TC-VER-*` (versioning), `TC-SEARCH-*` (recherche
modèle), `TC-SCORE-*` (règle de décision), `TC-API-*` (API), `TC-DRIFT-*` (dérive).
Procédure de rejeu complète : `guide_experimentation_churn_saas.md`.
