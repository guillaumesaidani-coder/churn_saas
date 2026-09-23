# Guide d'expérimentation — mécanismes portés depuis InduSense

> **Public** : toute personne qui veut dérouler elle-même le cahier de tests
> (`cahier_de_tests_churn_saas.md`) -- évaluateur, formateur, nouveau contributeur. Toutes les
> commandes ci-dessous ont réellement été exécutées pendant le développement -- rien de
> spéculatif.

## 0. Ce que vous allez pouvoir faire

1. Lancer la suite de tests unitaires complète (87 tests, aucune dépendance externe).
2. Vérifier que le versioning Bronze → Silver → Gold reproduit exactement les données réelles.
3. Relancer la recherche d'hyperparamètres (Optuna) et voir si elle change la décision de modèle.
4. Démarrer la stack complète (API + Prometheus + Grafana + exporteur de dérive) en une commande.
5. Appeler l'API de scoring et lire sa réponse.
6. Observer la dérive dans Grafana et vérifier que l'alerte Prometheus est chargée.

## 1. Prérequis

| Outil | Usage | Vérifier |
|---|---|---|
| Python 3.13 | tests, scripts | `python --version` |
| pip | dépendances | `python -m pip --version` |
| Docker Desktop | stack API/Prometheus/Grafana (§3+) | `docker compose version` |

### 1.1 Installer les dépendances

```bash
python -m pip install -r requirements.txt
python -m pip install pytest optuna mlflow prometheus_client httpx
```

Rien de tout cela n'est nécessaire pour lire les notebooks 00-06 (qui restent la version
pédagogique, indépendante de `src/`) -- seulement pour dérouler ce cahier de tests.

## 2. Dérouler la suite de tests unitaires (§1 à §5 du cahier)

```bash
python -m pytest tests/ -q
# 87 passed
```

Pour un domaine précis (correspond à chaque section du cahier de tests) :

```bash
python -m pytest tests/test_versioning.py tests/test_bronze.py tests/test_silver.py tests/test_gold.py -v   # TC-VER
python -m pytest tests/test_model_search.py tests/test_tracking.py -v                                       # TC-SEARCH
python -m pytest tests/test_scoring.py -v                                                                    # TC-SCORE
python -m pytest tests/test_api.py -v                                                                        # TC-API
python -m pytest tests/test_drift.py -v                                                                      # TC-DRIFT
```

## 3. Vérifier le versioning contre les données réelles (TC-VER-02/03)

```python
import json
import pandas as pd
from src.silver import clean_silver
from src.gold import build_gold

bronze = pd.read_parquet("data/bronze/clients_churn_bronze.parquet")
catalogue = pd.read_parquet("data/bronze/catalogue_plans_bronze.parquet")
silver_out, report = clean_silver(bronze, catalogue)
print(report)  # {'n_doublons': 35, ...}

silver_expected = pd.read_parquet("data/silver/clients_churn_silver.parquet")
pd.testing.assert_frame_equal(silver_out.reset_index(drop=True), silver_expected.reset_index(drop=True), check_dtype=False)
print("Silver reproduit à l'identique.")

gold_out, info = build_gold(silver_out)
manifest = json.load(open("data/gold/gold_manifest.json", encoding="utf-8"))
print(info["feature_columns"] == manifest["features_modele_principal"])  # True
```

## 4. Relancer la recherche du modèle optimal (TC-SEARCH-03)

```python
import json
import pandas as pd
from src.model_search import build_rf_pipeline, search_best_params

gold = pd.read_parquet("data/gold/clients_churn_gold.parquet")
manifest = json.load(open("data/gold/gold_manifest.json", encoding="utf-8"))
feature_columns = manifest["features_modele_principal"]

train = gold[gold["split"] == "train"]
X_train, y_train = train[feature_columns], train["churn"]
cat_cols = [c for c in feature_columns if not pd.api.types.is_numeric_dtype(gold[c])]
num_cols = [c for c in feature_columns if c not in cat_cols]

def builder(params):
    return build_rf_pipeline(cat_cols, num_cols, params)

best_params, study = search_best_params(builder, X_train, y_train, n_trials=25)
print(best_params, study.best_value)
```

Compter ~100 secondes pour 25 trials. Le résultat mesuré (PR-AUC CV 0,773, PR-AUC test 0,716)
reste sous la régression logistique retenue (0,759) -- voir TC-SEARCH-03.

## 5. Démarrer la stack complète

```bash
docker compose config -q                  # valide compose.yaml
docker compose up -d --build --wait       # api, drift-exporter, prometheus, grafana
docker compose ps                         # api et prometheus doivent etre "healthy"
```

Interfaces disponibles (ports décalés par rapport à une éventuelle stack InduSense déjà
active sur la même machine -- voir §7) :

| Service | URL locale | Identifiants |
|---|---|---|
| API | http://localhost:8011 | `X-API-Key: dev-local-key` |
| Swagger | http://localhost:8011/docs | -- |
| Exporteur de dérive | http://localhost:9111/metrics | -- |
| Prometheus | http://localhost:9092 | aucun |
| Grafana | http://localhost:3011 | `admin`/`admin` |

## 6. Appeler l'API de scoring (TC-API-02 à 06)

```bash
curl -s http://localhost:8011/health
# {"status":"ok"}

curl -s http://localhost:8011/ready
# {"status":"ready"}

curl -s -X POST http://localhost:8011/score-batch \
  -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" \
  -d '{"clients": [{"client_id": "TEST-1", "features": {"anciennete_mois": 12, "csat": 3}}]}'
# {"resultats": [{"client_id": "TEST-1", "score_churn": ..., "priorite": ..., ...}]}
```

Le contrat complet des features attendues (30 colonnes) est celui de
`data/model/model_manifest.json` -> `features`.

## 7. Observer la dérive dans Grafana/Prometheus (TC-DRIFT-02/03, TC-STACK-03/04)

```bash
curl -s http://localhost:9092/api/v1/targets      # churn-saas-api et churn-saas-drift = up
curl -s http://localhost:9092/api/v1/rules        # ChurnSaasDriftPSIEleve chargée
curl -s -u admin:admin http://localhost:3011/api/search?query=   # dashboard "Churn SaaS"
```

Dans Grafana : dossier **Churn SaaS** → **Churn SaaS — service & dérive** (PSI par feature,
taux d'alerte, requêtes API par statut, p95 de latence, taille des batches, p-value KS).

## 8. Arrêter et nettoyer

```bash
docker compose down            # conserve les volumes (prometheus_data, grafana_data)
docker compose down -v         # + supprime les volumes
```

## 9. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `Bind for 0.0.0.0:8011 failed: port is already allocated` | une autre stack (InduSense ou autre) occupe déjà ce port | changer le port hôte dans `compose.yaml` (ex. `8012:8000`), ou arrêter l'autre stack |
| `docker compose up` reste bloqué sur `prometheus` | `api` pas encore `healthy` (dépendance `condition: service_healthy`) | attendre le `HEALTHCHECK` du Dockerfile (10s d'intervalle, 5s de démarrage) |
| `/ready` renvoie `503` | `data/model/model.joblib` ou `model_clv.joblib` absent au moment du build de l'image | vérifier que ces fichiers existent avant `docker compose build` (ils sont copiés à la construction, pas montés en volume) |
| `pytest tests/test_api.py` échoue sur `test_ready_503_quand_aucun_artefact_charge` | confusion entre le `tmp_path` de la fixture `artifacts_dir` et celui du test | pointer vers un sous-répertoire distinct (`tmp_path / "vide"`), pas le même `tmp_path` que celui déjà peuplé |
| La recherche Optuna (§4) semble lente | 25 trials × 5 folds = 125 entraînements de forêt aléatoire | normal, ~100 s sur les 5000 lignes du Gold dataset ; réduire `n_trials` pour un essai plus rapide |
