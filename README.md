# Churn SaaS : prédiction de la résiliation client

Projet de certification « Concevoir et implémenter une solution d'intelligence artificielle ».
Cas d'usage : estimer la probabilité qu'un compte client B2B résilie à l'échéance (classification
binaire), et estimer sa valeur vie client (régression, cible secondaire), pour aider les équipes
Customer Success à prioriser leurs actions de rétention.

| Ressource | Lien |
|---|---|
| **Notebook de certification exécuté (livrable)** | [`reports/notebooks/notebook_certifiant_churn_saas.ipynb`](reports/notebooks/notebook_certifiant_churn_saas.ipynb) |
| Code (GitHub) | https://github.com/guillaumesaidani-coder/churn_saas |
| Jeu de données et modèles (DagsHub, DVC) | https://dagshub.com/guillaume.saidani/churn_saas |
| Runs d'entraînement (MLflow sur DagsHub) | https://dagshub.com/guillaume.saidani/churn_saas.mlflow |

## Résultats du modèle v2 (notebook de certification, jeu de test de 1 000 comptes)

| | Valeur |
|---|---|
| Modèle churn | Régression logistique, 20 variables (Gold v2) |
| PR-AUC / ROC-AUC (test) | 0,761 / 0,883 (baseline métier : 0,593 / 0,791) |
| Seuil D9 (calculé hors pli) | 0,286 : rappel 80,7 %, précision 62,4 % |
| 150 priorités Hautes | 97 comptes réellement partis (hasard : 42), 84 % de la perte réelle captée |
| CLV | Gradient boosting sur log(CLV) : R² log 0,89, erreur relative médiane 43 % |

## Résultats v1 (notebooks 04 à 06, conservés pour comparaison)

| Modèle churn | ROC-AUC | PR-AUC |
|---|---|---|
| Baseline (Dummy) | 0,534 | 0,296 |
| **Régression logistique (retenue)** | **0,880** | **0,759** |
| Forêt aléatoire | 0,859 | 0,713 |

Régression CLV : forêt aléatoire sur `log1p(cible)`, R² = 0,697, MAE = 40 615 €.
Seuil de décision : 0,282 (rappel ≥ 80 %, décision D9), voir `data/model/scoring_manifest.json`.

## Structure

```
Examen_cas d'usage candidat/*.csv.dvc   données brutes (versionnées par DVC)
notebooks/            notebook_certifiant_churn_saas.ipynb (livrable) + notebooks v1 par étape (00 à 06)
reports/notebooks/    mêmes notebooks exécutés par le pipeline, avec leurs sorties
data/{rgpd,bronze,silver,gold,model,model_v2}/   sorties du pipeline, avec un manifeste par étape (hash SHA-256)
src/                  code réutilisable (nettoyage, gold, scoring, API, tracking MLflow, dérive)
tests/                tests unitaires (pytest)
dvc.yaml / dvc.lock   pipeline reproductible RGPD → Bronze → Silver → Gold → modèles → scoring
Dockerfile, compose.yaml   API de scoring, exporteur de dérive, Prometheus, Grafana, pipeline
.github/workflows/ci.yml   CI : tests, puis dvc pull, build Docker et test de fumée
```

## Reproduire

```bash
pip install -r requirements-dev.txt
dvc pull            # récupère données et modèles depuis DagsHub
dvc repro           # rejoue uniquement les étapes dont une dépendance a changé
dvc repro certification   # exécute le notebook de certification
pytest              # tests unitaires
mlflow ui --backend-store-uri sqlite:///data/model/mlflow.db   # runs tracés en local
# Pour tracer sur le serveur MLflow de DagsHub plutôt qu'en local :
#   MLFLOW_TRACKING_URI=https://dagshub.com/guillaume.saidani/churn_saas.mlflow
#   MLFLOW_TRACKING_USERNAME=<user DagsHub>  MLFLOW_TRACKING_PASSWORD=<jeton DagsHub>
```

Avec Docker :

```bash
docker compose up -d                                   # API :8011, Grafana :3011, Prometheus :9092
docker compose --profile pipeline run --rm pipeline    # dvc repro dans un conteneur
```

## Données personnelles

La clé et la table de pseudonymisation (`data/rgpd/keymap_*`) ne sont jamais publiées : elles
sont exclues de Git et du cache DVC. Le reste de la gouvernance est décrit dans `data/README.md`
et `data/rgpd/rgpd_gate_manifest.json`.
