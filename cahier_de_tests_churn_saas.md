# Cahier de tests — Churn SaaS, mécanismes portés depuis InduSense

> **Public** : évaluateurs, testeurs, formateur — toute personne qui doit vérifier que les
> trois mécanismes portés depuis `py-init/ml` (versioning Bronze/Silver/Gold, recherche du
> modèle optimal, déploiement + observabilité) fonctionnent réellement, pas juste lire qu'ils
> fonctionnent. Chaque cas de test référence soit un fichier `tests/test_*.py` exécutable
> directement, soit une commande déjà exécutée pendant le développement -- les résultats
> attendus sont les résultats réellement mesurés (chiffres exacts), pas des cibles théoriques.

## Convention

| Colonne | Signification |
|---|---|
| **ID** | `TC-<domaine>-<numéro>` |
| **Résultat attendu** | ce qui doit être observé -- un nombre de tests, un code retour, une valeur figée |
| **Preuve** | fichier de test ou commande qui a produit ce résultat |

Statut de chaque domaine à la dernière exécution complète : ✅ tous les cas passent.

## Prérequis communs

```bash
python -m pip install -r requirements.txt
python -m pip install pytest optuna mlflow prometheus_client httpx
```

Pour les cas TC-STACK-*, TC-API-02+ et TC-DRIFT-03+ : Docker Desktop, et la stack démarrée
(`docker compose up -d --build --wait`) -- voir `guide_experimentation_churn_saas.md` §2.

---

## 1. Versioning Bronze → Silver → Gold — ✅

| ID | Objectif | Étapes | Résultat attendu | Preuve |
|---|---|---|---|---|
| TC-VER-01 | Les fonctions extraites des notebooks 01-03 sont testées unitairement | `pytest tests/test_versioning.py tests/test_bronze.py tests/test_silver.py tests/test_gold.py -v` | 42 passed (3+6+20+13) | `tests/test_{versioning,bronze,silver,gold}.py` |
| TC-VER-02 | `clean_silver()` reproduit exactement le Silver réel | rejouer `src.silver.clean_silver(bronze, catalogue)` contre `data/bronze/*.parquet`, comparer à `data/silver/clients_churn_silver.parquet` | 5000 lignes, 35 doublons supprimés, contenu strictement identique (`pd.testing.assert_frame_equal`) | exécuté en session, voir historique de développement |
| TC-VER-03 | `build_gold()` reproduit exactement le Gold réel | rejouer `src.gold.build_gold(silver)` contre `data/silver/clients_churn_silver.parquet`, comparer à `data/gold/clients_churn_gold.parquet` et `gold_manifest.json` | corrélation de fuite -0,881, AUC 0,999, split train/test 28,0%/28,0% (seed 42), features et leurres identiques au manifeste | idem |
| TC-VER-04 | La chaîne de hash sha256 reste vérifiable de bout en bout | comparer `sha256_gold` de `gold_manifest.json` au `gold_sha256` de `model_manifest.json` | valeurs identiques (`c3f400321b24...`) | `data/gold/gold_manifest.json`, `data/model/model_manifest.json`, `data/README.md` |

## 2. Recherche du modèle optimal (Optuna + MLflow) — ✅

| ID | Objectif | Étapes | Résultat attendu | Preuve |
|---|---|---|---|---|
| TC-SEARCH-01 | Le mécanisme de recherche et de tracking est testé unitairement | `pytest tests/test_model_search.py tests/test_tracking.py -v` | 10 passed (5+5) | `tests/test_model_search.py`, `tests/test_tracking.py` |
| TC-SEARCH-02 | La recherche est reproductible à seed fixe | `search_best_params(..., n_trials=3, random_state=42)` exécuté deux fois | mêmes `best_params` aux deux exécutions | `tests/test_model_search.py::TestSearchBestParams::test_meme_seed_donne_les_memes_meilleurs_params` |
| TC-SEARCH-03 | La recherche confirme (ou infirme) le choix de modèle déjà retenu | recherche Optuna (25 trials, 5 folds) sur la forêt aléatoire, contre le vrai Gold train, évaluée sur le vrai Gold test | PR-AUC test forêt optimisée = 0,716 (contre 0,713 non optimisée) -- **toujours inférieur** à la régression logistique retenue (0,759) : la décision `model_manifest.json` reste valide après recherche | exécuté en session (~100 s, 25 trials) |
| TC-SEARCH-04 | Un run est tracé dans MLflow avec le tag de provenance Gold | `log_training_run(..., gold_sha256="...")` puis `mlflow.get_run(run_id)` | le run porte `tags["gold_sha256"]` et les métriques loguées | `tests/test_tracking.py::TestLogTrainingRun` |

## 3. Règle de décision de scoring D9/D10/D14 — ✅

| ID | Objectif | Étapes | Résultat attendu | Preuve |
|---|---|---|---|---|
| TC-SCORE-01 | `src/scoring.py` (réaligné sur le notebook 06 réel) est testé unitairement | `pytest tests/test_scoring.py -v` | 17 passed | `tests/test_scoring.py` |
| TC-SCORE-02 | Le seuil D9 recalculé sur le vrai cycle de test reproduit la valeur figée en production | `calibrer_seuil_d9(y_true, score_churn, rappel_cible=0.80)` sur `gold[split=="test"]` | seuil = 0,282, rappel = 0,80 -- identique à `scoring_manifest.json` | exécuté en session |
| TC-SCORE-03 | La capacité CSM (D10) plafonne bien la priorité Haute | `assigner_priorites(..., seuil_d9=0.282, capacite_haute=150)` sur le même cycle | exactement 150 comptes en `Haute`, 207 en `Moyenne`, 643 en `Basse` | exécuté en session |
| TC-SCORE-04 | Conformité D3 / art. 22 RGPD | `action_est_conforme_d3(...)` sur les 3 actions du catalogue D11 + 3 formulations à risque | les 3 actions réelles conformes, les 3 formulations à risque rejetées | `tests/test_scoring.py::TestConformiteD3` |

## 4. API de scoring — ✅

| ID | Objectif | Étapes | Résultat attendu | Preuve |
|---|---|---|---|---|
| TC-API-01 | Contrôles de service testés unitairement (auth, débit, payload, id de requête, métriques) | `pytest tests/test_api.py -v` | 11 passed | `tests/test_api.py` |
| TC-API-02 | Liveness | `curl http://localhost:8011/health` | `200 {"status":"ok"}` | mesuré en session |
| TC-API-03 | Readiness avec modèles chargés | `curl http://localhost:8011/ready` | `200 {"status":"ready"}` | idem |
| TC-API-04 | Clé API absente rejetée | `POST /score-batch` sans `X-API-Key` | `401` | idem |
| TC-API-05 | Scoring réel bout en bout | `POST /score-batch` avec 3 clients réels du split test, `X-API-Key: dev-local-key` | `200`, `perte_attendue_eur` = score_churn × valeur_vie_estimee_eur, priorité cohérente avec le seuil D9 | mesuré en session (ex. CLI-002449 : score 0,96, priorité Haute) |
| TC-API-06 | Métriques Prometheus exposées | `curl http://localhost:8011/metrics` | contient `churn_saas_http_requests_total`, `churn_saas_scoring_batch_size` | mesuré en session |

## 5. Détection de dérive (PSI/KS) — ✅

| ID | Objectif | Étapes | Résultat attendu | Preuve |
|---|---|---|---|---|
| TC-DRIFT-01 | Calcul PSI/KS testé unitairement (porté à l'identique de InduSense) | `pytest tests/test_drift.py -v` | 7 passed | `tests/test_drift.py` |
| TC-DRIFT-02 | Exposition réelle sur le Gold dataset | `python scripts/export_drift_metrics.py` puis `curl http://localhost:9111/metrics` | 21 features numériques évaluées, PSI < 0,25 sur toutes (split train/test aléatoire, pas de vraie dérive) | mesuré en session |
| TC-DRIFT-03 | Règle d'alerte Prometheus chargée | `curl http://localhost:9092/api/v1/rules` | groupe `churn-saas-drift`, règle `ChurnSaasDriftPSIEleve` présente | mesuré en session |

## 6. Stack Docker / observabilité — ✅

| ID | Objectif | Étapes | Résultat attendu | Preuve |
|---|---|---|---|---|
| TC-STACK-01 | Les deux images se construisent | `docker compose build` | build réussi (`cisia_uc-api`, `cisia_uc-drift-exporter`) | mesuré en session |
| TC-STACK-02 | Tous les services démarrent sains | `docker compose up -d --build --wait` | `api` et `prometheus` `healthy`, `drift-exporter` et `grafana` `Started`/`healthy` | mesuré en session |
| TC-STACK-03 | Les 2 cibles Prometheus sont `up` | `curl http://localhost:9092/api/v1/targets` | `churn-saas-api` et `churn-saas-drift` = `up` | mesuré en session |
| TC-STACK-04 | Dashboard Grafana provisionné | `curl -u admin:admin http://localhost:3011/api/search?query=` | dossier `Churn SaaS`, dashboard `churn-saas-observabilite` listés | mesuré en session |

---

## Matrice de synthèse

| Domaine | Cas de test | Tests pytest | Statut |
|---|---|---|---|
| Versioning Bronze/Silver/Gold | 4 | 42 | ✅ |
| Recherche du modèle optimal | 4 | 10 | ✅ |
| Règle de décision D9/D10/D14 | 4 | 17 | ✅ |
| API de scoring | 6 | 11 | ✅ |
| Dérive | 3 | 7 | ✅ |
| Stack Docker/observabilité | 4 | — | ✅ |
| **Total** | **25** | **87** | ✅ |

`pytest tests/ -q` → **87 passed**.

## Limites connues — non couvertes par ce cahier, par construction

- **Recherche du modèle optimal limitée à la forêt aléatoire.** La régression logistique
  (modèle réellement retenu) n'a qu'un hyperparamètre significatif (`C`, laissé à sa valeur
  par défaut) -- aucun espace de recherche n'a été construit dessus. TC-SEARCH-03 confirme la
  décision existante, il ne la remet pas en cause par une recherche plus large.
- **Dérive mesurée sur un split aléatoire, pas sur un vrai nouveau cycle.** TC-DRIFT-02
  compare `train` à `test` (même tirage stratifié, pas de décalage temporel réel) : le PSI
  proche de 0 mesuré est attendu et ne prouve pas que l'exporteur détecterait une vraie
  dérive terrain -- seul le mécanisme de calcul est prouvé (voir aussi `tests/test_drift.py`
  pour les cas de dérive franche, sur données synthétiques).
- **Seuil D9 et capacité D10 figés, jamais recalculés en production.** Aucun mécanisme de
  recalibration continue n'existe : une dérive du taux de churn réel rendrait le seuil 0,282
  progressivement obsolète sans que rien ne l'alerte automatiquement (contrairement au PSI,
  qui surveille les features, pas la calibration du seuil lui-même).
- **Rate limit en mémoire, par instance.** Comme dans InduSense : suffisant pour une seule
  instance de l'API, pas pour un déploiement multi-instance (un load balancer devant
  plusieurs replicas contournerait la limite).
- **MLflow en SQLite local, pas de registre partagé.** `data/model/mlflow.db` n'existe que
  sur la machine qui l'a produit -- pas de serveur MLflow centralisé, pas de Model Registry.
- **Pas de CI/CD.** Contrairement à InduSense (`TC-PKG-05`), aucun pipeline GitHub Actions ne
  rejoue ce cahier automatiquement à chaque changement.
- **`notebooks/01-06` ne sont pas branchés sur `src/`.** Les notebooks conservent leur propre
  copie de la logique (utile pédagogiquement) ; seul `src/` est couvert par ce cahier. Un
  changement dans un notebook peut diverger de `src/` sans qu'aucun test ne le détecte (déjà
  arrivé une fois : voir la correction de `src/scoring.py` sur la logique D9/D10).
- **Pas de mesure d'impact post-déploiement.** D12 (groupe témoin) et D13 (cadence de
  reporting) sont explicitement hors périmètre (`scoring_manifest.json`) -- aucun mécanisme
  ne mesure si les actions recommandées réduisent réellement le churn.
