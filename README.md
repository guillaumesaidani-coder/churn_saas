# Churn SaaS : prédiction de la résiliation client

Projet de certification « Concevoir et implémenter une solution d'intelligence artificielle ».
Cas d'usage : estimer la probabilité qu'un compte client B2B résilie à l'échéance (classification
binaire), et estimer sa valeur vie client (régression, cible secondaire), pour aider les équipes
Customer Success à prioriser leurs actions de rétention.

| Ressource | Lien |
|---|---|
| **Notebook de certification exécuté (livrable)** | [`reports/notebooks/notebook_certifiant_churn_saas.ipynb`](reports/notebooks/notebook_certifiant_churn_saas.ipynb) |
| **Documentation** (architecture, API, model cards, décisions, exploitation) | [`docs/index.md`](docs/index.md) |
| Code (GitHub) | https://github.com/guillaumesaidani-coder/churn_saas |
| **Jeu de données et modèles (téléchargement libre, release v2.0)** | https://github.com/guillaumesaidani-coder/churn_saas/releases/tag/v2.0 |
| Versioning DVC (DagsHub, compte gratuit requis pour naviguer) | https://dagshub.com/guillaume.saidani/churn_saas |
| Runs d'entraînement (MLflow sur DagsHub) | https://dagshub.com/guillaume.saidani/churn_saas.mlflow |

## Résultats du modèle v2.1 (notebook de certification, jeu de test de 1 000 comptes)

| | Valeur |
|---|---|
| Modèle churn | Régression logistique, 20 variables (Gold v2, version v2.1 : retards de paiement impossibles neutralisés) |
| PR-AUC / ROC-AUC (test) | 0,748 / 0,882 (baseline métier : 0,593 / 0,791) |
| Seuil D9 (calculé hors pli) | 0,283 : rappel 82,5 %, précision 63,1 % |
| 150 priorités Hautes | 102 comptes réellement partis (hasard : 42), 82 % de la perte réelle captée |
| CLV | Gradient boosting sur log(CLV) : R² log 0,89, erreur relative médiane 42 % |

## Explicabilité et base de connaissance

Chaque score est expliqué, et le modèle est confronté à ce que l'on sait du domaine
(`src/explain.py`, notebook §9.6.1 à §9.6.3, §10.2.1, §12.4.1, §13.1.1) :

- **Base de connaissance** [`knowledge/base_connaissance.yaml`](knowledge/base_connaissance.yaml),
  écrite avant de regarder le modèle : libellé, unité, plage et sens d'effet attendu de chaque
  variable, variables exclues (fuite, cibles, leurres, redondances) et leur raison, règles de décision.
- **Explication de chaque compte** : contributions exactes au score (régression logistique :
  coefficient × écart à la moyenne d'entraînement, égales aux valeurs SHAP), les 3 facteurs qui
  augmentent et les 3 qui diminuent le risque, la trace de la règle D9/D10/D14, et des
  avertissements (valeur manquante imputée, hors plage, modalité inconnue).
- **Contrôles** : variable exclue présente, effet de sens contraire à l'attendu, une variable qui
  porte plus de 50 % de l'explication (signature de fuite), modalités hors dictionnaire.
- **API** : `POST /score-batch?explain=true` ajoute l'explication à chaque compte ; `/ready`
  répond 503 si le modèle servi contient une variable exclue par la base (donc la CI échoue).

Détail : [base de connaissance](docs/explicabilite/base_de_connaissance.md),
[contrôles](docs/explicabilite/controles.md), [lire une explication](docs/explicabilite/lire_une_explication.md).

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
docs/                 documentation de référence (lisible sur GitHub et dans Obsidian) ; point d'entrée docs/index.md
src/                  code réutilisable (nettoyage, gold, scoring, explicabilité, API, tracking MLflow, dérive)
knowledge/            base de connaissance du domaine (explications et contrôles du modèle)
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
